"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DeliveryAttempt } from "@/lib/api";

export default function DeadLetterPage() {
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<string | null>(null);

  const fetchDead = async () => {
    try {
      const data = await api.get("/api/v1/dashboard/dead-letter");
      setAttempts(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDead(); }, []);

  const handleRetry = async (id: string) => {
    setRetrying(id);
    try {
      await api.post(`/api/v1/dashboard/delivery-attempts/${id}/retry`, {});
      await fetchDead();
    } catch (e) {
      console.error(e);
    } finally {
      setRetrying(null);
    }
  };

  return (
    <div>
      <div style={{
        padding: "20px 28px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        gap: 16,
      }}>
        <h1 style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Dead Letter Queue</h1>
        <span style={{
          fontSize: 11,
          color: attempts.length > 0 ? "var(--red)" : "var(--text-muted)",
          background: attempts.length > 0 ? "var(--red-glow)" : "var(--bg-raised)",
          border: `1px solid ${attempts.length > 0 ? "rgba(239,68,68,0.2)" : "var(--border)"}`,
          padding: "1px 8px",
          borderRadius: "var(--radius)",
        }}>
          {attempts.length} items
        </span>
      </div>

      <div style={{ padding: 28 }}>
        {loading ? (
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading...</div>
        ) : attempts.length === 0 ? (
          <div className="card" style={{
            padding: 48,
            textAlign: "center",
          }}>
            <div style={{ fontSize: 24, marginBottom: 8, color: "var(--green)" }}>✓</div>
            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
              Dead letter queue is empty.
            </div>
            <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 4 }}>
              All events have been delivered or are in retry.
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 1, background: "var(--border)", border: "1px solid var(--border)" }}>
            {attempts.map((a) => (
              <div key={a.id} style={{
                background: "var(--bg-base)",
                padding: "16px 20px",
                display: "flex",
                alignItems: "flex-start",
                gap: 20,
              }}>
                {/* Left: status strip */}
                <div style={{
                  width: 3,
                  alignSelf: "stretch",
                  background: "var(--red)",
                  flexShrink: 0,
                  borderRadius: 1,
                }} />

                {/* Center: info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                    <span className="tag tag-amber">{a.event?.event_type || "unknown"}</span>
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      Failed after {a.attempt_number} attempt{a.attempt_number !== 1 ? "s" : ""}
                    </span>
                    <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
                      {new Date(a.created_at).toLocaleString("en-US", {
                        month: "short", day: "2-digit",
                        hour: "2-digit", minute: "2-digit", hour12: false
                      })}
                    </span>
                  </div>

                  {a.error_message && (
                    <div style={{
                      fontSize: 11,
                      color: "var(--red)",
                      fontFamily: "var(--font-mono)",
                      background: "var(--red-glow)",
                      border: "1px solid rgba(239,68,68,0.15)",
                      padding: "5px 10px",
                      borderRadius: "var(--radius)",
                      marginBottom: 8,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}>
                      {a.error_message}
                    </div>
                  )}

                  {a.ai_analysis && (
                    <div style={{
                      fontSize: 11,
                      color: "var(--text-secondary)",
                      background: "var(--amber-glow)",
                      border: "1px solid rgba(245,158,11,0.15)",
                      padding: "6px 10px",
                      borderRadius: "var(--radius)",
                    }}>
                      <span style={{ color: "var(--amber)", marginRight: 6, letterSpacing: "0.04em" }}>
                        ◆ {a.ai_analysis.failure_category.toUpperCase()}
                      </span>
                      {a.ai_analysis.suggested_fix}
                    </div>
                  )}
                </div>

                {/* Right: actions */}
                <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                  <Link href={`/dashboard/attempts/${a.id}`} className="btn btn-ghost btn-sm">
                    View
                  </Link>
                  <button
                    onClick={() => handleRetry(a.id)}
                    disabled={retrying === a.id}
                    className="btn btn-primary btn-sm"
                  >
                    {retrying === a.id ? "Queuing…" : "Retry"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}