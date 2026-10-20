import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Alert, Health, Provenance } from "../types";
import { usePreferences } from "../App";

export function ErrorNotice({ error }: { error: string }) {
  return error ? (
    <div className="error" role="alert">
      {error}
    </div>
  ) : null;
}
export function Badge({ value }: { value: string }) {
  return (
    <span className={`badge ${value.toLowerCase().replace(/ /g, "-")}`}>
      {value}
    </span>
  );
}
export function Meta({ value }: { value: Provenance }) {
  return (
    <div className="meta">
      <Badge
        value={
          value.engine === "rules"
            ? "Rule-based"
            : value.provider === "mock"
              ? "Mock output"
              : "Local AI"
        }
      />
      <span>
        {value.model} · {(value.generation_ms / 1000).toFixed(1)} s
      </span>
    </div>
  );
}
export function Loading({ label = "Loading" }: { label?: string }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      {label} · {elapsed}s
    </div>
  );
}
export function SystemStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");
  const { rulesOnly } = usePreferences();
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const h = await api<Health>("/health");
        if (active) {
          setHealth(h);
          setError("");
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    }
    void refresh();
    const timer = setInterval(refresh, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  return (
    <header className="systembar">
      <span>
        <span className={`local-dot ${error ? "offline" : ""}`} />
        {error
          ? "Backend not running"
          : health
            ? `${health.provider} · ${health.model_status.replace(/_/g, " ")}`
            : "Connecting to backend…"}
      </span>
      <span>
        {rulesOnly ? "Rules-only mode" : "Copilot enabled"}
        <span className="divider">/</span> Seed source: simulated feed · webhook
        ingest supported
      </span>
    </header>
  );
}
export function AlertTable({ items }: { items: Alert[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Alert</th>
            <th>Time</th>
            <th>Source</th>
            <th>Type</th>
            <th>Severity</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.id}>
              <td>
                <Link className="id-link" to={`/alerts/${a.id}`}>
                  {a.display_id}
                </Link>
                <small>{a.origin}</small>
              </td>
              <td>{new Date(a.timestamp).toLocaleString()}</td>
              <td>{a.source}</td>
              <td>{a.baseline.incident_type}</td>
              <td>
                <Badge value={a.baseline.severity} />
              </td>
              <td>{a.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && (
        <div className="empty">No alerts match these filters.</div>
      )}
    </div>
  );
}
export function Pager({
  page,
  total,
  size,
  onPage,
}: {
  page: number;
  total: number;
  size: number;
  onPage: (n: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <div className="pager">
      <span>
        {total} records · Page {page} of {pages}
      </span>
      <div>
        <button disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <button disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}
