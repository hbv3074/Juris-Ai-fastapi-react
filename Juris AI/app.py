import streamlit as st
import os
import re
from typing import Any, List, Dict
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_community.retrievers import BM25Retriever
    from langchain.retrievers import EnsembleRetriever
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False

# ------------------ PAGE CONFIG ------------------
st.set_page_config(
    page_title="JurisAi",
    page_icon="⚖️",
    layout="centered"
)

# --- CSS BLOCK HERE ---
st.markdown("""
<style>
/* Improve main container spacing */
.block-container {
    padding-top: 3rem;
    padding-bottom: 2rem;
}

/* Title styling */
h2 {
    font-weight: 700;
    letter-spacing: 0.5px;
}

/* Subtitle refinement */
[data-testid="stCaption"] {
    font-size: 14px;
    opacity: 0.8;
}

/* Divider soft look */
hr {
    opacity: 0.2;
}

/* Input box polish */
textarea {
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# ------------------ HEADER ------------------
st.markdown("## ⚖️ JurisAi")
st.caption("AI-Powered Legal Information Retrieval System (RAG-Based Prototype)")

st.divider()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ------------------ LOAD ENV ------------------
# Prefer .env in this project folder; fallback to parent workspace .env.
dotenv_candidates = [
    os.path.join(BASE_DIR, ".env"),
    os.path.join(os.path.dirname(BASE_DIR), ".env"),
]

for env_path in dotenv_candidates:
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
        break

groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
xai_api_key = os.getenv("XAI_API_KEY", "").strip()
XAI_MODEL_NAME = os.getenv("XAI_MODEL_NAME", "").strip()
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile").strip()

# Backward compatibility: if user set GROQ_API_KEY to an xAI key, treat it as xAI.
if not xai_api_key and groq_api_key.startswith("xai"):
    xai_api_key = groq_api_key

if not groq_api_key and not xai_api_key:
    st.error(
        "No LLM API key found. Set GROQ_API_KEY (gsk_...) or XAI_API_KEY (xai...)."
    )
    st.stop()


def _resolve_path(path_value: str, default_path: str) -> str:
    value = path_value.strip() if path_value else default_path
    return value if os.path.isabs(value) else os.path.normpath(os.path.join(BASE_DIR, value))


VECTOR_STORE_DIR = _resolve_path(os.getenv("VECTOR_STORE_DIR"), "my_vector_store")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
VECTOR_K = int(os.getenv("VECTOR_K", "10"))
VECTOR_FETCH_K = int(os.getenv("VECTOR_FETCH_K", "20"))
BM25_K = int(os.getenv("BM25_K", "10"))
PRIVACY_REDACTION_ENABLED = os.getenv("PRIVACY_REDACTION_ENABLED", "true").lower() == "true"
SHOW_RETRIEVAL_DEBUG = os.getenv("SHOW_RETRIEVAL_DEBUG", "true").lower() == "true"
RETRIEVAL_MIN_SCORE = float(os.getenv("RETRIEVAL_MIN_SCORE", "2.2"))
SCORE_SOURCE_MATCH = float(os.getenv("SCORE_SOURCE_MATCH", "2.2"))
SCORE_PRIORITY_SECTION = float(os.getenv("SCORE_PRIORITY_SECTION", "2.0"))
SCORE_INTENT_PRIMARY = float(os.getenv("SCORE_INTENT_PRIMARY", "2.6"))
SCORE_INTENT_SECONDARY = float(os.getenv("SCORE_INTENT_SECONDARY", "1.0"))
SCORE_INTENT_AVOID = float(os.getenv("SCORE_INTENT_AVOID", "-1.6"))
SCORE_KEYWORD_STEP = float(os.getenv("SCORE_KEYWORD_STEP", "0.45"))
SCORE_KEYWORD_CAP = float(os.getenv("SCORE_KEYWORD_CAP", "2.0"))
HIGH_CONF_DOC_LIMIT = int(os.getenv("HIGH_CONF_DOC_LIMIT", "5"))
FALLBACK_DOC_LIMIT = int(os.getenv("FALLBACK_DOC_LIMIT", "4"))


def sanitize_query(text: str) -> tuple[str, bool]:
    """Redact common PII-like patterns before sending text to remote LLM APIs."""
    redacted = text
    patterns = [
        (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]"),
        (r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)", "[REDACTED_PHONE]"),
        (r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)", "[REDACTED_AADHAAR]"),
        (r"\b[A-Z]{5}\d{4}[A-Z]\b", "[REDACTED_PAN]"),
    ]

    changed = False
    for pattern, replacement in patterns:
        next_text = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
        if next_text != redacted:
            changed = True
            redacted = next_text

    return redacted, changed


def infer_priority_sources(query: str) -> List[str]:
    lowered = query.lower()
    source_rules = [
        (["ipc", "penal code", "murder", "homicide", "theft", "cheating", "criminal breach", "dishonestly", "movable property", "without consent"], "ipc_act.pdf"),
        (["companies act", "director", "board", "company law"], "CompaniesAct2013.pdf"),
        (["copyright", "infringement", "license", "author"], "CopyrightRules1957.pdf"),
        (["customs", "import", "export", "duty"], "customacta1962-52.pdf"),
        (["labour", "worker", "wage", "industrial", "employment"], "Labour Act.pdf"),
        (["constitution", "article", "fundamental rights", "coi"], "COI.pdf"),
        (["criminal law amendment", "2018", "pocso"], "CSdivTheCriminalLawAct_14082018_0.pdf"),
    ]

    prioritized = []
    for keywords, source in source_rules:
        if any(keyword in lowered for keyword in keywords):
            prioritized.append(source)
    return prioritized


def infer_priority_sections(query: str) -> List[str]:
    lowered = query.lower()
    rules = [
        (["culpable homicide", "murder"], ["299", "300", "304"]),
        (["theft", "dishonestly takes", "movable property"], ["378", "379", "382"]),
        (["criminal breach of trust"], ["405", "406"]),
        (["cheating"], ["415", "417", "420"]),
        (["copyright", "infringement", "penalt"], ["51", "63", "63A"]),
        (["director", "duties of directors", "section 166"], ["166"]),
    ]
    matches: List[str] = []
    for keywords, sections in rules:
        if any(keyword in lowered for keyword in keywords):
            matches.extend(sections)
    return list(dict.fromkeys(matches))


def infer_intent_profile(query: str) -> Dict[str, List[str]]:
    lowered = query.lower()
    if any(k in lowered for k in ["theft", "dishonestly", "movable property", "without consent"]):
        return {"primary": ["378", "379"], "secondary": ["380", "381", "382"], "avoid": ["403", "410", "216A", "216B"]}
    if any(k in lowered for k in ["culpable homicide", "murder"]):
        return {"primary": ["299", "300"], "secondary": ["302", "304"], "avoid": ["376E", "403"]}
    if "criminal breach of trust" in lowered:
        return {"primary": ["405", "406"], "secondary": ["407", "408", "409"], "avoid": ["415", "420"]}
    if "cheating" in lowered:
        return {"primary": ["415", "417", "420"], "secondary": ["418", "419"], "avoid": ["405", "406"]}
    return {"primary": [], "secondary": [], "avoid": []}


def query_keywords(query: str) -> List[str]:
    stopwords = {
        "what", "when", "where", "which", "under", "with", "from", "that", "this",
        "into", "about", "their", "there", "those", "these", "have", "has", "had",
        "does", "doing", "between", "explain", "difference", "according", "act", "law",
    }
    tokens = re.findall(r"[a-zA-Z]{4,}", query.lower())
    return [token for token in tokens if token not in stopwords]


def build_verified_citations(docs: List[Document], limit: int = 4) -> List[str]:
    lines = []
    seen = set()

    def _infer_section_from_content(text: str) -> str:
        match = re.search(r"\b(\d{1,3}[A-Z]?)\.\s*[A-Za-z]", text)
        return f"Section {match.group(1)}" if match else "NA"

    # Prefer high-confidence chunks for user-facing citations.
    ordered_docs = sorted(
        docs,
        key=lambda d: d.metadata.get("_retrieval_score", 0.0),
        reverse=True,
    )
    citation_docs = [d for d in ordered_docs if d.metadata.get("_retrieval_score", 0.0) >= RETRIEVAL_MIN_SCORE]
    if not citation_docs:
        citation_docs = ordered_docs[:2]

    for doc in citation_docs:
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "NA")
        section = doc.metadata.get("section_hint", "NA") or "NA"
        if section == "NA":
            section = _infer_section_from_content(doc.page_content)
        key = (source, page, section)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- [source={source}, page={page}, section={section}]")
        if len(lines) >= limit:
            break
    return lines


def strip_model_citation_blocks(text: str) -> str:
    cleaned = re.split(r"\n\s*Citations\s*:\s*", text, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.split(r"\n\s*Verified Citations\s*:\s*", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    return cleaned.strip()


def document_relevance_score(
    doc: Document,
    query: str,
    priority_sources: List[str],
    priority_sections: List[str],
) -> float:
    score = 0.0
    keywords = query_keywords(query)
    content = doc.page_content.lower()
    source = str(doc.metadata.get("source", "")).lower()
    section_hint = str(doc.metadata.get("section_hint", "")).lower()

    if priority_sources and source in [s.lower() for s in priority_sources]:
        score += SCORE_SOURCE_MATCH

    if priority_sections:
        for sec in priority_sections:
            sec_pattern = rf"\bsection\s*{re.escape(sec)}\b|\b{re.escape(sec)}\."
            if re.search(sec_pattern, section_hint, flags=re.IGNORECASE) or re.search(sec_pattern, content, flags=re.IGNORECASE):
                score += SCORE_PRIORITY_SECTION
                break

    intent = infer_intent_profile(query)
    lowered_query = query.lower()
    for sec in intent["primary"]:
        sec_pattern = rf"\bsection\s*{re.escape(sec)}\b|\b{re.escape(sec)}\."
        if re.search(sec_pattern, section_hint, flags=re.IGNORECASE) or re.search(sec_pattern, content, flags=re.IGNORECASE):
            score += SCORE_INTENT_PRIMARY
            break

    for sec in intent["secondary"]:
        sec_pattern = rf"\bsection\s*{re.escape(sec)}\b|\b{re.escape(sec)}\."
        if re.search(sec_pattern, section_hint, flags=re.IGNORECASE) or re.search(sec_pattern, content, flags=re.IGNORECASE):
            score += SCORE_INTENT_SECONDARY
            break

    for sec in intent["avoid"]:
        sec_pattern = rf"\bsection\s*{re.escape(sec)}\b|\b{re.escape(sec)}\."
        if re.search(sec_pattern, section_hint, flags=re.IGNORECASE) or re.search(sec_pattern, content, flags=re.IGNORECASE):
            score += SCORE_INTENT_AVOID
            break

    # Intent-specific lexical gating to reduce near-section drift in IPC queries.
    if any(k in lowered_query for k in ["theft", "dishonestly", "movable property", "without consent"]):
        has_theft_core = "theft" in content and ("dishonest" in content or "movable property" in content)
        if has_theft_core:
            score += 2.0
        else:
            score -= 2.0

    if any(k in lowered_query for k in ["culpable homicide", "murder"]):
        has_homicide_core = "culpable homicide" in content or "murder" in content
        if has_homicide_core:
            score += 1.6
        else:
            score -= 1.0

    if "criminal breach of trust" in lowered_query:
        has_cbot_core = "criminal breach of trust" in content or "entrust" in content
        if has_cbot_core:
            score += 1.4
        else:
            score -= 1.0

    if "cheating" in lowered_query:
        has_cheating_core = "cheating" in content or "deceiv" in content
        if has_cheating_core:
            score += 1.4
        else:
            score -= 1.0

    if keywords:
        overlap = sum(1 for kw in keywords if kw in content)
        score += min(SCORE_KEYWORD_CAP, overlap * SCORE_KEYWORD_STEP)

    return score


class SourceAwareRetriever(BaseRetriever):
    base_retriever: Any

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        docs = self.base_retriever.invoke(query)
        prioritized_sources = infer_priority_sources(query)
        prioritized_sections = infer_priority_sections(query)

        scored_docs: List[Document] = []
        for doc in docs:
            score = document_relevance_score(doc, query, prioritized_sources, prioritized_sections)
            doc.metadata["_retrieval_score"] = round(score, 3)
            scored_docs.append(doc)

        sorted_docs = sorted(scored_docs, key=lambda d: d.metadata.get("_retrieval_score", 0.0), reverse=True)
        high_conf_docs = [d for d in sorted_docs if d.metadata.get("_retrieval_score", 0.0) >= RETRIEVAL_MIN_SCORE]

        if high_conf_docs:
            return high_conf_docs[:HIGH_CONF_DOC_LIMIT]

        return sorted_docs[:FALLBACK_DOC_LIMIT]

# ------------------ SESSION STATE ------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferWindowMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="answer",
        k=2
    )

# ------------------ LOAD VECTOR STORE ------------------
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

if not os.path.exists(VECTOR_STORE_DIR):
    st.error(f"Vector store not found at: {VECTOR_STORE_DIR}")
    st.stop()

db = FAISS.load_local(
    VECTOR_STORE_DIR,
    embeddings,
    allow_dangerous_deserialization=True
)

vector_retriever = db.as_retriever(
    search_type="mmr",
    search_kwargs={"k": VECTOR_K, "fetch_k": VECTOR_FETCH_K}
)

if HYBRID_AVAILABLE:
    bm25_docs = list(db.docstore._dict.values())
    bm25_retriever = BM25Retriever.from_documents(bm25_docs)
    bm25_retriever.k = BM25_K

    base_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.4, 0.6]
    )
else:
    st.warning(
        "Hybrid retrieval disabled: install rank_bm25 to enable BM25 + vector mode. "
        "Running with vector retrieval only."
    )
    base_retriever = vector_retriever

retriever = SourceAwareRetriever(base_retriever=base_retriever)

# ------------------ PROMPT ------------------
prompt_template = """
You are a legal assistant. Answer strictly using the provided context.
If the answer is not found in the context, respond exactly with:
"The provided context does not contain sufficient information."

Output format rules (mandatory):
1) Start with "Answer:" followed by a concise legal answer.
2) Then add "Legal Basis:" with IPC/Act section references if present.
3) Then add "Citations:" and list 1-4 items in this exact format:
    - [source=<filename>, page=<page>, section=<section_hint_or_NA>]
