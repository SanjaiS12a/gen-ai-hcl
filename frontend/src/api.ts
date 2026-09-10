import type { IncidentAnalysis } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export async function analyzeAlert(rawAlert: string): Promise<IncidentAnalysis> {
  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_alert: rawAlert }),
  });

  if (!response.ok) {
    throw new Error("Analysis failed. Check that the FastAPI server is running.");
  }

  return response.json();
}

export async function askIncident(incident: IncidentAnalysis, question: string): Promise<string> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident, question }),
  });

  if (!response.ok) {
    throw new Error("Incident chat failed.");
  }

  const data = await response.json();
  return data.answer;
}
