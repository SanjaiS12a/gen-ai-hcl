import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { HistoryData } from "../types";
import { AlertTable, ErrorNotice, Loading, Pager } from "../components/Common";
export default function HistoryPage() {
  const [data, setData] = useState<HistoryData | null>(null),
    [error, setError] = useState(""),
    [page, setPage] = useState(1);
  useEffect(() => {
    const ctrl = new AbortController();
    setData(null);
    setError("");
    api<HistoryData>(
      `/api/history?page=${page}`,
      undefined,
      undefined,
      ctrl.signal,
    )
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => ctrl.abort();
  }, [page]);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">CASE RECORD</p>
          <h1>History & audit</h1>
          <p>Closed alerts and the decisions recorded along the way.</p>
        </div>
      </div>
      <ErrorNotice error={error} />
      {data ? (
        <>
          <section className="panel">
            <h2>Status changes</h2>
            {data.changes.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Alert</th>
                      <th>From</th>
                      <th>To</th>
                      <th>Recorded</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.changes.map((x) => (
                      <tr key={x.id}>
                        <td>
                          <Link to={`/alerts/${x.alert_id}`}>
                            ALR-{x.alert_id}
                          </Link>
                        </td>
                        <td>{x.old_status}</td>
                        <td>{x.new_status}</td>
                        <td>{new Date(x.timestamp).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty">No status changes on this page.</p>
            )}
          </section>
          <section className="panel">
            <h2>Closed alerts</h2>
            <AlertTable items={data.closed.items} />
          </section>
          <Pager
            page={page}
            total={Math.max(data.closed.total, data.changes_total)}
            size={20}
            onPage={setPage}
          />
        </>
      ) : (
        !error && <Loading label="Loading audit history" />
      )}
    </>
  );
}