4) Do not cite any source not present in context.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""

prompt = PromptTemplate(
    template=prompt_template,
    input_variables=["context", "question"]
)

# ------------------ LLM ------------------
if xai_api_key:
    if ChatOpenAI is None:
        st.error("xAI key detected but langchain-openai is not installed. Run: pip install langchain-openai")
        st.stop()

    if not XAI_MODEL_NAME:
        st.error(
            "XAI_MODEL_NAME is not set. Add a model you have access to in .env and restart. "
            "Example: XAI_MODEL_NAME=grok-3-mini"
        )
        st.stop()

    llm = ChatOpenAI(
        api_key=xai_api_key,
        base_url="https://api.x.ai/v1",
        model=XAI_MODEL_NAME
    )
elif groq_api_key:
    if ChatGroq is None:
        st.error("Groq key detected but langchain-groq is not installed. Run: pip install langchain-groq")
        st.stop()

    if not groq_api_key.startswith("gsk_"):
        st.error("GROQ_API_KEY format looks invalid. Groq keys should start with 'gsk_'.")
        st.stop()

    llm = ChatGroq(
        groq_api_key=groq_api_key,
        model_name=GROQ_MODEL_NAME
    )
else:
    st.error("Unable to initialize LLM provider from environment keys.")
    st.stop()

