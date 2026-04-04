"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DeliveryAttempt } from "@/lib/api";
import { use } from "react";

const SEVERITY_COLOR: Record<string, string> = {
  low:      "var(--green)",
  medium:   "var(--yellow)",
  high:     "var(--amber)",
  critical: "var(--red)",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", borderBottom: "1px solid var(--border)" }}>
      <div style={{
        width: 180,
        padding: "9px 16px",
        fontSize: 11,
        color: "var(--text-muted)",
        letterSpacing: "0.06em",
        background: "var(--bg-surface)",
        borderRight: "1px solid var(--border)",
        flexShrink: 0,
        textTransform: "uppercase",
      }}>
        {label}
      </div>
      <div style={{
        flex: 1,
        padding: "9px 16px",
        fontSize: 12,
        color: "var(--text-secondary)",
        fontFamily: "var(--font-mono)",
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}>
        {children}
      </div>
    </div>
  );
}

export default function AttemptDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [attempt, setAttempt] = useState<DeliveryAttempt | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    api.get(`/api/v1/dashboard/delivery-attempts/${id}`)
      .then(setAttempt)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await api.post(`/api/v1/dashboard/delivery-attempts/${id}/retry`, {});
      const updated = await api.get(`/api/v1/dashboard/delivery-attempts/${id}`);
      setAttempt(updated);
    } catch (e) {
      console.error(e);
    } finally {
      setRetrying(false);
    }
  };

  if (loading) return (
    <div style={{ padding: 28, fontSize: 12, color: "var(--text-muted)" }}>Loading...</div>
  );
  if (!attempt) return (
    <div style={{ padding: 28, fontSize: 12, color: "var(--text-muted)" }}>Attempt not found.</div>
  );

  const statusColors: Record<string, string> = {
    delivered: "var(--green)", failed: "var(--red)",
    pending: "var(--yellow)", delivering: "var(--blue)", dead: "var(--gray)",
  };

  return (
    <div>
      {/* Header */}
      <div style={{
        padding: "20px 28px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Link href="/dashboard/attempts" style={{ fontSize: 11, color: "var(--text-muted)", letterSpacing: "0.06em" }}>
            ← ATTEMPTS
          </Link>
          <span style={{ color: "var(--border-bright)" }}>|</span>
          <h1 style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>
            Attempt Detail
          </h1>
          <span style={{
            fontSize: 11,
            color: statusColors[attempt.status] || "var(--gray)",
            background: `${statusColors[attempt.status]}15`,
            padding: "2px 8px",
            border: `1px solid ${statusColors[attempt.status]}40`,
            borderRadius: "var(--radius)",
          }}>
            {attempt.status.toUpperCase()}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {(attempt.status === "failed" || attempt.status === "dead") && (
            <button
              onClick={handleRetry}
              disabled={retrying}
              className="btn btn-primary"
            >
              {retrying ? "Queuing..." : "Retry Delivery"}
            </button>
          )}
        </div>
      </div>

      <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Primary fields */}
        <div className="card" style={{ overflow: "hidden" }}>
          <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
            <span className="section-label">Delivery Record</span>
          </div>
          <Field label="Attempt ID"><span style={{ color: "var(--text-muted)" }}>{attempt.id}</span></Field>
          <Field label="Event Type">
            <span className="tag tag-amber">{attempt.event?.event_type || "—"}</span>
          </Field>
          <Field label="Attempt #">#{attempt.attempt_number}</Field>
          <Field label="Response Code">
            {attempt.response_code ? (
              <span className={`tag ${attempt.response_code < 300 ? "tag-green" : attempt.response_code < 500 ? "tag-yellow" : "tag-red"}`}>
                {attempt.response_code}
              </span>
            ) : "—"}
          </Field>
          <Field label="Duration">
            {attempt.duration_ms ? `${attempt.duration_ms.toFixed(1)}ms` : "—"}
          </Field>
          <Field label="Created">{new Date(attempt.created_at).toISOString()}</Field>
          {attempt.delivered_at && (
            <Field label="Delivered At">{new Date(attempt.delivered_at).toISOString()}</Field>
          )}
          {attempt.next_retry_at && (
            <Field label="Next Retry">{new Date(attempt.next_retry_at).toISOString()}</Field>
          )}
        </div>

        {/* Error */}
        {attempt.error_message && (
          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{
              padding: "10px 16px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}>
              <span className="status-dot status-failed" />
              <span className="section-label">Error Details</span>
            </div>
            <div style={{ padding: 16 }}>
              <pre className="code-block" style={{ color: "var(--red)", borderColor: "rgba(239,68,68,0.2)", background: "var(--red-glow)" }}>
                {attempt.error_message}
              </pre>
            </div>
          </div>
        )}

        {/* AI Analysis */}
        {attempt.ai_analysis && (
          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{
              padding: "10px 16px",
              borderBottom: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 11, color: "var(--amber)" }}>◆</span>
                <span className="section-label">AI Failure Analysis</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
                  Confidence: {(attempt.ai_analysis.confidence_score * 100).toFixed(0)}%
                </span>
                <span style={{
                  fontSize: 11,
                  fontWeight: 500,
                  color: SEVERITY_COLOR[attempt.ai_analysis.severity] || "var(--gray)",
                  letterSpacing: "0.08em",
                }}>
                  {attempt.ai_analysis.severity.toUpperCase()}
                </span>
              </div>
            </div>

            <Field label="Category">
              <span className="tag tag-amber">{attempt.ai_analysis.failure_category}</span>
            </Field>
            <Field label="Explanation">
              <span style={{ whiteSpace: "pre-wrap", color: "var(--text-secondary)", fontFamily: "var(--font-sans)", fontSize: 13 }}>
                {attempt.ai_analysis.explanation}
              </span>
            </Field>
            <Field label="Suggested Fix">
              <span style={{ whiteSpace: "pre-wrap", color: "var(--text-secondary)", fontFamily: "var(--font-sans)", fontSize: 13 }}>
                {attempt.ai_analysis.suggested_fix}
              </span>
            </Field>
          </div>
        )}

        {/* Event payload */}
        {attempt.event && (
          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
              <span className="section-label">Event Payload</span>
            </div>
            <div style={{ padding: 16 }}>
              <pre className="code-block">
                {JSON.stringify(attempt.event.payload, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {/* Response body */}
        {attempt.response_body && (
          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
              <span className="section-label">Response Body</span>
            </div>
            <div style={{ padding: 16 }}>
              <pre className="code-block">{attempt.response_body}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}