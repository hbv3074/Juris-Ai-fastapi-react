# ⚖️ Juris AI  
### *Intelligent Legal RAG Assistant*

**Juris AI** is a Retrieval-Augmented Generation (RAG) system designed to answer legal queries with **traceable, citation-backed responses**. It supports both a modern web interface and a lightweight prototype app.

---

## 🚀 Interfaces

- **FastAPI + React (Primary App)**
  - Backend: `backend/`
  - Frontend: `frontend/`
  - Full-featured dashboard experience

- **Streamlit (Prototype / Legacy)**
  - File: `app.py`
  - Quick testing and experimentation

---

## ✨ Core Features

- 🔍 **Hybrid Retrieval System**
  - Combines **BM25 (keyword search)** + **FAISS (vector search)**

- 📄 **Custom PDF Upload & Query**
  - Users can upload documents and query them instantly

- 🧠 **Session-Based Memory**
  - Maintains conversational context within sessions

- ⚡ **Multi-Provider LLM Support**
  - Compatible with:
    - **Groq**
    - **xAI (OpenAI-compatible endpoint)**

- 📌 **Citation-Aware Responses**
  - Structured metadata:
    - `source`
    - `page`
    - `section`

- 🖥️ **Interactive Dashboard UI**
  - Chat interface  
  - Document upload  
  - Confidence panel  
  - Citation viewer  
  - Retrieval debug panel  

- 🛡️ **Fallback Mechanism**
  - Handles API limits gracefully with extractive answers

---

## 📁 Project Structure

```text
Juris AI/
│
├── backend/
│   ├── app/main.py        # FastAPI API (/health, /upload, /chat)
│   ├── run.py             # Backend launcher
│   └── requirements.txt   # Minimal backend dependencies
│
├── frontend/
│   ├── src/               # React source code
│   ├── public/            # Static assets (logos/icons)
│   └── package.json
│
├── app.py                 # Streamlit app (prototype)
├── ingestion.py           # Corpus ingestion + FAISS index build
│
├── LEGAL-DATA/            # Base legal PDFs
├── my_vector_store/       # FAISS index storage
│
├── DEMO_RUNBOOK_WINDOWS.md
├── README_LOCAL_FASTAPI_REACT.md
└── requirements.txt       # Full Python dependency snapshot
```

---

## ⚙️ How It Works

1. Base legal corpus is embedded using `ingestion.py` and stored in `my_vector_store/`.
2. Backend loads **FAISS + BM25 retrievers**.
3. Users upload PDFs → backend:
   - Extracts text  
   - Splits into chunks  
   - Stores in session memory  
4. Queries are processed using a **conversational retrieval chain**.
5. Responses include **normalized citations**.
6. If API limits are hit → system falls back to **deterministic extractive answers**.

---

## 🛠️ Setup (Windows)

### 1. Python Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
```

---

### 2. Node Environment (Frontend)

Install Node.js (LTS), then:

```powershell
cd .\frontend
npm install
cd ..
```

---

### 3. Configure Environment Variables

Create `.env` in project root:

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

---

### 4. Run FastAPI + React (Recommended)

**Terminal 1 (Backend):**
```powershell
cd .\backend
python run.py
```

**Terminal 2 (Frontend):**
```powershell
cd .\frontend
npm run dev
```

Open: `http://127.0.0.1:5173`

---

### 5. Optional: Run Streamlit App

```powershell
streamlit run app.py
```

---

## 🔄 Rebuild Base Vector Store (Optional)

If you update files in `LEGAL-DATA/`:

```powershell
python ingestion.py
```

---

## 🚀 Key Enhancements

- Hybrid retrieval (BM25 + FAISS)
- Improved metadata for traceability
- Multi-provider LLM support (Groq / xAI)
- FastAPI-based upload pipeline
- Enhanced UI/UX with dashboard components
- Robust fallback handling for API limits

---

## ⚠️ Known Constraints

- Upload index is **in-memory (not persistent)**
- No authentication or multi-user isolation
- Not production-ready (requires:
  - Persistent storage  
  - User-level vector namespaces  
  - API authentication)

---

## 🧪 Troubleshooting

- **429 Rate Limit Error**
  - Wait for quota reset or switch provider

- **Import Errors**
  - Ensure correct Python venv is selected

- **PowerShell Frontend Issues**
```powershell
npm.cmd run dev
npm.cmd run build
```

---

## 📜 License / Usage Note

Ensure compliance with legal dataset licensing before public use.  
Replace or remove restricted datasets before deployment or sharing.

---

## 💡 Future Improvements

- Persistent vector database (e.g., Pinecone, Weaviate)
- User authentication & role-based access
- Multi-tenant architecture
- Deployment (Docker + Cloud)
- Fine-tuned legal LLM integration

---

### 👨‍💻 Built for scalable, explainable legal AI systems