# ------------------ CHAIN ------------------
qa = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=retriever,
    memory=st.session_state.memory,
    combine_docs_chain_kwargs={"prompt": prompt},
    return_source_documents=True
)

# ------------------ DISPLAY CHAT ------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# ------------------ INPUT ------------------
user_input = st.chat_input("Enter your legal query...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    llm_question = user_input
    was_redacted = False
    if PRIVACY_REDACTION_ENABLED:
        llm_question, was_redacted = sanitize_query(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving statutory provisions..."):
            debug_sources = []
            try:
                result = qa.invoke({"question": llm_question})
                response = result["answer"]
                debug_sources = result.get("source_documents", [])
                top_score = max((doc.metadata.get("_retrieval_score", 0.0) for doc in debug_sources), default=0.0)

                if top_score < RETRIEVAL_MIN_SCORE:
                    response = "The provided context does not contain sufficient information."

                response = strip_model_citation_blocks(response)
                verified = build_verified_citations(debug_sources)
                if verified:
                    response = f"{response}\n\nCitations:\n" + "\n".join(verified)
            except Exception as exc:
                error_text = str(exc)
                if "Model not found" in error_text:
                    response = (
                        "Configured model was not found for your API key. "
                        "Update XAI_MODEL_NAME or GROQ_MODEL_NAME in .env to a model your account can access."
                    )
                else:
                    response = f"Request failed: {error_text}"

            if was_redacted:
                st.caption("Privacy filter applied: sensitive identifiers were redacted before LLM call.")
            st.write(response)

            if SHOW_RETRIEVAL_DEBUG:
                prioritized = infer_priority_sources(llm_question)
                with st.expander("Retrieval Debug", expanded=False):
                    st.write(f"Prioritized sources: {prioritized if prioritized else '[none]'}")
                    if not debug_sources:
                        st.write("No source documents returned.")
                    else:
                        for idx, doc in enumerate(debug_sources[:6], 1):
                            source = doc.metadata.get("source", "unknown")
                            page = doc.metadata.get("page", "NA")
                            section = doc.metadata.get("section_hint", "NA") or "NA"
                            score = doc.metadata.get("_retrieval_score", 0.0)
                            preview = " ".join(doc.page_content.split())[:220]
                            st.markdown(f"{idx}. `{source}` page `{page}` section `{section}` score `{score}`")
                            st.caption(preview)

    st.session_state.messages.append({"role": "assistant", "content": response})

# ------------------ FOOTER ------------------
st.divider()
st.caption("Developed as an academic prototype using Retrieval-Augmented Generation (RAG).")