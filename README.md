# JurisAI - Developer Handover Guide

> An AI-powered legal RAG (Retrieval-Augmented Generation) assistant that answers legal queries with citation-backed responses.

---

## What This Project Does

JurisAI lets users ask legal questions in natural language and get answers grounded in actual legal documents. Every answer comes with citations (source file, page number, section) so nothing is made up out of thin air. Users can also upload their own PDFs and query them on top of the pre-built legal corpus.

There are two interfaces:

- **Primary:** FastAPI backend + React frontend (full dashboard)
- **Legacy/Prototype:** Streamlit app (`app.py`) for quick testing

---

## Project Structure

```
Juris AI/
│
├── backend/
│   ├── app/main.py        # All backend logic: API routes, retrieval, LLM calls
│   ├── run.py             # Starts the FastAPI server
│   └── requirements.txt
│
├── frontend/
│   ├── src/App.jsx        # Entire React UI (single-file component)
│   ├── public/            # Logo and icon assets
│   └── package.json
│
├── app.py                 # Streamlit prototype (not the main app)
├── ingestion.py           # One-time script to build the FAISS vector index
│
├── LEGAL-DATA/            # Base legal PDFs (the "corpus")
├── my_vector_store/       # Pre-built FAISS index (do NOT delete this)
│
└── .env                   # API keys and config (you must create this)
```

---

## How the System Works (End to End)

Understanding this flow is the most important thing before touching any code.

### Step 1: Corpus Ingestion (One-Time Setup)

`ingestion.py` reads all PDFs from `LEGAL-DATA/`, splits them into text chunks, converts each chunk into a vector embedding using the `all-MiniLM-L6-v2` model from HuggingFace, and saves the resulting FAISS index to `my_vector_store/`.

You only run this once, or again if you add new PDFs to `LEGAL-DATA/`.

```
LEGAL-DATA/ PDFs --> ingestion.py --> my_vector_store/ (FAISS index)
```

### Step 2: Backend Startup

When `backend/run.py` starts, `main.py` does the following:

1. Loads the pre-built FAISS index from `my_vector_store/`
2. Builds two retrievers from it:
   - **BM25 retriever** - keyword-based search (good for exact legal terms)
   - **FAISS retriever** - semantic/vector search (good for meaning-based queries)
3. Combines them into a single **EnsembleRetriever** (60% FAISS, 40% BM25) called `base_retriever`
4. Exposes three HTTP endpoints: `/health`, `/upload`, `/chat`

### Step 3: User Sends a Question

The React frontend sends a POST request to `/chat` with the user's question and their `session_id`.

Inside `/chat`, the backend:

1. Looks up or creates a **ConversationBufferWindowMemory** for that session (keeps the last 2 exchanges for context)
2. Checks if the session has any uploaded documents - if yes, builds a combined retriever that weights uploads at 65% and the base corpus at 35%
3. Runs a **ConversationalRetrievalChain** which:
   - Retrieves the top relevant chunks using the retriever
   - Passes those chunks + the question into the LLM with the system prompt
   - Gets back an answer with a "Legal Basis" section
4. Extracts citations from the source documents and returns them alongside the answer

### Step 4: PDF Upload

When a user uploads a PDF via the frontend:

1. The `/upload` endpoint receives the file
2. `pypdf` extracts the text page by page
3. The text is split into overlapping chunks (default: 1200 chars with 150 char overlap)
4. These chunks are stored **in memory** under the session ID (not persisted to disk)
5. On the next question, the session's upload chunks are mixed into retrieval

**Important:** Upload memory is lost when the server restarts. This is a known limitation (see the Known Constraints section below).

### Step 5: LLM Integration

The backend supports two LLM providers, selected based on which API key is present in `.env`:

- **Groq** (`GROQ_API_KEY` starting with `gsk_`) - uses `langchain_groq.ChatGroq`
- **xAI** (`XAI_API_KEY`) - uses `langchain_openai.ChatOpenAI` pointed at `https://api.x.ai/v1`

The `get_llm()` function in `main.py` checks for these at call time. If neither key is configured, it raises a `RuntimeError`.

### Step 6: Fallback Handling

If the LLM provider returns a 429 (rate limit exceeded), the backend does NOT crash. Instead it:

1. Directly invokes the retriever to get the top document chunks
2. Assembles a plain extractive answer from those chunks (no LLM involved)
3. Returns it to the user with a note that it is extractive

This keeps the demo usable even when the API quota runs out.

---

## The Two Retrieval Modes Explained

### Base Retrieval (no uploads)

```
User question
    --> BM25 retriever (top 10 chunks by keyword match)  --\
    --> FAISS MMR retriever (top 10 chunks by semantic)  ----> EnsembleRetriever (40/60 mix)
                                                               --> Top chunks passed to LLM
```

### Session Retrieval (with uploads)

```
User question
    --> Upload BM25 (top 2-4 chunks from uploaded PDFs)  --\
    --> base_retriever (the combined one above)           ----> EnsembleRetriever (65/35 mix)
                                                               --> Top chunks passed to LLM
```

The uploaded documents get higher weight (65%) because they are specifically what the user wants to query. The base corpus provides fallback coverage.

---

## The LLM Prompt

