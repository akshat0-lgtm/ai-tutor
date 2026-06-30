# 🎓 AI Office Hours / Tutor

Paste a YouTube link → the app fetches/transcribes it, builds a RAG knowledge
base from the transcript, and then either **teaches** you the material topic by
topic or **quizzes** you on it. Text-only MVP.

Everything runs on **free tiers**: Groq for the LLM + Whisper, local
`all-MiniLM-L6-v2` embeddings, an in-memory vector store, and YouTube captions.

```
ai-tutor/
├── backend/     FastAPI — transcript, chunking, embeddings, vector store, all LLM calls
└── frontend/    Next.js — landing → processing → mode select → teach / quiz + chat
```

## How it works (the pipeline)

1. **Transcript** — `youtube-transcript-api` for existing captions, or `yt-dlp`
   pulls the audio and **Groq Whisper** transcribes it. You choose which on the
   landing page so you can compare quality.
2. **Chunking** — timestamp-aware, ~200–400 words per chunk at sentence boundaries.
3. **Embeddings** — every chunk embedded locally with `all-MiniLM-L6-v2` into an
   in-memory vector store (cosine similarity search).
4. **Topics** — one Groq call over the transcript + your learning goal extracts an
   ordered topic list (`topic_name`, `start_ts`, `end_ts`, `one_line_description`).
5. **Teach / Quiz** — both run on RAG over those chunks. The chat box answers
   strictly from the video when it can, and **clearly labels** when it falls back
   to general knowledge (📚 From the video vs 🌐 General knowledge).

---

## Run it locally

You need **Python 3.11+** and **Node 18+**. You'll run two terminals.

### 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt     # first install downloads torch — give it a few minutes

cp .env.example .env                # then edit .env and paste your Groq key
```

Get a free key at **https://console.groq.com/keys** and put it in `backend/.env`:

```
GROQ_API_KEY=gsk_your_real_key_here
```

Start the server:

```bash
uvicorn app.main:app --reload --port 8000
```

Check it: open http://localhost:8000/api/health — you should see
`{"status":"ok","groq_key_configured":true}`.

> The first request that needs embeddings downloads the ~80MB MiniLM model once.

### 2. Frontend (Next.js)

In a second terminal:

```bash
cd frontend
npm install
cp .env.local.example .env.local    # default points at http://localhost:8000
npm run dev
```

Open **http://localhost:3000**, paste a YouTube URL (one with captions is the
quickest first test), type what you want to learn, and go.

---

## Deploying (Vercel + Render)

See **[DEPLOY.md](DEPLOY.md)** for a click-by-click guide (≈15 minutes, all free tier).

---

## Notes & known limits

- **One session = one video.** No auth, no database; sessions live in memory and
  reset if the backend restarts (per spec).
- **Whisper path** has a ~24MB audio limit on the free tier — use captions for
  long videos.
- **Cloud IP blocking:** YouTube sometimes blocks caption/`yt-dlp` requests from
  datacenter IPs. It always works locally; on Render it can be intermittent.
- Any transcript/pipeline failure shows a single friendly message —
  *"Error with the video, please try another video."* — never a stack trace.

## Deliberately deferred (not built, not blocked)

Voice input (STT) and spoken responses (TTS), multilingual support, adaptive
quiz difficulty, and cross-session persistence.
