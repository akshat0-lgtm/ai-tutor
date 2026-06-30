# 🚀 Deploy guide — Vercel (frontend) + Render (backend)

This walks you through deploying for **free**, step by step. No prior DevOps
knowledge assumed. Total time ≈ 15 minutes.

You'll deploy the **backend first** (so you have its URL), then the **frontend**,
then tell each one about the other.

---

## Before you start

You need three free accounts. Sign up with GitHub for the smoothest path:

1. **GitHub** — https://github.com (your code lives here)
2. **Render** — https://render.com (runs the Python backend)
3. **Vercel** — https://vercel.com (runs the Next.js frontend)

And your **Groq API key** from https://console.groq.com/keys (starts with `gsk_`).

Optional: a **Sarvam API key** from https://dashboard.sarvam.ai if you want Teach
mode's voice conversation feature ("talk to the tutor") live in production. Skip
it and the app still works fine in text-only mode.

### Push your code to GitHub

If you haven't already, from the project root (`ai-tutor/`):

```bash
git init
git add .
git commit -m "AI tutor MVP"
```

Then create a new empty repo on GitHub (the "+" → "New repository", don't add a
README), and run the two commands GitHub shows you, which look like:

```bash
git remote add origin https://github.com/YOUR_USERNAME/ai-tutor.git
git branch -M main
git push -u origin main
```

> ✅ Your `.env` file is already gitignored, so your Groq key will **not** be
> uploaded. You'll paste it into Render's dashboard instead.

---

## Part 1 — Backend on Render

1. Go to https://dashboard.render.com → **New +** → **Web Service**.
2. Click **Build and deploy from a Git repository** → **Connect** your GitHub and
   pick your `ai-tutor` repo.
3. Fill in the settings:
   - **Name**: `ai-tutor-backend` (or anything)
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: **Free**
4. Scroll to **Environment Variables** → **Add Environment Variable**:
   - Key: `GROQ_API_KEY` → Value: your `gsk_...` key
   - (Optional) Key: `SARVAM_API_KEY` → Value: your Sarvam key, for voice mode
   - (You'll add `CORS_ORIGINS` in Part 3, once you have the Vercel URL.)
5. Click **Create Web Service**. The first build takes a few minutes (it installs
   PyTorch — that's normal).
6. When it's live, copy the URL at the top, e.g.
   `https://ai-tutor-backend.onrender.com`.
7. Test it: open `https://ai-tutor-backend.onrender.com/api/health` in your
   browser. You want `{"status":"ok","groq_key_configured":true,"sarvam_key_configured":true}`
   (the last field will be `false` if you skipped Sarvam — that's fine).

> 💤 **Free tier sleeps.** After ~15 min idle, Render spins the service down. The
> next request wakes it and can take ~30–60s. That's expected on free tier.

---

## Part 2 — Frontend on Vercel

1. Go to https://vercel.com/new → **Import** your `ai-tutor` GitHub repo.
2. Vercel detects Next.js automatically. Set:
   - **Root Directory**: click **Edit** → choose `frontend`.
3. Expand **Environment Variables** and add:
   - Key: `NEXT_PUBLIC_API_URL`
   - Value: your Render URL from Part 1 (e.g.
     `https://ai-tutor-backend.onrender.com`) — **no trailing slash**.
4. Click **Deploy**. After a minute you'll get a URL like
   `https://ai-tutor.vercel.app`.

---

## Part 3 — Connect them (CORS)

The backend must allow your Vercel site to call it.

1. Back in **Render** → your service → **Environment** → add:
   - Key: `CORS_ORIGINS`
   - Value: your Vercel URL, e.g. `https://ai-tutor.vercel.app` (no trailing slash)
2. Save — Render redeploys automatically.

> The backend also auto-allows any `*.vercel.app` preview URL, so preview
> deployments work too. Setting `CORS_ORIGINS` pins your production domain.

---

## Part 4 — Try it

Open your Vercel URL, paste a YouTube link (one **with captions** is the fastest
first test), type what you want to learn, and click **Build my tutor**.

If the very first request is slow, that's the Render free tier waking up — give it
up to a minute and retry.

---

## Environment variables, summarized

| Where    | Variable              | Value                                            |
|----------|-----------------------|--------------------------------------------------|
| Render   | `GROQ_API_KEY`        | Your `gsk_...` key from console.groq.com/keys    |
| Render   | `SARVAM_API_KEY`      | (Optional) your key from dashboard.sarvam.ai — enables voice mode |
| Render   | `CORS_ORIGINS`        | Your Vercel URL, e.g. `https://ai-tutor.vercel.app` |
| Vercel   | `NEXT_PUBLIC_API_URL` | Your Render URL, e.g. `https://...onrender.com`  |

All free tier. Groq is the only required key; Sarvam is optional (voice mode).

---

## Troubleshooting

- **`groq_key_configured: false`** on `/api/health` → the key isn't set on Render.
  Re-check the `GROQ_API_KEY` env var spelling, then redeploy.
- **Frontend says "Could not reach the server"** → `NEXT_PUBLIC_API_URL` is wrong
  or has a trailing slash. Fix it in Vercel → Settings → Environment Variables →
  **Redeploy**.
- **Browser console shows a CORS error** → `CORS_ORIGINS` on Render doesn't match
  your exact Vercel URL. Match it exactly, no trailing slash.
- **"Error with the video, please try another video."** → that video has no usable
  captions (try the Whisper option) or YouTube is blocking the request from
  Render's datacenter IP. Try a different, well-known video; it always works
  locally if the cloud path is being blocked.
- **First request after idle is very slow** → Render free tier cold start. Normal.
- **"talk to the tutor" / voice mode doesn't work** → check `sarvam_key_configured`
  on `/api/health`. If `false`, add `SARVAM_API_KEY` on Render and redeploy. If
  `true`, it's likely a browser mic-permission prompt being dismissed — HTTPS
  (which Vercel/Render both give you by default) is required for microphone
  access, so this only matters if you've customized hosting.
