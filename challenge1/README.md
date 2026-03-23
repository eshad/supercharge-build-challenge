# Challenge 1 — AI Customer Support Chatbot
**SuperCharge SG Build Challenge 2026 | Mehadi Hasan**

## Overview

RAG-powered Telegram (+ WhatsApp bonus) customer support bot for SuperCharge SG.
Built with FastAPI + python-telegram-bot + ChromaDB + OpenAI GPT-4o-mini.

## Architecture

```
User → Telegram/WhatsApp
         ↓
   FastAPI Webhook Server (Railway.app)
         ↓
   Intent Router (keyword + LLM fallback)
         ↓
   ┌─────────────────────────────────┐
   │  RAG Pipeline                   │
   │  ChromaDB (local, persistent)   │
   │  sentence-transformers embeds   │
   │  GPT-4o-mini response           │
   └─────────────────────────────────┘
         ↓
   Session Manager (in-memory, 30m TTL)
         ↓
   Lead Capture → Google Sheets (gspread)
   Escalation  → Slack webhook + Email
```

## RAG Pipeline

- **Embeddings**: `all-MiniLM-L6-v2` (sentence-transformers, runs locally, no API key needed)
- **Vector store**: ChromaDB persistent local store (`./chroma_db/`)
- **Knowledge base**: `knowledge_base/supercharge_kb.txt` — chunked by logical topic (200–400 tokens)
- **Chunking strategy**: Split on `---` section separators, then by paragraph. Q&A pairs kept together.
- **Top-k retrieval**: k=3 chunks passed to GPT-4o-mini as context
- **LLM**: GPT-4o-mini with SuperCharge persona system prompt
- **Confidence**: L2 distance from ChromaDB → confidence score. Below 0.40 → auto-escalation

## Intents Handled

| Intent | Trigger | Response |
|--------|---------|----------|
| Greeting | hi, hello, help | Welcome message with capabilities |
| EV Charger | ev, charger, ocpp, type 2 | RAG answer |
| Solar Panel | solar, pv, ecis, kwp | RAG answer |
| Price/Quote | price, cost, how much, sgd | RAG answer with pricing ranges |
| Maintenance/Fault | fault, broken, not working | RAG answer + escalation if severe |
| Human Agent | speak to person, support | Immediate escalation + handoff message |
| Lead Capture | interested, want to, book | Multi-turn name/email/enquiry collection |

## Setup

### 1. Get a Telegram Bot Token
1. Message `@BotFather` on Telegram
2. Send `/newbot` → follow prompts
3. Copy the bot token

### 2. Set Up Google Sheets (Lead Capture)
1. Create a new Google Sheet at sheets.google.com
2. Copy the Sheet ID from the URL
3. Go to Google Cloud Console → Create Service Account → Download JSON key
4. Share the Google Sheet with the service account email

### 3. Set Up Slack Webhook (Escalation)
1. Go to api.slack.com/apps → Create New App
2. Enable Incoming Webhooks → Add New Webhook to Workspace
3. Copy the webhook URL

### 4. Deploy to Railway.app (Free)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up

# Set environment variables in Railway dashboard
# (see .env.example for all required variables)
```

### 5. Local Development
```bash
pip install -r requirements.txt

# Copy and fill in .env
cp .env.example .env
# Edit .env with your tokens

# For local dev, use ngrok for webhook
ngrok http 8000

# Set WEBHOOK_URL=https://xxxxx.ngrok.io in .env
python -m uvicorn bot.main:app --reload --port 8000
```

## Environment Variables

See `.env.example` for all required variables.

**Required:**
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `WEBHOOK_URL` — your Railway.app HTTPS URL
- `OPENAI_API_KEY` — from platform.openai.com
- `GOOGLE_SHEET_ID` — Google Sheet ID for leads
- `GOOGLE_CREDS_JSON` — Google service account JSON (stringified)

**Optional (escalation):**
- `SLACK_WEBHOOK_URL` — Slack incoming webhook
- `ESCALATION_EMAIL`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`

## Lead Capture

When a user expresses interest, the bot initiates a 3-step conversation:
1. Asks for name
2. Asks for email (validates format)
3. Asks for enquiry type (EV/Solar/Bundle/Maintenance/Other)

Saves to Google Sheet: `Timestamp | Name | Email | Enquiry Type | Chat ID | Source`

## Escalation

Triggered by:
1. User says "speak to a person" / "human agent" / similar
2. RAG confidence score < 0.40 (low-confidence response)
3. 3 consecutive failed intents

Alert sent via Slack webhook (primary) and email (secondary).

## Known Limitations

- ChromaDB is file-based; data persists across restarts but is not distributed
- Session storage is in-memory; sessions are lost on server restart
- WhatsApp integration requires Twilio or Meta business account setup (see bonus section)
- Knowledge base must be re-indexed if KB text is updated (delete `./chroma_db/` folder)

## WhatsApp Bonus (+20 pts)

To add WhatsApp via Twilio sandbox:
1. Sign up at twilio.com
2. Enable WhatsApp Sandbox (Messaging → Try it Out → WhatsApp)
3. Add the Twilio FastAPI handler (see `bot/whatsapp.py` — extend `main.py`)
4. Set ngrok/Railway URL as Twilio webhook

## Test the Bot

Telegram: Search for your bot by the username you set with @BotFather.

Test messages to send:
1. "Hello" → greeting response
2. "How much does a 7kW EV charger cost?" → pricing RAG
3. "What is TR25?" → regulatory FAQ
4. "I'm interested in solar panels" → lead capture flow
5. "Speak to a person" → escalation
6. "My charger is not working" → maintenance + possible escalation