The system prompt that shapes every answer is defined as `prompt_template` in `main.py`. It tells the model:

- Only use the provided context (no hallucination from training data)
- Format the answer as: `Answer: ...` followed by `Legal Basis: ...`
- Only say "insufficient information" if the context is genuinely irrelevant

If you want to change the answer format or behavior, this is the only place to edit.

---

## React Frontend Architecture

The entire frontend is a single file: `frontend/src/App.jsx`.

It is structured as one default-exported `App` component with several inner components defined inside it:

- `Header` - top bar with backend status indicator and session ID
- `LeftSidebar` - PDF upload area, source filter (All/Base/My Documents), and document list
- `ChatArea` - the chat thread with message bubbles, citations, and the input box
- `RightPanel` - confidence score, top citations, domain tags, and a debug panel

State is managed at the top level (`App`) and passed down to inner components via closures. There is no Redux or external state library.

**Session persistence:** The session ID is generated once and stored in `localStorage` so it survives page refreshes. If localStorage is unavailable, it falls back to an in-memory ID.

**Backend health check:** The frontend pings `/health` every 5 seconds and shows a coloured status indicator (Connected / Disconnected).

**Citations:** After each assistant response, the frontend renders a citation grid directly under the message bubble, plus a summary in the right panel. The confidence score is a heuristic calculated from the number of citations that have a non-null section field.

---

## Setup Instructions

### 1. Python Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Node Environment

Install Node.js (LTS) from nodejs.org, then:

```powershell
cd .\frontend
npm install
cd ..
```

### 3. Create the `.env` File

Create `.env` in the project root:

```env
# Use one of these - Groq is recommended for testing

GROQ_API_KEY=gsk_xxx
GROQ_MODEL_NAME=llama-3.3-70b-versatile

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

### 4. Run the App

Terminal 1 (Backend):
```powershell
cd .\backend
python run.py
```

Terminal 2 (Frontend):
```powershell
cd .\frontend
npm run dev
```

Open: `http://127.0.0.1:5173`

### 5. Rebuild the Vector Store (Only If You Add New Legal PDFs)

```powershell
python ingestion.py
```

---

## Configuration Reference

All tunable values live in `.env` and are loaded at the top of `main.py`.

| Variable | Default | What It Controls |
|---|---|---|
| `VECTOR_K` | 10 | How many chunks the FAISS retriever returns per query |
| `VECTOR_FETCH_K` | 20 | Candidates considered before MMR re-ranking (must be >= VECTOR_K) |
| `BM25_K` | 10 | How many chunks the BM25 retriever returns per query |
| `UPLOAD_CHUNK_SIZE` | 1200 | Character length of each chunk from uploaded PDFs |
| `UPLOAD_CHUNK_OVERLAP` | 150 | Overlap between consecutive chunks (helps preserve context at chunk boundaries) |
| `EMBEDDING_MODEL_NAME` | all-MiniLM-L6-v2 | HuggingFace model used for embeddings |
| `VECTOR_STORE_DIR` | ./my_vector_store | Where the FAISS index is stored/loaded from |

---

## Known Constraints

These are not bugs - they are design limitations you should understand before extending the project.

**In-memory uploads:** Uploaded PDF chunks are stored in a Python dictionary (`upload_docs_by_session`) keyed by session ID. They vanish when the backend process restarts. To fix this, you would need to persist chunks to a vector database (Pinecone, Weaviate, etc.) or at least to disk.

**No authentication:** Any user can call `/chat` or `/upload` with any session ID. There is no login, token validation, or per-user isolation at the API level.

**No multi-user vector separation:** If two users happen to use the same session ID, their uploaded documents get merged. In practice this is unlikely due to UUID-based session generation, but it is not enforced.

**Single-process memory:** The session memory (`memory_by_session`) and upload store (`upload_docs_by_session`) live in the FastAPI process. Horizontal scaling would break session continuity.

---

## Troubleshooting

**429 Rate Limit Error from LLM**
The API quota for your Groq or xAI key is exhausted. The app will automatically fall back to extractive answers. Wait for the quota to reset or switch providers in `.env`.

**`RuntimeError: No LLM API key configured`**
The `.env` file is missing or the key format is wrong. Groq keys must start with `gsk_`. Check that `load_dotenv` is finding the right file (it searches from the project root).

**`FAISS load failed` or similar on backend start**
The `my_vector_store/` directory is missing or corrupted. Run `python ingestion.py` to rebuild it.

**Frontend shows "Disconnected"**
The backend is not running, or it is running on a different port. Check that `python run.py` started successfully and is listening on port 8000.

**PowerShell npm issues**
```powershell
npm.cmd run dev
npm.cmd run build
```

**`ModuleNotFoundError` on backend start**
Make sure your `.venv` is activated. The imports `langchain_groq` and `langchain_openai` are optional - the backend catches their absence and raises a clear error only when the relevant provider is actually used.

---

## Areas for Future Improvement

- Persistent vector storage (Pinecone, Weaviate, or pgvector) so uploads survive restarts
- User authentication and proper session isolation
- Docker Compose setup to run backend + frontend together
- Fine-tuned legal LLM for better domain accuracy
- Streaming responses so answers appear token by token instead of all at once
- Section-level metadata extraction during ingestion for more precise citations
