from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import AnalyzeRequest, ChatRequest, ChatResponse, IncidentAnalysis
from app.services.analyzer import analyze_alert, answer_incident_question

app = FastAPI(title="SOC Incident Response Copilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=IncidentAnalysis)
def analyze(request: AnalyzeRequest) -> IncidentAnalysis:
    return analyze_alert(request.raw_alert)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(answer=answer_incident_question(request.incident, request.question))
