from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


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
