# AI-Powered SOC Incident Response Copilot

A working GenAI-style SOC analyst prototype that turns raw security alerts and logs into structured incident analysis, severity scoring, IOC extraction, MITRE ATT&CK mapping, response recommendations, analyst reports, and incident chat.

## Project Structure

```text
backend/   FastAPI API for parsing and incident analysis
frontend/  React + Vite analyst dashboard
```

## Run Locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal.

## Optional LLM Integration

The backend currently uses a deterministic SOC analysis engine so the demo works without an API key. To add Gemini/OpenAI, replace or augment `backend/app/services/analyzer.py` with an LLM call that returns the same structured JSON shape as `IncidentAnalysis`.
