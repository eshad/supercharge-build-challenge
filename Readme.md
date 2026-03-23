  What I've Built

  54 files across all three challenges:

  ┌────────────────────────────┬────────────────────────────────────────────────────────┐
  │         Challenge          │                         Status                         │
  ├────────────────────────────┼────────────────────────────────────────────────────────┤
  │ 1 — Telegram RAG Chatbot   │ Complete — bot, RAG pipeline, lead capture, escalation │
  ├────────────────────────────┼────────────────────────────────────────────────────────┤
  │ 2 — Smart Energy Dashboard │ Complete — FastAPI backend + React frontend            │
  ├────────────────────────────┼────────────────────────────────────────────────────────┤
  │ 3 — AGV Brain Proposal     │ Complete — full engineering document + BOM             │
  └────────────────────────────┴────────────────────────────────────────────────────────┘

  ---
  Your Action Steps (in order)

  Step 1 — Get API Keys (30 min)

  1. Telegram bot token — Message @BotFather on Telegram → /newbot
  2. OpenAI API key — platform.openai.com → Create key
  3. Google Sheets (lead capture):
    - Create a blank Google Sheet at sheets.google.com, copy the Sheet ID from the URL
    - Go to console.cloud.google.com → Create Service Account → download JSON key
    - Share the sheet with the service account email
  4. Slack webhook (escalation) — api.slack.com/apps → Create App → Incoming Webhooks

  Step 2 — Create a GitHub repo and push code (10 min)

  cd /Volumes/MyExternal/personal/assesments/SuperCharge
  git init
  git add .
  git commit -m "SuperCharge SG Build Challenge — all three challenges"
  # Create a new repo on github.com, then:
  git remote add origin https://github.com/YOUR_USERNAME/supercharge-build-challenge.git
  git push -u origin main

  Step 3 — Deploy Challenge 1 (Telegram Bot) to Railway.app (20 min)

  1. Go to railway.app → New Project → Deploy from GitHub repo
  2. Select challenge1/ as the root directory
  3. Add these environment variables in Railway dashboard:
    - TELEGRAM_BOT_TOKEN = your bot token
    - WEBHOOK_URL = https://YOUR-APP.railway.app (Railway gives you this URL)
    - OPENAI_API_KEY = your key
    - GOOGLE_SHEET_ID = your sheet ID
    - GOOGLE_CREDS_JSON = paste the entire JSON file content as a string
    - SLACK_WEBHOOK_URL = your Slack webhook
  4. Deploy. Once live, send "hello" to your bot on Telegram.

  Step 4 — Deploy Challenge 2 (Dashboard) to Railway.app (20 min)

  1. Deploy backend from challenge2/backend/ — same Railway process
  2. Set env vars: OPENAI_API_KEY, SECRET_KEY=any-long-random-string
  3. For frontend: deploy from challenge2/frontend/ — set VITE_API_URL to backend Railway URL
  4. Test login with Client A: admin@greenfield-condo.sg / SuperCharge@ClientA

  Step 5 — Convert Challenge 3 to PDF (10 min)

  # Install pandoc if not already installed
  brew install pandoc

  cd /Volumes/MyExternal/personal/assesments/SuperCharge/challenge3
  pandoc AGV_Brain_Proposal.md -o AGV_Brain_Proposal.pdf --pdf-engine=wkhtmltopdf
  Or paste the markdown into a Google Doc and export as PDF.

  Step 6 — Record Loom Videos (30 min each)

  - Challenge 1: Show bot handling at least 3 intents live — FAQ, lead capture, escalation
  - Challenge 2: Show multi-tenant login, live data updating, fault injection triggering anomaly, PDF download

  Step 7 — Submit to support@supercharge.sg

  Send an email with:
  - Challenge 1: Telegram bot link + GitHub repo + Google Sheet link + escalation screenshot + Loom
  - Challenge 2: Live dashboard URL + both client credentials + forwarded weekly digest email + sample PDF + Loom
  - Challenge 3: PDF proposal + BOM CSV file

  Deadline: 25 March 2026 (12 days from now). Submit before 20 March for +5 bonus points.
