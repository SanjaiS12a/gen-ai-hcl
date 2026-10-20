import { useEffect, useState } from "react";
import { api } from "../api";
import type { Health } from "../types";
import { ErrorNotice } from "../components/Common";
import { usePreferences } from "../App";
export default function SettingsPage() {
  const { rulesOnly, setRulesOnly } = usePreferences();
  const [health, setHealth] = useState<Health | null>(null),
    [error, setError] = useState(""),
    [feedback, setFeedback] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    const ctrl = new AbortController();
    api<Health>("/health", undefined, undefined, ctrl.signal)
      .then(setHealth)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, []);
  async function reload() {
    setBusy(true);
    setError("");
    try {
      await api("/api/seed", {});
      setFeedback("30 simulated alerts reloaded. Webhook alerts preserved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">LOCAL CONFIGURATION</p>
          <h1>Settings</h1>
          <p>Control assistance and inspect the local runtime.</p>
        </div>
      </div>
      <ErrorNotice error={error} />
      <section className="panel settings-panel">
        <h2>Copilot assistance</h2>
        <label className="toggle">
          <input
            type="checkbox"
            checked={!rulesOnly}
            onChange={(e) => setRulesOnly(!e.target.checked)}
          />
          Enable local model explanations
        </label>
        <p>
          {rulesOnly
            ? "Rules-only mode: explanation and chat requests bypass model generation."
            : "Local model enabled: unavailable or invalid output falls back to rules."}
        </p>
        <p className="muted">
          This preference is saved in this browser. Indicators, classification,
          severity, and MITRE mappings always come from code.
        </p>
        <h3>Runtime</h3>
        {health?.model_error && <ErrorNotice error={health.model_error}/>}
        {health ? (
          <dl>
            <div>
              <dt>Provider</dt>
              <dd>{health.provider}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{health.model}</dd>
            </div>
            <div>
              <dt>Model state</dt>
              <dd>{health.model_status}</dd>
            </div>
          </dl>
        ) : (
          <p>Model information unavailable. Check the backend.</p>
        )}
        <p className="muted">
          Change provider/model with backend environment variables and restart.
          Model not loaded is normal before the first request.
        </p>
      </section>
      <section className="panel settings-panel">
        <h2>Simulated alert feed</h2>
        <p>The demo feed is seeded data. No SIEM is connected by default.</p>
        <p>
          Reload resets sample alert statuses, notes, explanations, and chats.
          Webhook alerts are preserved.
        </p>
        <button disabled={busy} onClick={reload}>
          {busy ? "Reloading…" : "Reload 30 sample alerts"}
        </button>
        <p role="status">{feedback}</p>
      </section>
    </>
  );
}
