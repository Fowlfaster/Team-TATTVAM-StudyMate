# StudyMate AI Deployment Checklist

## Push to GitHub

From the project root:

```powershell
git add -A
git commit -m "Prepare StudyMate for deployment"
git push origin main
```

## Render Backend

1. In Render, create a **New Web Service** from the GitHub repository.
2. Set **Root Directory** to `backend`, **Runtime** to `Docker`, and **Instance Type** to **Starter**.
3. Add a persistent disk mounted at `/data` with **1 GB** storage.
4. Set **Health Check Path** to `/health`.
5. Add these environment variables (enter secrets in Render, never in Git):

```text
GROQ_API_KEY=<your Groq key>
JWT_SECRET=<a new long random value>
JWT_EXPIRE_MINUTES=1440
DATABASE_PATH=/data/studymate.db
UPLOADS_DIR=/data/uploads
CHROMA_DIR=/data/chroma_data
MODEL_CACHE_DIR=/data/model_cache
FRONTEND_ORIGINS=https://<your-vercel-app>.vercel.app,http://localhost:5173
```

The remaining settings use safe defaults: `GROQ_CHAT_MODEL`, `GROQ_WHISPER_MODEL`, `EMBEDDING_MODEL`, and `CHROMA_COLLECTION`.

## Vercel Frontend

1. Import the same GitHub repository into Vercel.
2. Set **Root Directory** to `frontend` and **Framework Preset** to **Vite**.
3. Add `VITE_API_URL=https://<your-render-service>.onrender.com` with no trailing slash.
4. Deploy.

After both deployments, update `FRONTEND_ORIGINS` on Render to include the real Vercel URL, then redeploy the backend.

## Smoke Test

Test signup, subject creation, PDF upload, Explain, and Quiz from the deployed Vercel app. Confirm the uploaded source finishes processing before trying Explain or Quiz.

## Troubleshooting

- **CORS errors:** Ensure `FRONTEND_ORIGINS` exactly matches the deployed Vercel origin, with no trailing slash, then redeploy Render.
- **404 after refreshing a frontend route:** Confirm `frontend/vercel.json` is deployed and the Vercel root directory is `frontend`.
- **Frontend still calls localhost:** Set the production `VITE_API_URL` to the Render URL without a trailing slash, then redeploy Vercel.
- **Render out of memory:** The embedding runtime and model loading need memory headroom. Check Starter plan usage and avoid concurrent large ingestions.
- **Slow first load:** FastEmbed downloads its model on the first run. The `/data/model_cache` directory persists it across deployments when the disk remains attached.
