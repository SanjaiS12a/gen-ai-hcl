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
