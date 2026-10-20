import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { AlertPage, Stats } from "../types";
import { AlertTable, ErrorNotice, Loading, Pager } from "../components/Common";

export default function Queue() {
  const [data, setData] = useState<AlertPage | null>(null),
    [stats, setStats] = useState<Stats | null>(null),
    [error, setError] = useState("");
  const [severity, setSeverity] = useState(""),
    [status, setStatus] = useState(""),
    [type, setType] = useState(""),
    [q, setQ] = useState(""),
    [page, setPage] = useState(1),
    [lookup, setLookup] = useState(""),
    [revision, setRevision] = useState(0);
  const navigate = useNavigate();
  useEffect(() => {
    const ctrl = new AbortController();
    setError("");
    setData(null);
    const qs = new URLSearchParams({
      severity,
      status,
      type,
      q,
      page: String(page),
    });
    Promise.all([
      api<AlertPage>("/api/alerts?" + qs, undefined, undefined, ctrl.signal),
      api<Stats>("/api/stats", undefined, undefined, ctrl.signal),
    ])
      .then(([d, s]) => {
        setData(d);
        setStats(s);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, [severity, status, type, q, page, revision]);
  function lookupAlert(e: React.FormEvent) {
    e.preventDefault();
    const id = lookup.trim().toUpperCase().replace(/^ALR-/, "");
    if (!/^\d+$/.test(id)) {
      setError("Enter an alert number, for example 1002 or ALR-1002.");
      return;
    }
    navigate("/alerts/" + id);
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">TRIAGE WORKSPACE</p>
          <h1>Alert queue</h1>
          <p>Review the signal. Verify the evidence. Decide the response.</p>
        </div>
        <button onClick={() => setRevision((v) => v + 1)}>Refresh queue</button>
      </div>
      <ErrorNotice error={error} />
      {error && (
        <button onClick={() => setRevision((v) => v + 1)}>
          Retry connection
        </button>
      )}
      {stats && (
        <>
          <div className="stats-strip">
            <div>
              <span>Open alerts</span>
              <strong>{stats.open_count}</strong>
            </div>
            {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => (
              <div key={s}>
                <span>{s}</span>
                <strong className={s.toLowerCase()}>
                  {stats.by_severity[s] ?? 0}
                </strong>
              </div>
            ))}
          </div>
          <div className="overview">
            <section>
              <h2>Detection mix</h2>
              <div className="type-counts">
                {Object.entries(stats.by_type).map(([t, n]) => (
                  <button
                    key={t}
                    onClick={() => {
                      setType(t);
                      setPage(1);
                    }}
                  >
                    {t}
                    <b>{n}</b>
                  </button>
                ))}
              </div>
            </section>
            <section>
              <h2>
                Alert volume <small>per day · UTC</small>
              </h2>
              <div
                className="bar-chart"
                role="img"
                aria-label={stats.over_time
                  .map((x) => `${x.time}: ${x.count} alerts`)
                  .join(", ")}
              >
                {stats.over_time.map((x) => (
                  <div key={x.time}>
                    <span>{x.count}</span>
                    <i
                      style={{
                        height: `${Math.max(4, (x.count / Math.max(...stats.over_time.map((v) => v.count))) * 60)}px`,
                      }}
                    />
                    <small>{x.time.slice(5)}</small>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </>
      )}
      <section className="panel">
        <div className="panel-heading">
          <h2>All alerts</h2>
          <form onSubmit={lookupAlert} className="lookup">
            <label htmlFor="lookup">Go to alert #</label>
            <input
              id="lookup"
              value={lookup}
              onChange={(e) => setLookup(e.target.value)}
              placeholder="1002"
            />
            <button>Open alert</button>
          </form>
        </div>
        <div className="filters">
          <label>
            Search
            <input
              value={q}
              placeholder="ID, source, or alert text"
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <label>
            Severity
            <select
              value={severity}
              onChange={(e) => {
                setSeverity(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All severities</option>
              {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              {["New", "In progress", "Closed"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Type
            <select
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All types</option>
              {Object.keys(stats?.by_type ?? {}).map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <button
            onClick={() => {
              setQ("");
              setSeverity("");
              setStatus("");
              setType("");
              setPage(1);
            }}
          >
            Clear
          </button>
        </div>
        {data ? (
          <>
            <AlertTable items={data.items} />
            <Pager page={page} total={data.total} size={20} onPage={setPage} />
          </>
        ) : (
          !error && <Loading label="Loading alerts" />
        )}
      </section>
    </>
  );
}
