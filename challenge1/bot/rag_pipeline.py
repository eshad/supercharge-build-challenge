"""
RAG Pipeline — SuperCharge SG Chatbot
Uses ChromaDB (local) + sentence-transformers + OpenAI GPT-4o-mini
"""

import os
import logging
from typing import Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from openai import OpenAI

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
KB_PATH = BASE_DIR / "knowledge_base" / "supercharge_kb.txt"
CHROMA_PATH = BASE_DIR / "chroma_db"

# ── Models ─────────────────────────────────────────────────────────────────
EMBED_MODEL = "all-MiniLM-L6-v2"
LLM_MODEL = "gpt-4o-mini"
COLLECTION_NAME = "supercharge_kb"

# ── System prompt ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are SuperCharge SG's AI customer support assistant. SuperCharge SG is a Singapore-based clean energy company offering EV charging and solar PV installation services.

Your rules:
1. Answer ONLY using the provided context. If the context does not contain the answer, say: "I don't have specific information on that — let me connect you with our team for an accurate answer."
2. Never invent prices, specifications, or facts not in the context.
3. Always be professional, helpful, and concise.
4. For safety/electrical questions, always recommend speaking to our LEW-certified team.
5. For pricing, give the indicative range from context and recommend a site assessment for exact quotes.
6. You represent SuperCharge SG — speak as "we" and "our team".
7. If the user expresses interest in a product or service, guide them toward a free consultation.
8. Confidence threshold: if the context retrieval gives weak results, acknowledge uncertainty and offer to escalate.
"""


class RAGPipeline:
    """ChromaDB-backed RAG pipeline for SuperCharge SG chatbot."""

    def __init__(self):
        self.embedder: Optional[SentenceTransformer] = None
        self.client: Optional[chromadb.PersistentClient] = None
        self.collection = None
        self.oai: Optional[OpenAI] = None
        self._initialized = False

    def initialize(self):
        """Load models and build/load vector store."""
        if self._initialized:
            return
        logger.info("Initialising RAG pipeline…")
        self.embedder = SentenceTransformer(EMBED_MODEL)
        self.oai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False),
        )

        existing = [c.name for c in self.client.list_collections()]
        if COLLECTION_NAME in existing:
            self.collection = self.client.get_collection(COLLECTION_NAME)
            logger.info("Loaded existing ChromaDB collection (%d chunks)", self.collection.count())
        else:
            self._build_index()

        self._initialized = True
        logger.info("RAG pipeline ready.")

    def _build_index(self):
        """Chunk KB text and index into ChromaDB."""
        logger.info("Building ChromaDB index from %s…", KB_PATH)
        text = KB_PATH.read_text(encoding="utf-8")

        # Chunk by section (lines starting with ---) and by paragraph
        chunks = self._chunk_text(text, chunk_size=400, overlap=50)
        logger.info("Created %d chunks", len(chunks))

        embeddings = self.embedder.encode(chunks).tolist()

        self.collection = self.client.create_collection(COLLECTION_NAME)
        self.collection.add(
            documents=chunks,
            embeddings=embeddings,
            ids=[str(i) for i in range(len(chunks))],
        )
        logger.info("Index built with %d chunks.", len(chunks))

    def _chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
        """
        Chunk by logical topic (--- separator), then by token count.
        Keeps Q&A pairs together.
        """
        # Split on section separators
        import re
        sections = re.split(r"\n---\s*[A-Z].*?---\n", text)

        chunks = []
        for section in sections:
            section = section.strip()
            if not section:
                continue
            # Split section into paragraphs
            paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
            current_chunk = ""
            for para in paragraphs:
                # Keep Q+A together: if para starts with Q:, include next para too
                words = para.split()
                if len(current_chunk.split()) + len(words) <= chunk_size:
                    current_chunk = (current_chunk + "\n\n" + para).strip()
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = para

            if current_chunk:
                chunks.append(current_chunk)

        # Remove duplicates and very short chunks
        chunks = [c for c in chunks if len(c.split()) > 10]
        return chunks

    def query(self, user_query: str, history: list[dict], n_results: int = 3) -> tuple[str, float]:
        """
        Run RAG query. Returns (response_text, confidence_score).
        confidence_score: 0.0–1.0 (lower = less confident, should escalate)
        """
        if not self._initialized:
            self.initialize()

        # Embed query
        query_embedding = self.embedder.encode([user_query]).tolist()[0]

        # Retrieve top-k chunks
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

        docs = results["documents"][0]
        distances = results["distances"][0]  # lower = more similar in L2

        # Compute confidence from distances (cosine sim approximation)
        # ChromaDB returns L2 by default; convert to a 0–1 confidence
        # L2 distance: 0 = identical, 2 = orthogonal
        min_dist = min(distances) if distances else 2.0
        confidence = max(0.0, 1.0 - (min_dist / 2.0))

        context = "\n\n".join(docs)

        # Build messages for LLM
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.append({
            "role": "system",
            "content": f"Use ONLY the following context to answer:\n\n{context}\n\nIf the answer is not in the context, say so honestly."
        })

        # Add last 4 turns of history
        for turn in history[-4:]:
            messages.append(turn)

        # Add current query
        messages.append({"role": "user", "content": user_query})

        response = self.oai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.3,
        )

        return response.choices[0].message.content.strip(), confidence


# Global singleton
rag = RAGPipeline()
