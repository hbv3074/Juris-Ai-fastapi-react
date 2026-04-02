import io
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel
from pypdf import PdfReader

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

VECTOR_STORE_DIR = os.getenv("VECTOR_STORE_DIR", os.path.join(BASE_DIR, "my_vector_store"))
if not os.path.isabs(VECTOR_STORE_DIR):
    VECTOR_STORE_DIR = os.path.normpath(os.path.join(BASE_DIR, VECTOR_STORE_DIR))

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
VECTOR_K = int(os.getenv("VECTOR_K", "10"))
VECTOR_FETCH_K = int(os.getenv("VECTOR_FETCH_K", "20"))
BM25_K = int(os.getenv("BM25_K", "10"))
UPLOAD_CHUNK_SIZE = int(os.getenv("UPLOAD_CHUNK_SIZE", "1200"))
UPLOAD_CHUNK_OVERLAP = int(os.getenv("UPLOAD_CHUNK_OVERLAP", "150"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip()
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
XAI_MODEL_NAME = os.getenv("XAI_MODEL_NAME", "")

if not XAI_API_KEY and GROQ_API_KEY.startswith("xai"):
    XAI_API_KEY = GROQ_API_KEY


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    citations: List[Dict[str, Any]]
    session_id: str


app = FastAPI(title="JurisAI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
base_db = FAISS.load_local(
    VECTOR_STORE_DIR,
    embeddings,
    allow_dangerous_deserialization=True,
)
base_vector_retriever = base_db.as_retriever(
    search_type="mmr",
    search_kwargs={"k": VECTOR_K, "fetch_k": VECTOR_FETCH_K},
)
base_bm25 = BM25Retriever.from_documents(list(base_db.docstore._dict.values()))
base_bm25.k = BM25_K
base_retriever = EnsembleRetriever(
    retrievers=[base_bm25, base_vector_retriever],
    weights=[0.4, 0.6],
)

memory_by_session: Dict[str, ConversationBufferWindowMemory] = {}
upload_docs_by_session: Dict[str, List[Document]] = {}

prompt_template = """
You are a legal assistant. Use only the provided context.
If relevant text exists, provide the best possible answer grounded in that context.
Only say "The provided context does not contain sufficient information." when the context is clearly unrelated or empty for the question.

Output format:
Answer: <short legal answer>
Legal Basis: <sections/articles/acts from context>

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""
prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])


def get_llm():
    if XAI_API_KEY:
        if ChatOpenAI is None:
            raise RuntimeError("langchain-openai is not installed")
        if not XAI_MODEL_NAME:
            raise RuntimeError("XAI_MODEL_NAME is required when using XAI_API_KEY")
        return ChatOpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1", model=XAI_MODEL_NAME)

    if GROQ_API_KEY:
        if ChatGroq is None:
            raise RuntimeError("langchain-groq is not installed")
        if not GROQ_API_KEY.startswith("gsk_"):
            raise RuntimeError("GROQ_API_KEY must start with gsk_")
        return ChatGroq(groq_api_key=GROQ_API_KEY, model_name=GROQ_MODEL_NAME)

    raise RuntimeError("No LLM API key configured")


def build_retriever_for_session(session_id: str):
    upload_docs = upload_docs_by_session.get(session_id, [])
    if not upload_docs:
        return base_retriever

    upload_bm25 = BM25Retriever.from_documents(upload_docs)
    # Keep upload retrieval narrow to control prompt size and token cost.
    upload_bm25.k = min(4, max(2, len(upload_docs)))
    return EnsembleRetriever(
        retrievers=[upload_bm25, base_retriever],
        weights=[0.65, 0.35],
    )


def split_text_with_overlap(text: str, chunk_size: int, overlap: int) -> List[str]:
    if chunk_size <= 0:
        return [text]
    if overlap < 0:
        overlap = 0
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

    chunks: List[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(text_len, start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start = max(0, end - overlap)
    return chunks


def get_memory(session_id: str):
    if session_id not in memory_by_session:
        memory_by_session[session_id] = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer",
            k=2,
        )
    return memory_by_session[session_id]


def normalize_citations(docs: List[Document], limit: int = 4) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "NA")
        section = doc.metadata.get("section_hint") or "NA"
        if section == "NA":
            m = re.search(r"\b(\d{1,3}[A-Z]?)\.\s*[A-Za-z]", doc.page_content)
            if m:
                section = f"Section {m.group(1)}"
        key = (source, page, section)
        if key in seen:
            continue
        seen.add(key)
        out.append({"source": source, "page": page, "section": section})
        if len(out) >= limit:
            break
    return out


def build_extractive_fallback_answer(question: str, docs: List[Document]) -> str:
    if not docs:
        return "The provided context does not contain sufficient information."

    snippets: List[str] = []
    for doc in docs[:3]:
        text = " ".join((doc.page_content or "").split())
        if not text:
            continue
        # Keep fallback concise and deterministic for demo continuity.
        snippets.append(text[:260].rstrip())

    if not snippets:
        return "The provided context does not contain sufficient information."

    lines = [
        "Answer: Provider quota is temporarily exhausted, so this is an extractive answer from retrieved context.",
        "Legal Basis: Based on top retrieved passages from the uploaded/default corpus.",
    ]
    for idx, s in enumerate(snippets, start=1):
        lines.append(f"Context {idx}: {s}")
    lines.append(f"Question Focus: {question}")
    return "\n".join(lines)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 25MB")

    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unreadable PDF: {exc}")

    docs: List[Document] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = " ".join(text.split())
        if len(text) < 20:
            continue
        page_chunks = split_text_with_overlap(text, UPLOAD_CHUNK_SIZE, UPLOAD_CHUNK_OVERLAP)
        for chunk_id, chunk_text in enumerate(page_chunks, start=1):
            docs.append(
                Document(
                    page_content=chunk_text,
                    metadata={
                        "source": file.filename,
                        "page": idx,
                        "section_hint": "NA",
                        "uploaded": True,
                        "chunk_id": f"{idx}-{chunk_id}",
                    },
                )
            )

    if not docs:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")

    existing = upload_docs_by_session.get(session_id, [])
    upload_docs_by_session[session_id] = existing + docs

    return {
        "uploaded": True,
        "session_id": session_id,
        "filename": file.filename,
        "pages_indexed": len(docs),
        "total_uploaded_chunks": len(upload_docs_by_session[session_id]),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    session_id = req.session_id or str(uuid.uuid4())
    retriever = build_retriever_for_session(session_id)
    llm = get_llm()

    qa = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=get_memory(session_id),
        combine_docs_chain_kwargs={"prompt": prompt},
        return_source_documents=True,
    )

    source_documents: List[Document] = []
    try:
        result = qa.invoke({"question": question})
        answer = (result.get("answer") or "").strip()
        source_documents = result.get("source_documents", [])
    except Exception as exc:
        err_text = str(exc)
        err_lc = err_text.lower()

        if "rate limit" in err_lc or "429" in err_lc or "rate_limit_exceeded" in err_lc:
            # Keep demo usable even when provider quota is exhausted.
            source_documents = retriever.invoke(question)
            answer = build_extractive_fallback_answer(question, source_documents)
        else:
            raise HTTPException(status_code=500, detail=f"Chat generation failed: {err_text}")

    # Deterministic fallback: if retrieval produced no evidence, return a clear message.
    if not source_documents:
        answer = "The provided context does not contain sufficient information."

    return ChatResponse(
        answer=answer,
        citations=normalize_citations(source_documents),
        session_id=session_id,
    )
