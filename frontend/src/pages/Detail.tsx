import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, API_BASE, reportText } from "../api";
import type { Alert, CopilotResult, Message, Status } from "../types";
import { Badge, ErrorNotice, Loading, Meta } from "../components/Common";
import { usePreferences } from "../App";
import Chat from "../components/Chat";

export default function DetailRoute() {
  const { id = "" } = useParams();
  return <Detail key={id} id={id} />;
}
function Detail({ id }: { id: string }) {
  const [alert, setAlert] = useState<Alert | null>(null),
    [result, setResult] = useState<CopilotResult | null>(null),
    [messages, setMessages] = useState<Message[]>([]),
    [error, setError] = useState(""),
    [generating, setGenerating] = useState(false),
    [notes, setNotes] = useState(""),
    [saved, setSaved] = useState(""),
    [saving, setSaving] = useState(false),
    [statusBusy, setStatusBusy] = useState(false);
  const { rulesOnly } = usePreferences();
  const active = useRef(true);
  const generationVersion = useRef(0);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      api<Alert>(`/api/alerts/${id}`, undefined, undefined, ctrl.signal),
      api<{ text: string }>(
        `/api/alerts/${id}/notes`,
        undefined,
        undefined,
        ctrl.signal,
      ),
      api<Message[]>(
        `/api/alerts/${id}/chat`,
        undefined,
        undefined,
        ctrl.signal,
      ),
    ])
      .then(([a, n, m]) => {
        setAlert(a);
        setNotes(n.text);
        setMessages(m);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, [id]);
  useEffect(() => {
    generationVersion.current++;
    setResult(null);
    setGenerating(false);
  }, [rulesOnly]);
  async function explain(regenerate = false) {
    const version = ++generationVersion.current;
    setGenerating(true);
    setError("");
    try {
      const r = await api<CopilotResult>(
        `/api/alerts/${id}/explain?regenerate=${regenerate}&rules_only=${rulesOnly}`,
        {},
      );
      if (active.current && version === generationVersion.current) setResult(r);
    } catch (e) {
      if (active.current && version === generationVersion.current)
        setError((e as Error).message);
    } finally {
      if (active.current && version === generationVersion.current)
        setGenerating(false);
    }
  }
  async function saveNotes() {
    setSaving(true);
    setSaved("");
    try {
      await api(`/api/alerts/${id}/notes`, { text: notes }, "PUT");
      if (active.current) setSaved("Notes saved.");
    } catch (e) {
      if (active.current) setError((e as Error).message);
    } finally {
      if (active.current) setSaving(false);
    }
  }
  async function changeStatus(status: Status) {
    setStatusBusy(true);
    try {
      const a = await api<Alert>(
        `/api/alerts/${id}/status`,
        { status },
        "PATCH",
      );
      if (active.current) setAlert(a);
    } catch (e) {
      if (active.current) setError((e as Error).message);
    } finally {
      if (active.current) setStatusBusy(false);
    }
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(await reportText(id, rulesOnly));
      if (active.current) setSaved("Markdown report copied.");
    } catch (e) {
      if (active.current) setError((e as Error).message);
    }
  }
  if (!alert)
    return (
      <>
        <Link to="/">← Alert queue</Link>
        <ErrorNotice error={error} />
        {!error && <Loading label="Loading alert" />}
      </>
    );
  const b = alert.baseline;
  const grouped: Record<string, string[]> = {};
  b.extracted_iocs.forEach((i) => (grouped[i.type] ??= []).push(i.value));
  return (
    <>
      <Link className="back" to="/">
        ← Alert queue
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">
            {alert.display_id} / {alert.origin}
          </p>
          <h1>{b.incident_type}</h1>
          <p>
            {alert.source} · {new Date(alert.timestamp).toLocaleString()}
          </p>
        </div>
        <Badge value={b.severity} />
      </div>
      <ErrorNotice error={error} />
      <div className="detail-grid">
        <div>
          <section className="panel">
            <div className="panel-heading">
              <h2>Original alert</h2>
              <span className="muted">Untrusted source data</span>
            </div>
            <pre>{alert.raw_alert}</pre>
          </section>
          <section className="panel">
            <h2>Parsed evidence</h2>
            {b.evidence.length ? (
              <dl>
                {b.evidence.map((x) => (
                  <div key={x.label}>
                    <dt>{x.label}</dt>
                    <dd>{x.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="muted">No structured evidence fields found.</p>
            )}
            <h3>Extracted indicators</h3>
            {Object.entries(grouped).map(([type, values]) => (
              <div className="ioc-group" key={type}>
                <h4>{type}</h4>
                {values.map((v) => (
                  <code key={v}>{v}</code>
                ))}
              </div>
            ))}
            {!b.extracted_iocs.length && (
              <p className="muted">
                No concrete IOCs extracted. Request original logs.
              </p>
            )}
          </section>
          <section className="panel baseline">
            <div className="panel-heading">
              <h2>Detection baseline</h2>
              <Badge value="Rule-based" />
            </div>
            <p>{b.summary}</p>
            <p className="muted">
              {b.confidence} confidence · Candidate cause: {b.root_cause}
            </p>
            <ul>
              {b.why_suspicious.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
            <h3>MITRE ATT&CK candidates</h3>
            {b.mitre_attack.length ? (
              b.mitre_attack.map((x) => (
                <p key={x.technique_id}>
                  <code>{x.technique_id}</code> {x.technique} · {x.tactic}
                </p>
              ))
            ) : (
              <p>No technique supported by these rules.</p>
            )}
          </section>
        </div>
        <div>
          <section className="panel copilot">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">LOCAL ASSISTANT</p>
                <h2>Copilot explanation</h2>
              </div>
              <button
                className="primary"
                disabled={generating}
                onClick={() => explain(!!result)}
              >
                {result ? "Regenerate" : "Explain alert"}
              </button>
            </div>
            <p className="disclosure">
              AI-generated, verify before acting. Rule fallback is labeled
              below.
            </p>
            {generating && (
              <>
                <Loading label="Generating explanation" />
                <p className="muted">
                  CPU generation can take 10–30+ seconds. You can continue
                  reviewing the evidence.
                </p>
              </>
            )}
            {result ? (
              <>
                <Meta value={result} />
                {result.cached && (
                  <small>
                    Saved explanation · original generation time shown
                  </small>
                )}
                <ErrorNotice error={result.fallback_reason ?? ""} />
                {result.context_truncated && (
                  <p className="notice">
                    Model context was shortened to fit the local budget (raw
                    text, long fields, or history). Full alert remains on the
                    left.
                  </p>
                )}
                <h3>Summary</h3>
                <p>{result.summary}</p>
                <h3>Why it matters</h3>
                <p>{result.why_it_matters}</p>
                <h3>Verify first</h3>
                <div className="checklist">
                  {result.verify_first.map((x, i) => (
                    <label key={`${i}-${x}`}>
                      <input type="checkbox" />
                      {x}
                    </label>
                  ))}
                </div>
                <h3>Recommended next steps</h3>
                <ol>
                  {result.next_steps.map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ol>
                {result.false_positive_likelihood && (
                  <p className="notice">
                    <b>
                      False-positive likelihood:{" "}
                      {result.false_positive_likelihood.likelihood}
                    </b>
                    <br />
                    {result.false_positive_likelihood.reason}
                  </p>
                )}
              </>
            ) : (
              !generating && (
                <div className="empty">
                  Generate an explanation to see what matters and what to verify
                  first. {rulesOnly && "Rules-only mode is enabled."}
                </div>
              )
            )}
          </section>
          <Chat id={id} messages={messages} onMessages={setMessages} />
        </div>
      </div>
      <section className="panel disposition">
        <div>
          <h2>Analyst disposition</h2>
          <label>
            Status
            <select
              value={alert.status}
              disabled={statusBusy}
              onChange={(e) => changeStatus(e.target.value as Status)}
            >
              {["New", "In progress", "Closed"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <p className="muted">Every status change is recorded in History.</p>
          <div className="actions">
            <button onClick={copy}>Copy Markdown</button>
            <a
              className="button"
              href={`${API_BASE}/api/alerts/${id}/report.md?rules_only=${rulesOnly}`}
            >
              Export report.md
            </a>
          </div>
        </div>
        <div>
          <label htmlFor="notes">Analyst notes</label>
          <textarea
            id="notes"
            disabled={saving}
            rows={5}
            maxLength={20000}
            value={notes}
            onChange={(e) => {
              setNotes(e.target.value);
              setSaved("Unsaved changes");
            }}
          />
          <button disabled={saving} onClick={saveNotes}>
            {saving ? "Saving…" : "Save notes"}
          </button>
          <span className="save-feedback" role="status">
            {saved}
          </span>
        </div>
      </section>
    </>
  );
}
