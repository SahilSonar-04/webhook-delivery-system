import Link from "next/link";

export default function Home() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "48px 24px",
        position: "relative",
        overflow: "hidden",
      }}
      className="grid-bg"
    >
      {/* Corner marks */}
      <span style={{
        position: "absolute", top: 24, left: 24,
        fontSize: 10, letterSpacing: "0.1em",
        color: "var(--text-muted)", fontFamily: "var(--font-mono)"
      }}>
        WDS / v1.0.0
      </span>
      <span style={{
        position: "absolute", top: 24, right: 24,
        fontSize: 10, letterSpacing: "0.1em",
        color: "var(--text-muted)", fontFamily: "var(--font-mono)"
      }}>
        SYS:ONLINE
      </span>

      <div style={{ textAlign: "center", maxWidth: 480, animation: "slide-in 0.4s ease forwards" }}>
        {/* System label */}
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          marginBottom: 32, padding: "4px 12px",
          border: "1px solid var(--border-bright)",
          borderRadius: "var(--radius)",
        }}>
          <span className="status-dot status-delivered live-dot" />
          <span style={{ fontSize: 10, letterSpacing: "0.12em", color: "var(--text-muted)" }}>
            WEBHOOK DELIVERY SYSTEM
          </span>
        </div>

        <h1 style={{
          fontSize: 52,
          fontWeight: 300,
          letterSpacing: "-0.03em",
          lineHeight: 1.1,
          marginBottom: 16,
          color: "var(--text-primary)",
          fontFamily: "var(--font-mono)",
        }}>
          WDS
        </h1>

        <p style={{
          fontSize: 13,
          color: "var(--text-secondary)",
          marginBottom: 8,
          fontFamily: "var(--font-mono)",
          letterSpacing: "0.02em",
        }}>
          Async event delivery with exponential backoff,
        </p>
        <p style={{
          fontSize: 13,
          color: "var(--text-secondary)",
          marginBottom: 48,
          fontFamily: "var(--font-mono)",
          letterSpacing: "0.02em",
        }}>
          dead-letter queuing &amp; AI failure analysis.
        </p>

        <Link href="/dashboard" className="btn btn-primary" style={{ fontSize: 13, padding: "10px 28px" }}>
          Open Dashboard →
        </Link>

        {/* Stats row */}
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
          gap: 1, marginTop: 64,
          border: "1px solid var(--border)",
          background: "var(--border)",
        }}>
          {[
            { label: "Max Retries", value: "5" },
            { label: "Backoff", value: "EXP" },
            { label: "Timeout", value: "30s" },
          ].map((s) => (
            <div key={s.label} style={{
              background: "var(--bg-surface)", padding: "16px",
              textAlign: "center",
            }}>
              <div style={{ fontSize: 20, fontWeight: 300, color: "var(--amber)", letterSpacing: "-0.02em", marginBottom: 4 }}>
                {s.value}
              </div>
              <div style={{ fontSize: 10, letterSpacing: "0.1em", color: "var(--text-muted)", textTransform: "uppercase" }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom label */}
      <span style={{
        position: "absolute", bottom: 24,
        fontSize: 10, letterSpacing: "0.08em",
        color: "var(--text-dim)", fontFamily: "var(--font-mono)"
      }}>
        RELIABLE · OBSERVABLE · RESILIENT
      </span>
    </main>
  );
}