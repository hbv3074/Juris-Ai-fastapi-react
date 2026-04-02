# Local Showcase: FastAPI + React

This setup runs a local API and React UI for your final year project demo.

## 1) Backend (FastAPI)

From workspace root (`C:\Users\Harsh\Downloads\LegalAssistant`):

```powershell
.\legal_assistant\Scripts\Activate.ps1
cd .\Legal-CHATBOT-main\backend
pip install -r requirements.txt
python run.py
```

Backend starts on `http://127.0.0.1:8000`.

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

## 2) Frontend (React + Vite)

Open a second terminal:

```powershell
cd C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main\frontend
npm install
npm run dev
```

Frontend starts on `http://127.0.0.1:5173`.

## 3) Environment Variables

Backend reads env values from:

- `Legal-CHATBOT-main/.env` (preferred)
- fallback: workspace `.env`

Required for LLM calls:

- `GROQ_API_KEY` with `GROQ_MODEL_NAME`, or
- `XAI_API_KEY` with `XAI_MODEL_NAME`

## 4) Demo Flow

1. Open frontend URL.
2. Upload a legal PDF (session-scoped temporary index).
3. Ask questions; answers return citations (`source`, `page`, `section`).

## Notes

- Uploaded PDF chunks are kept in-memory per browser session id for demo use.
- Base corpus retrieval still uses `my_vector_store`.
- For production, move uploads to persistent storage and per-user vector namespaces.
