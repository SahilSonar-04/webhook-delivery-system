"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DashboardStats, DeliveryAttempt } from "@/lib/api";

const STATUS_CONFIG: Record<string, { color: string; cls: string }> = {
  delivered: { color: "var(--green)", cls: "status-delivered" },
  failed:    { color: "var(--red)",   cls: "status-failed" },
  pending:   { color: "var(--yellow)",cls: "status-pending" },
  delivering:{ color: "var(--blue)",  cls: "status-delivering" },
  dead:      { color: "var(--gray)",  cls: "status-dead" },
};

function PageHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div style={{
      padding: "20px 28px",
      borderBottom: "1px solid var(--border)",
      display: "flex",
      alignItems: "baseline",
      gap: 16,
    }}>
      <h1 style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)", letterSpacing: "0.02em" }}>
        {title}
      </h1>
      {sub && (
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{sub}</span>
      )}
    </div>
  );
}

function StatCard({ label, value, color, sub }: { label: string; value: string | number; color?: string; sub?: string }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: color || "var(--text-primary)" }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);
  const [liveEvents, setLiveEvents] = useState<{ time: string; text: string; type: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, attemptsData] = await Promise.all([
          api.get("/api/v1/dashboard/stats"),
          api.get("/api/v1/dashboard/delivery-attempts?limit=12"),
        ]);
        setStats(statsData);
        setAttempts(attemptsData);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);

    const sse = new EventSource(
      `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/dashboard/stream`
    );
    sse.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type !== "heartbeat") {
        setLiveEvents((prev) => [
          {
            time: new Date().toLocaleTimeString("en-US", { hour12: false }),
            text: `[${data.type.toUpperCase()}] ${JSON.stringify(data.data).slice(0, 90)}`,
            type: data.type,
          },
          ...prev.slice(0, 29),
        ]);
      }
    };

    return () => {
      clearInterval(interval);
      sse.close();
    };
  }, []);

  if (loading) {
    return (
      <div style={{ padding: 28, color: "var(--text-muted)", fontSize: 12 }}>
        Initializing...
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="System Overview" sub="Real-time delivery monitoring" />

      <div style={{ padding: 28 }}>
        {/* Primary stats */}
        {stats && (
          <>
            <div style={{ marginBottom: 6 }} className="section-label">System Metrics</div>
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: 1,
              marginBottom: 24,
              background: "var(--border)",
              border: "1px solid var(--border)",
            }}>
              <StatCard label="Ingested Events" value={stats.total_events.toLocaleString()} color="var(--text-primary)" />
              <StatCard
                label="Success Rate"
                value={`${stats.success_rate}%`}
                color={stats.success_rate >= 90 ? "var(--green)" : stats.success_rate >= 70 ? "var(--yellow)" : "var(--red)"}
                sub={`${stats.delivered} of ${stats.total_attempts} attempts`}
              />
            </div>

            <div style={{ marginBottom: 6 }} className="section-label">Attempt Breakdown</div>
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(5, 1fr)",
              gap: 1,
              marginBottom: 24,
              background: "var(--border)",
              border: "1px solid var(--border)",
            }}>
              {[
                { label: "Delivered", value: stats.delivered, color: "var(--green)" },
                { label: "Delivering", value: stats.delivering, color: "var(--blue)" },
                { label: "Pending", value: stats.pending, color: "var(--yellow)" },
                { label: "Failed", value: stats.failed, color: "var(--red)" },
                { label: "Dead", value: stats.dead, color: "var(--gray)" },
              ].map((s) => (
                <StatCard key={s.label} label={s.label} value={s.value.toLocaleString()} color={s.color} />
              ))}
            </div>

            {/* Progress bar */}
            <div style={{ marginBottom: 28 }}>
              <div style={{
                height: 3,
                background: "var(--bg-overlay)",
                overflow: "hidden",
                border: "1px solid var(--border)",
              }}>
                <div style={{
                  height: "100%",
                  width: `${stats.success_rate}%`,
                  background: stats.success_rate >= 90 ? "var(--green)" : stats.success_rate >= 70 ? "var(--yellow)" : "var(--red)",
                  transition: "width 0.6s ease",
                }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5, fontSize: 10, color: "var(--text-muted)" }}>
                <span>0%</span>
                <span>DELIVERY SUCCESS RATE</span>
                <span>100%</span>
              </div>
            </div>
          </>
        )}

        {/* Two column section */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--border)", border: "1px solid var(--border)" }}>
          {/* Recent attempts */}
          <div style={{ background: "var(--bg-base)" }}>
            <div style={{
              padding: "10px 16px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}>
              <span className="section-label">Recent Attempts</span>
              <Link href="/dashboard/attempts" style={{ fontSize: 10, color: "var(--amber)", letterSpacing: "0.06em" }}>
                VIEW ALL →
              </Link>
            </div>

            <div>
              {attempts.length === 0 && (
                <div style={{ padding: "24px 16px", fontSize: 12, color: "var(--text-muted)", textAlign: "center" }}>
                  No delivery attempts yet.
                </div>
              )}
              {attempts.map((a, i) => {
                const cfg = STATUS_CONFIG[a.status] || { color: "var(--gray)", cls: "status-dead" };
                return (
                  <Link key={a.id} href={`/dashboard/attempts/${a.id}`} style={{ display: "block" }}>
                    <div style={{
                      padding: "8px 16px",
                      borderBottom: "1px solid var(--border)",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      cursor: "pointer",
                      transition: "background 0.1s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <span className={`status-dot ${cfg.cls}`} />
                      <span style={{ flex: 1, fontSize: 12, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {a.event?.event_type || "unknown"}
                      </span>
                      <span style={{ fontSize: 10, color: "var(--text-muted)" }}>#{a.attempt_number}</span>
                      <span style={{ fontSize: 10, color: cfg.color, minWidth: 60, textAlign: "right" }}>{a.status}</span>
                      {a.duration_ms && (
                        <span style={{ fontSize: 10, color: "var(--text-muted)", minWidth: 48, textAlign: "right" }}>
                          {Math.round(a.duration_ms)}ms
                        </span>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Live feed */}
          <div style={{ background: "var(--bg-base)" }}>
            <div style={{
              padding: "10px 16px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}>
              <span className="status-dot status-delivered live-dot" style={{ width: 5, height: 5 }} />
              <span className="section-label">Live Event Stream</span>
            </div>

            <div style={{
              padding: 0,
              height: 384,
              overflow: "hidden",
              fontFamily: "var(--font-mono)",
            }}>
              {liveEvents.length === 0 && (
                <div style={{ padding: "24px 16px", fontSize: 11, color: "var(--text-muted)", textAlign: "center" }}>
                  Waiting for events...
                </div>
              )}
              {liveEvents.map((ev, i) => (
                <div key={i} style={{
                  display: "flex",
                  gap: 10,
                  padding: "5px 16px",
                  borderBottom: "1px solid var(--border)",
                  animation: i === 0 ? "slide-in 0.2s ease" : "none",
                  opacity: Math.max(0.3, 1 - i * 0.06),
                }}>
                  <span style={{ fontSize: 10, color: "var(--text-muted)", flexShrink: 0 }}>{ev.time}</span>
                  <span style={{
                    fontSize: 11,
                    color: ev.type.includes("success") || ev.type.includes("delivered")
                      ? "var(--green)"
                      : ev.type.includes("dead")
                      ? "var(--red)"
                      : ev.type.includes("failed")
                      ? "var(--yellow)"
                      : "var(--text-secondary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}>
                    {ev.text}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}