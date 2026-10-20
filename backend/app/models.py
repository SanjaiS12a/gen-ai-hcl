from enum import Enum
from typing import Literal

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class Severity(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"
    critical = "CRITICAL"


class AnalyzeRequest(BaseModel):
    raw_alert: str = Field(..., min_length=5)


class ChatRequest(BaseModel):
    incident: "IncidentAnalysis"
    question: str = Field(..., min_length=3)


class Indicator(BaseModel):
    type: str
    value: str


class MitreTechnique(BaseModel):
    tactic: str
    technique_id: str
    technique: str


class EvidenceItem(BaseModel):
    label: str
    value: str


class IncidentAnalysis(BaseModel):
    id: str
    title: str
    incident_type: str
    severity: Severity
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    summary: str
    why_suspicious: list[str]
    root_cause: str
    extracted_iocs: list[Indicator]
    evidence: list[EvidenceItem]
    mitre_attack: list[MitreTechnique]
    recommended_actions: list[str]
    analyst_report: str
    raw_alert: str


class ChatResponse(BaseModel):
    answer: str


Status = Literal['New', 'In progress', 'Closed']


class IngestRequest(BaseModel):
    raw_alert: str = Field(min_length=5, max_length=20000)
    source: str = Field(default='Local webhook', min_length=1, max_length=150)
    timestamp: datetime | None = None


class Alert(BaseModel):
    id: int
    revision: str
    display_id: str
    title: str
    source: str
    origin: Literal['simulated feed', 'webhook']
    timestamp: str
    status: Status
    raw_alert: str
    baseline: IncidentAnalysis


class AlertPage(BaseModel):
    items: list[Alert]
    total: int
    page: int
    page_size: int


class StatusRequest(BaseModel):
    status: Status


class NotesRequest(BaseModel):
    text: str = Field(max_length=20000)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    rules_only: bool = False


class FalsePositive(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    likelihood: Literal['LOW', 'MEDIUM', 'HIGH']
    reason: str = Field(min_length=1, max_length=400)


class Narrative(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    summary: str = Field(min_length=1, max_length=1600)
    why_it_matters: str = Field(min_length=1, max_length=1200)
    verify_first: list[str] = Field(min_length=1, max_length=8)
    next_steps: list[str] = Field(min_length=1, max_length=8)
    false_positive_likelihood: FalsePositive | None = None


class CopilotResult(Narrative):
    engine: Literal['llm', 'rules']
    provider: str
    model: str
    generation_ms: int
    fallback_reason: str | None = None
    context_truncated: bool = False
    cached: bool = False


class ScopedChatResponse(BaseModel):
    answer: str
    engine: Literal['llm', 'rules']
    provider: str
    model: str
    generation_ms: int
    fallback_reason: str | None = None
