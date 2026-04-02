# Juris AI

Juris AI is a legal RAG assistant with two runnable interfaces:

- `backend/` + `frontend/`: FastAPI + React (Vite) local showcase app.
- `app.py`: Streamlit app (legacy/prototype path).

The system answers legal queries using retrieval-augmented generation over a base legal corpus and uploaded PDFs, with citations in responses.

## What This Project Includes

- Hybrid retrieval for base corpus: BM25 + FAISS vector retrieval.
- Upload and query flow for user PDFs in FastAPI.
- Session-scoped chat memory in backend API.
- Provider support for Groq and xAI (OpenAI-compatible endpoint).
- Citation normalization (`source`, `page`, `section`).
- Frontend dashboard UI with upload, chat, confidence panel, citations, and retrieval debug panel.

## Project Structure

```text
Juris AI/
    backend/
        app/main.py            # FastAPI API (/health, /upload, /chat)
        run.py                 # Backend launcher
        requirements.txt       # Minimal backend runtime deps
    frontend/
        src/                   # React UI source
        public/                # Logos/icons
        package.json
    app.py                   # Streamlit-based app
    ingestion.py             # Corpus ingestion and FAISS build
    LEGAL-DATA/              # Base legal PDFs
    my_vector_store/         # FAISS index for base corpus
    DEMO_RUNBOOK_WINDOWS.md
    README_LOCAL_FASTAPI_REACT.md
    requirements.txt         # Full Python dependency snapshot
```

## How It Works

1. Base corpus is embedded and stored in `my_vector_store/` using `ingestion.py`.
2. API loads FAISS + BM25 retrievers for the base corpus.
3. User can upload a PDF. Backend extracts text, chunks it, and adds it to in-memory upload docs for that session.
4. Query is answered through a conversational retrieval chain.
5. Response includes normalized citations for traceability.
6. If provider quota is hit (for example, rate limit), backend returns a deterministic extractive fallback from retrieved context.

## Setup (Windows)

## 1. Python Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Node Environment (Frontend)

Install Node.js LTS, then:

```powershell
cd .\frontend
npm install
cd ..
```

## 3. Configure Environment Variables

Create `.env` in project root (`Juris AI/.env`) with one provider option:

```env
# Option A: Groq
GROQ_API_KEY=gsk_xxx
GROQ_MODEL_NAME=llama-3.3-70b-versatile

# Option B: xAI
# XAI_API_KEY=xai-xxx
# XAI_MODEL_NAME=grok-2-latest

EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
VECTOR_STORE_DIR=./my_vector_store
LEGAL_DATA_DIR=./LEGAL-DATA
VECTOR_K=10
VECTOR_FETCH_K=20
BM25_K=10
UPLOAD_CHUNK_SIZE=1200
UPLOAD_CHUNK_OVERLAP=150
```

## 4. Run FastAPI + React (Recommended)

Terminal 1:

```powershell
cd .\backend
python run.py
```

Terminal 2:

```powershell
cd .\frontend
npm run dev
```

Open `http://127.0.0.1:5173`.

## 5. Optional: Run Streamlit App

```powershell
streamlit run app.py
```

## Rebuild Base Vector Store (Optional)

If you update files in `LEGAL-DATA/`, run:

```powershell
python ingestion.py
```

## Key Enhancements Implemented

- Migrated from basic vector-only flow to hybrid retrieval.
- Added richer metadata for chunk traceability.
- Added provider multiplexing (Groq/xAI).
- Added upload pipeline in local FastAPI demo.
- Added UI improvements and custom branding integration.
- Added fallback behavior for provider quota/rate limit scenarios.

## Known Demo Constraints

- Upload index is in-memory and session-scoped in backend (not persistent storage).
- No authentication/tenant isolation yet.
- For production, use persistent storage + per-user vector namespace + API auth.

## Troubleshooting

- `429 rate_limit_exceeded`: reduce usage, wait for quota reset, or switch provider/model.
- Import resolution warnings in editor: ensure selected Python interpreter is your project venv.
- Frontend command issues on PowerShell: use `npm.cmd run dev` / `npm.cmd run build`.

## License / Usage Note

Review legal dataset licensing before public redistribution. Replace or remove restricted data before publishing publicly.



