# StudyMate AI

StudyMate turns course files into a source-grounded tutor, adaptive quizzes, and a mastery dashboard.

## Features

- Upload PDF, PowerPoint, audio, and video course material, then organize sources by subject.
- Ask questions and explore concepts with answers grounded in retrieved passages and source citations.
- Generate simple explanations, detailed topic guides, and whole-source study overviews.
- Practice with adaptive quizzes, concept evaluations, and a subject mastery dashboard.
- Review citations that link back to a page, slide, or video timestamp.

## Requirements

- Python 3.10 or newer
- Node.js 20.19+ or 22.12+
- A Groq API key for AI explanations, chat, quizzes, and audio/video transcription

## Setup

Prerequisites: Python 3.10+, Node.js 20.19+ or 22.12+, and a Groq API key for chat, quizzes, and audio/video transcription.

1. Configure the backend:

   ```powershell
   cd backend
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

2. Set `GROQ_API_KEY` in `backend/.env`. Keep this file private and never commit it. The model names, JWT secret, and local data paths can also be overridden there.

3. Add PDF, PPTX, audio, or video files to `backend/sample_data/`, then seed the local database and vector store:

   ```powershell
   python seed.py
   ```

   Ready sources are skipped on later runs. Video/audio ingestion uses Groq transcription. If the folder has no supported files, the script prints a prompt and exits without error. The first seeded source may download the configured sentence-transformer model.

4. Start the API in a backend terminal:

   ```powershell
   uvicorn main:app --reload --port 8000
   ```

5. Start the web app in a second terminal:

   ```powershell
   cd frontend
   npm install
   npm run dev -- --host 127.0.0.1
   ```

6. Open <http://127.0.0.1:5173/>. The API is at <http://127.0.0.1:8000/> and its interactive docs are at <http://127.0.0.1:8000/docs>.

The backend allows the Vite origins `localhost:5173` and `127.0.0.1:5173`. SQLite, ChromaDB, and uploaded files are stored under `backend/` by default.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | Empty | Enables Groq-powered AI features. |
| `GROQ_CHAT_MODEL` | `openai/gpt-oss-20b` | Chat completion model. |
| `GROQ_WHISPER_MODEL` | `whisper-large-v3` | Audio/video transcription model. |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Local text embedding model. |
| `JWT_SECRET` | Development-only value | Set a long random secret outside local development. |
| `DATABASE_PATH` | `studymate.db` | SQLite database path. |
| `CHROMA_DIR` | `chroma_data` | ChromaDB vector-store directory. |
| `UPLOADS_DIR` | `uploads` | Uploaded source-file directory. |

On first use, the embedding model may be downloaded by SentenceTransformers. The backend also creates a built-in demo learner and sample source when it starts.

## Local Data and Secrets

The root `.gitignore` excludes backend `.env` files, virtual environments, SQLite databases, ChromaDB data, uploaded files, and generated frontend output. The example environment file and demo sample PDF are safe to keep in version control; replace all example secrets locally and do not add credentials to source files.

## Architecture

```text
+-------------------------+
| React + Vite            |
| Upload | Chat | Quiz    |
| Dashboard               |
+------------+------------+
             | HTTP JSON / multipart
             v
+-------------------------+        +---------------------+
| FastAPI                 |------->| Groq API            |
| ingestion, tutor, quiz  |        | chat + transcription|
+-----+-------------+-----+        +---------------------+
      |             |
      |             +----------------------+
      v                                    v
+-------------+                    +---------------------+
| SQLite      |                    | ChromaDB            |
| sources,    |                    | chunk vectors and   |
| mastery,    |                    | source metadata     |
| attempts    |                    +----------+----------+
+-------------+                               |
                                              v
                                  +-----------------------+
                                  | SentenceTransformers  |
                                  | local embeddings      |
                                  +-----------------------+
```

## Demo Flow

1. Put one or two lecture PDFs or slide decks in `backend/sample_data/` and run `python seed.py` from `backend/`.
2. Start both servers and show the seeded sources on the Upload page. You can also add a PDF, PPTX, or MP4 from the UI.
3. Open Chat and ask a question answered in the material; use a citation to jump back to its page, slide, or video segment.
4. Open Quiz, answer a generated question, and show the updated mastery on Dashboard.
5. For an audio/video demo, add a media file to `sample_data/` and configure the Groq API key before seeding.

Groq rate limits are retried once using the provider's `Retry-After` value when available. If the retry is also limited, StudyMate returns a message asking the learner to wait and try again.
