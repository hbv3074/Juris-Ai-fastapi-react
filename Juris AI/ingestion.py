import os
import re
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_path(path_value: str, default_path: str) -> str:
    """Resolve env paths relative to this file so cwd does not matter."""
    value = path_value.strip() if path_value else default_path
    return value if os.path.isabs(value) else os.path.normpath(os.path.join(BASE_DIR, value))


DATA_DIR = _resolve_path(os.getenv("LEGAL_DATA_DIR"), "LEGAL-DATA")
VECTOR_STORE_DIR = _resolve_path(os.getenv("VECTOR_STORE_DIR"), "my_vector_store")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))


def extract_section_hint(text: str) -> str:
    """Extract a lightweight section/chapter marker for downstream citation quality."""
    snippet = (text or "")[:600]

    # IPC/Act PDFs often use numeric headings like "299. Culpable homicide".
    numeric_heading = re.search(r"\b(\d{1,3}[A-Z]?)\.\s+[A-Za-z][^\n.]{2,80}", snippet)
    if numeric_heading:
        return f"Section {numeric_heading.group(1)}"

    patterns = [
        r"\bSection\s+\d+[A-Z]?\b",
        r"\bCHAPTER\s+[IVXLC0-9A-Z]+\b",
        r"\bPART\s+[IVXLC0-9A-Z]+\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, snippet, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return ""

def embed_and_save_documents():

    print("Initializing embeddings...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME
    )

    print("Loading PDFs...")
    print(f"Reading from: {DATA_DIR}")
    loader = PyPDFDirectoryLoader(DATA_DIR)
    docs = loader.load()

    print(f"Found {len(docs)} pages")

    if not docs:
        print("No documents found. Check folder path.")
        return

    print("Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\nCHAPTER ",
            "\nChapter ",
            "\nPART ",
            "\nPart ",
            "\nSECTION ",
            "\nSection ",
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ]
    )

    final_documents = text_splitter.split_documents(docs)
    print(f"Created {len(final_documents)} chunks")

    # Normalize and enrich metadata for better retrieval and citations.
    for chunk_index, doc in enumerate(final_documents):
        raw_source = doc.metadata.get("source", "")
        source_file = os.path.basename(raw_source) if raw_source else "unknown"

        page = doc.metadata.get("page")
        page_number = page + 1 if isinstance(page, int) else page

        doc.metadata["source_path"] = raw_source
        doc.metadata["source"] = source_file
        doc.metadata["source_file"] = source_file
        doc.metadata["page"] = page_number
        doc.metadata["chunk_id"] = chunk_index
        doc.metadata["doc_id"] = f"{source_file}:p{page_number}:c{chunk_index}"
        doc.metadata["section_hint"] = extract_section_hint(doc.page_content)

    print("Creating FAISS vector store...")
    vector_store = FAISS.from_documents(final_documents, embeddings)

    os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
    vector_store.save_local(VECTOR_STORE_DIR)

    print("Vectors saved successfully!")
    print("Ingestion complete.")

if __name__ == "__main__":
    embed_and_save_documents()