"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DeliveryAttempt } from "@/lib/api";

const STATUSES = ["", "pending", "delivering", "delivered", "failed", "dead"] as const;

const STATUS_CONFIG: Record<string, { color: string; tagCls: string; dotCls: string }> = {
  delivered:  { color: "var(--green)",  tagCls: "tag-green",  dotCls: "status-delivered" },
  failed:     { color: "var(--red)",    tagCls: "tag-red",    dotCls: "status-failed" },
  pending:    { color: "var(--yellow)", tagCls: "tag-yellow", dotCls: "status-pending" },
  delivering: { color: "var(--blue)",   tagCls: "tag-blue",   dotCls: "status-delivering" },
  dead:       { color: "var(--gray)",   tagCls: "tag-gray",   dotCls: "status-dead" },
};

export default function AttemptsPage() {
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const url = filter
      ? `/api/v1/dashboard/delivery-attempts?status=${filter}&limit=50`
      : "/api/v1/dashboard/delivery-attempts?limit=50";
    api.get(url)
      .then(setAttempts)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [filter]);

  return (
    <div>
      <div style={{
        padding: "20px 28px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <h1 style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Delivery Attempts</h1>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{attempts.length} shown</span>
        </div>

        {/* Filter tabs */}
        <div style={{ display: "flex", gap: 1, background: "var(--border)", border: "1px solid var(--border)" }}>
          {STATUSES.map((s) => {
            const active = filter === s;
            return (
              <button
                key={s}
                onClick={() => setFilter(s)}
                style={{
                  padding: "5px 12px",
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                  letterSpacing: "0.06em",
                  background: active ? "var(--amber)" : "var(--bg-surface)",
                  color: active ? "var(--bg-base)" : "var(--text-muted)",
                  border: "none",
                  cursor: "pointer",
                  transition: "all 0.1s",
                  textTransform: "uppercase",
                }}
              >
                {s || "All"}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ padding: 28 }}>
        {loading ? (
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading...</div>
        ) : (
          <div className="card" style={{ overflow: "hidden" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Event Type</th>
                  <th>Attempt</th>
                  <th>Response</th>
                  <th>Duration</th>
                  <th>AI</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((a) => {
                  const cfg = STATUS_CONFIG[a.status] || { color: "var(--gray)", tagCls: "tag-gray", dotCls: "status-dead" };
                  return (
                    <tr key={a.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                          <span className={`status-dot ${cfg.dotCls}`} />
                          <span className={`tag ${cfg.tagCls}`}>{a.status}</span>
                        </div>
                      </td>
                      <td style={{ color: "var(--text-primary)", fontWeight: 400 }}>
                        {a.event?.event_type || <span style={{ color: "var(--text-muted)" }}>—</span>}
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>#{a.attempt_number}</td>
                      <td>
                        {a.response_code ? (
                          <span className={`tag ${a.response_code < 300 ? "tag-green" : a.response_code < 500 ? "tag-yellow" : "tag-red"}`}>
                            {a.response_code}
                          </span>
                        ) : <span style={{ color: "var(--text-muted)" }}>—</span>}
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>
                        {a.duration_ms ? `${Math.round(a.duration_ms)}ms` : "—"}
                      </td>
                      <td>
                        {a.ai_analysis ? (
                          <span className="tag tag-amber" title={a.ai_analysis.failure_category}>
                            {a.ai_analysis.severity}
                          </span>
                        ) : <span style={{ color: "var(--text-dim)" }}>—</span>}
                      </td>
                      <td style={{ color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                        {new Date(a.created_at).toLocaleString("en-US", {
                          month: "short", day: "2-digit",
                          hour: "2-digit", minute: "2-digit", hour12: false
                        })}
                      </td>
                      <td>
                        <Link
                          href={`/dashboard/attempts/${a.id}`}
                          className="btn btn-ghost btn-sm"
                        >
                          View
                        </Link>
                      </td>
                    </tr>
                  );
                })}
                {attempts.length === 0 && (
                  <tr>
                    <td colSpan={8} style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
                      No attempts found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}