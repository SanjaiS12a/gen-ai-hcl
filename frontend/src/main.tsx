import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  Bot,
  ClipboardList,
  FileText,
  MessageSquare,
  RadioTower,
  Search,
  ShieldAlert,
} from "lucide-react";

import { analyzeAlert, askIncident } from "./api";
import { sampleAlerts } from "./samples";
import type { IncidentAnalysis, Severity } from "./types";
import "./styles.css";

const severityClass: Record<Severity, string> = {
  LOW: "severity low",
  MEDIUM: "severity medium",
  HIGH: "severity high",
  CRITICAL: "severity critical",
};

function App() {
  const [rawAlert, setRawAlert] = useState(sampleAlerts[0].value);
  const [incident, setIncident] = useState<IncidentAnalysis | null>(null);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<{ role: "analyst" | "copilot"; text: string }[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isChatting, setIsChatting] = useState(false);
  const [error, setError] = useState("");

  async function handleAnalyze() {
    setError("");
    setIsAnalyzing(true);
    try {
      const result = await analyzeAlert(rawAlert);
      setIncident(result);
      setMessages([
        {
          role: "copilot",
          text: `I classified this as ${result.incident_type} with ${result.severity} severity. Ask me what to verify, contain, or report next.`,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected analysis error.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleAsk() {
    if (!incident || !question.trim()) return;
    const nextQuestion = question.trim();
    setQuestion("");
    setMessages((current) => [...current, { role: "analyst", text: nextQuestion }]);
    setIsChatting(true);
    try {
      const answer = await askIncident(incident, nextQuestion);
      setMessages((current) => [...current, { role: "copilot", text: answer }]);
    } catch (err) {
      setMessages((current) => [
        ...current,
        { role: "copilot", text: err instanceof Error ? err.message : "I could not answer that." },
      ]);
    } finally {
      setIsChatting(false);
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <ShieldAlert size={24} />
          <div>
            <h1>SOC Copilot</h1>
            <span>Incident response assistant</span>
          </div>
        </div>

        <nav className="nav">
          <button className="nav-item active" title="Analyze alerts">
            <Search size={18} />
            <span>Analyze</span>
          </button>
          <button className="nav-item" title="Review incident report">
            <FileText size={18} />
            <span>Report</span>
          </button>
          <button className="nav-item" title="Chat with incident">
            <MessageSquare size={18} />
            <span>Chat</span>
          </button>
        </nav>

        <section className="sample-list">
          <h2>Sample incidents</h2>
          {sampleAlerts.map((sample) => (
            <button key={sample.label} onClick={() => setRawAlert(sample.value)}>
              {sample.label}
            </button>
          ))}
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">AI-powered security operations</p>
            <h2>Incident Analysis Dashboard</h2>
          </div>
          <button className="primary" onClick={handleAnalyze} disabled={isAnalyzing}>
            <Bot size={18} />
            <span>{isAnalyzing ? "Analyzing..." : "Analyze Alert"}</span>
          </button>
        </header>

        {error && <div className="error">{error}</div>}

        <div className="grid">
          <section className="panel input-panel">
            <div className="panel-title">
              <RadioTower size={18} />
              <h3>Raw Alert / Logs</h3>
            </div>
            <textarea value={rawAlert} onChange={(event) => setRawAlert(event.target.value)} />
          </section>

          <section className="panel incident-panel">
            <div className="panel-title">
              <AlertTriangle size={18} />
              <h3>Incident Classification</h3>
            </div>
            {incident ? (
              <>
                <div className="incident-head">
                  <div>
                    <span className={severityClass[incident.severity]}>{incident.severity}</span>
                    <h3>{incident.title}</h3>
                    <p>{incident.summary}</p>
                  </div>
                  <div className="score">
                    <strong>{incident.confidence}</strong>
                    <span>confidence</span>
                  </div>
                </div>
                <div className="mini-grid">
                  <Metric label="Type" value={incident.incident_type} />
                  <Metric label="Root cause" value={incident.root_cause} />
                </div>
              </>
            ) : (
              <EmptyState text="Run analysis to classify the alert and score severity." />
            )}
          </section>

          <section className="panel">
            <div className="panel-title">
              <Activity size={18} />
              <h3>Extracted IOCs</h3>
            </div>
            {incident && incident.extracted_iocs.length > 0 ? (
              <div className="ioc-list">
                {incident.extracted_iocs.map((ioc) => (
                  <div className="ioc" key={`${ioc.type}-${ioc.value}`}>
                    <span>{ioc.type}</span>
                    <code>{ioc.value}</code>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState text="IP addresses, URLs, hashes, domains, users, and emails appear here." />
            )}
          </section>

          <section className="panel">
            <div className="panel-title">
              <ClipboardList size={18} />
              <h3>MITRE ATT&CK</h3>
            </div>
            {incident ? (
              <div className="mitre-list">
                {incident.mitre_attack.map((item) => (
                  <div key={item.technique_id}>
                    <strong>{item.technique_id}</strong>
                    <span>{item.technique}</span>
                    <small>{item.tactic}</small>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState text="Technique mappings appear after classification." />
            )}
          </section>

          <section className="panel wide">
            <div className="panel-title">
              <ShieldAlert size={18} />
              <h3>Response Recommendations</h3>
            </div>
            {incident ? (
              <ol className="actions">
                {incident.recommended_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ol>
            ) : (
              <EmptyState text="Containment and investigation steps appear here." />
            )}
          </section>

          <section className="panel wide chat-panel">
            <div className="panel-title">
              <MessageSquare size={18} />
              <h3>Chat with Incident</h3>
            </div>
            <div className="messages">
              {messages.length === 0 ? (
                <EmptyState text="Analyze an alert, then ask about IOCs, severity, MITRE mapping, or next steps." />
              ) : (
                messages.map((message, index) => (
                  <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
                    <span>{message.role === "analyst" ? "Analyst" : "Copilot"}</span>
                    <p>{message.text}</p>
                  </div>
                ))
              )}
            </div>
            <div className="chat-input">
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") handleAsk();
                }}
                placeholder="Ask: What should I do next?"
                disabled={!incident || isChatting}
              />
              <button onClick={handleAsk} disabled={!incident || isChatting}>
                <MessageSquare size={18} />
              </button>
            </div>
          </section>

          <section className="panel wide report-panel">
            <div className="panel-title">
              <FileText size={18} />
              <h3>Analyst-Ready Report</h3>
            </div>
            <pre>{incident?.analyst_report ?? "Run an analysis to generate the incident report."}</pre>
          </section>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="empty">{text}</p>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
