# JurisAI Demo Runbook (Windows)

Use this every time you start your laptop from scratch.

## 0) Preconditions

- Project root: `C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main`
- Python venv exists at: `C:\Users\Harsh\Downloads\LegalAssistant\legal_assistant`
- Node is installed at: `C:\Program Files\nodejs`
- `.env` is configured at: `C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main\.env`

Example provider section in `.env` (Groq):

```env
GROQ_API_KEY=your_real_key_here
GROQ_MODEL_NAME=llama-3.3-70b-versatile
XAI_API_KEY=
XAI_MODEL_NAME=
```

Important: no leading spaces before keys in `.env`.

---

## 1) Start Backend (Terminal A: Command Prompt)

Open **CMD** (not PowerShell) and run:

```cmd
C:\Users\Harsh\Downloads\LegalAssistant\legal_assistant\Scripts\activate.bat
cd C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main\backend
python run.py
```

Expected output includes:

- `Uvicorn running on http://127.0.0.1:8000`

Keep this terminal open.

---

## 2) Verify Backend Health (Terminal B: PowerShell)

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing
```

Expected response content should include:

```json
{"ok":true}
```

If this fails, backend is not running correctly.

---

## 3) Start Frontend (Terminal C: PowerShell)

```powershell
$env:Path += ";C:\Program Files\nodejs"
cd "C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main\frontend"
& "C:\Program Files\nodejs\npm.cmd" run dev
```

Expected output includes:

- `Local: http://127.0.0.1:5173/`

Keep this terminal open.

---

## 4) Open the App

Open browser at:

- `http://127.0.0.1:5173`

Do **not** open `frontend/dist/index.html` directly.

---

## 5) Showcase Flow

1. Ask one base legal question.
2. Upload one legal PDF from left panel.
3. Ask one question specific to uploaded PDF.
4. Show citations in the answer.
5. Show backend status pill as connected.

---

## 6) Common Problems and Fixes

### A) Frontend says `Error: Failed to fetch`

- Backend is down or API key missing.
- Check Terminal A for errors.
- Check health endpoint again.

### B) Backend error: `RuntimeError: No LLM API key configured`

- `.env` missing/wrong file/wrong format.
- Fix file: `C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main\.env`
- Ensure key lines have no indentation.
- Restart backend.

### C) `npm` not recognized in PowerShell

Use full path command:

```powershell
& "C:\Program Files\nodejs\npm.cmd" -v
```

### D) PowerShell script policy blocks venv activation

Use CMD for backend activation (recommended), or temporary bypass in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### E) White screen in browser

- Ensure frontend server is running.
- Open `http://127.0.0.1:5173` (not dist file).
- Hard refresh `Ctrl+F5`.

---

## 7) Stop Demo

- In each running terminal, press `Ctrl + C`.

---

## 8) One-Minute Quick Start (copy/paste)

### CMD (backend):

```cmd
C:\Users\Harsh\Downloads\LegalAssistant\legal_assistant\Scripts\activate.bat
cd C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main\backend
python run.py
```

### PowerShell (frontend):

```powershell
$env:Path += ";C:\Program Files\nodejs"
cd "C:\Users\Harsh\Downloads\LegalAssistant\Legal-CHATBOT-main\frontend"
& "C:\Program Files\nodejs\npm.cmd" run dev
```

Then open: `http://127.0.0.1:5173`
