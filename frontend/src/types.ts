export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type Indicator = {
  type: string;
  value: string;
};

export type EvidenceItem = {
  label: string;
  value: string;
};

export type MitreTechnique = {
  tactic: string;
  technique_id: string;
  technique: string;
};

export type IncidentAnalysis = {
  id: string;
  title: string;
  incident_type: string;
  severity: Severity;
  confidence: "LOW" | "MEDIUM" | "HIGH";
  summary: string;
  why_suspicious: string[];
  root_cause: string;
  extracted_iocs: Indicator[];
  evidence: EvidenceItem[];
  mitre_attack: MitreTechnique[];
  recommended_actions: string[];
  analyst_report: string;
  raw_alert: string;
};

export type Status = "New" | "In progress" | "Closed";
export type Alert = {
  id: number;
  revision: string;
  display_id: string;
  title: string;
  source: string;
  origin: "simulated feed" | "webhook";
  timestamp: string;
  status: Status;
  raw_alert: string;
  baseline: IncidentAnalysis;
};
export type AlertPage = {
  items: Alert[];
  total: number;
  page: number;
  page_size: number;
};
export type Health = {
  status: string;
  provider: string;
  model: string;
  model_status: "not_loaded" | "loading" | "ready" | "error";
  model_error?: string | null;
  generation_progress?: {phase:string;input_tokens:number;generated_tokens:number} | null;
};
export type Provenance = {
  engine: "llm" | "rules";
  provider: string;
  model: string;
  generation_ms: number;
  fallback_reason: string | null;
};
export type CopilotResult = Provenance & {
  summary: string;
  why_it_matters: string;
  verify_first: string[];
  next_steps: string[];
  false_positive_likelihood: {
    likelihood: "LOW" | "MEDIUM" | "HIGH";
    reason: string;
  } | null;
  context_truncated: boolean;
  cached: boolean;
};
export type ChatResponse = Provenance & { answer: string };
export type Message = {
  id: number;
  alert_id: number;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  metadata: Partial<Provenance>;
};
export type Stats = {
  open_count: number;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  over_time: { time: string; count: number }[];
};
export type HistoryData = {
  closed: AlertPage;
  changes: {
    id: number;
    alert_id: number;
    old_status: Status;
    new_status: Status;
    timestamp: string;
  }[];
  changes_total: number;
};
