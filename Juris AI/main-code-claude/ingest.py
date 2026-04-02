import os
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

def embed_and_save_documents():
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    loader = PyPDFDirectoryLoader(r"C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main\LEGAL-DATA")
    print("Loader initialised")
    docs = loader.load()
    print(f"Found {len(docs)} pages")

    if not docs:
        print("ERROR: No documents found!")
        exit()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    final_documents = text_splitter.split_documents(docs)
    print(f"Split into {len(final_documents)} chunks")

    for doc in final_documents:
        if 'source' in doc.metadata:
            doc.metadata['source'] = os.path.basename(doc.metadata['source'])

    batch_size = 100
    batched_documents = [final_documents[i:i + batch_size] for i in range(0, len(final_documents), batch_size)]
    vector_stores = []
    for i, batch in enumerate(batched_documents):
        print(f"Embedding batch {i+1}/{len(batched_documents)}...")
        vector_store = FAISS.from_documents(batch, embeddings)
        vector_stores.append(vector_store)

    vectors = vector_stores[0]
    for vector_store in vector_stores[1:]:
        vectors.merge_from(vector_store)
    print("Merged the vectors")

    vectors.save_local(r"C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main\my_vector_store")
    print("Vectors saved successfully!")

embed_and_save_documents()