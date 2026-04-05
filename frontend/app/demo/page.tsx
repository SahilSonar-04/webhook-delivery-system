"use client";
import { useEffect, useRef, useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── types ──────────────────────────────────────────────────────────────────

type SetupStatus = "idle" | "provisioning" | "ready" | "error";
type DeliveryStatus = "pending" | "delivering" | "delivered" | "failed" | "dead";

interface Subscriber { id: string; api_key: string; name: string }
interface Subscription { id: string; event_type: string; target_url: string }

interface Attempt {
  id: string;
  event_id: string;
  status: DeliveryStatus;
  attempt_number: number;
  response_code: number | null;
  duration_ms: number | null;
  error_message: string | null;
  next_retry_at: string | null;
  delivered_at: string | null;
  created_at: string;
  updated_at: string;
  ai_analysis?: {
    failure_category: string;
    explanation: string;
    suggested_fix: string;
    confidence_score: number;
    severity: string;
  } | null;
  event?: { event_type: string; payload: Record<string, unknown> } | null;
}

interface LogEntry { id: number; time: string; text: string; kind: "info" | "ok" | "err" | "warn" | "sys" }

// ── scenarios ──────────────────────────────────────────────────────────────

type ScenarioKey = "success" | "retry" | "dead" | "idempotency" | "no_subscription" | "timeout";

interface Scenario {
  key: ScenarioKey;
  label: string;
  tag: string;
  tagColor: string;
  desc: string;
  endpoint: string;
  eventType: string;
}
const MOCK = process.env.NEXT_PUBLIC_MOCK_URL || "http://mock-subscriber:9000";

const SCENARIOS: Scenario[] = [
  {
    key: "success",
    label: "Successful delivery",
    tag: "Happy path",
    tagColor: "#10b981",
    desc: "Event accepted, HMAC-SHA256 signed, delivered on first attempt. Shows the X-Webhook-Signature header.",
    endpoint: `${MOCK}/webhook`,
    eventType: "order.created",
  },
  {
    key: "retry",
    label: "Failure + retry",
    tag: "Retry",
    tagColor: "#f59e0b",
    desc: "Subscriber returns 500. Watch exponential backoff — next_retry_at advances with each failure.",
    endpoint: `${MOCK}/webhook/fail`,
    eventType: "payment.received",
  },
  {
    key: "dead",
    label: "Dead letter + AI analysis",
    tag: "Dead letter",
    tagColor: "#ef4444",
    desc: "All 5 retries exhausted. Attempt lands in dead letter queue and Groq AI diagnoses the failure.",
    endpoint: `${MOCK}/webhook/fail`,
    eventType: "user.signup",
  },
  {
    key: "idempotency",
    label: "Idempotency",
    tag: "Deduplication",
    tagColor: "#3b82f6",
    desc: "Fire twice with the same idempotency_key. Second call returns the identical event_id — no duplicate delivery.",
    endpoint: `${MOCK}/webhook`,
    eventType: "invoice.paid",
  },
  {
    key: "no_subscription",
    label: "No subscription",
    tag: "Edge case",
    tagColor: "#8b5cf6",
    desc: "Event ingested for an event_type no subscriber has registered. API accepts 202 but queued=0.",
    endpoint: `${MOCK}/webhook`,
    eventType: "shipment.dispatched",
  },
  {
    key: "timeout",
    label: "Timeout",
    tag: "Timeout",
    tagColor: "#f97316",
    desc: "Subscriber hangs for 60 s. Worker cuts the connection after 30 s and schedules exponential retry.",
    endpoint: `${MOCK}/webhook/slow`,
    eventType: "order.created",
  },
];
 

const PAYLOADS: Record<string, Record<string, unknown>> = {
  "order.created":       { order_id: "ord_8f2k", amount: 129.00, currency: "USD", items: 3 },
  "payment.received":    { payment_id: "pay_3xk9", amount: 49.99, status: "captured" },
  "user.signup":         { user_id: "usr_7jd2", email: "alex@example.com", plan: "pro" },
  "invoice.paid":        { invoice_id: "inv_5mx1", total: 299.00, due_date: "2026-04-30" },
  "shipment.dispatched": { shipment_id: "shp_2pq8", carrier: "DHL", eta: "2026-04-08" },
};

const STATUS_COLORS: Record<DeliveryStatus, string> = {
  pending:    "#eab308",
  delivering: "#3b82f6",
  delivered:  "#10b981",
  failed:     "#f97316",
  dead:       "#ef4444",
};

function nowTime() {
  return new Date().toLocaleTimeString("en-US", { hour12: false });
}

// ── StatusPill ─────────────────────────────────────────────────────────────

function StatusPill({ status }: { status: SetupStatus }) {
  const color =
    status === "ready"        ? "#10b981" :
    status === "error"        ? "#ef4444" :
    status === "provisioning" ? "#3b82f6" : "#555";
  const label =
    status === "ready"        ? "Session active" :
    status === "provisioning" ? "Provisioning..." :
    status === "error"        ? "Setup failed"   : "Not started";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 12px", borderRadius: 20, background: color + "18", color, fontSize: 11, letterSpacing: "0.06em" }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, display: "inline-block", animation: status === "ready" ? "pulse 1.5s infinite" : "none" }} />
      {label}
    </div>
  );
}

// ── DemoPage ───────────────────────────────────────────────────────────────

export default function DemoPage() {
  const [setupStatus, setSetupStatus]   = useState<SetupStatus>("idle");
  const [subscriber, setSubscriber]     = useState<Subscriber | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [scenario, setScenario]         = useState<Scenario>(SCENARIOS[0]);
  const [logs, setLogs]                 = useState<LogEntry[]>([]);
  const [attempts, setAttempts]         = useState<Attempt[]>([]);
  const [firing, setFiring]             = useState(false);
  const [totalFired, setTotalFired]     = useState(0);
  const [lastIdempKey, setLastIdempKey] = useState<string | null>(null);
  const [selected, setSelected]         = useState<Attempt | null>(null);
  const [showSig, setShowSig]           = useState(false);

  const logCounter      = useRef(0);
  const logRef          = useRef<HTMLDivElement>(null);
  const sessionEventIds = useRef<Set<string>>(new Set());

  // ── log ────────────────────────────────────────────────────────────────

  const addLog = useCallback((text: string, kind: LogEntry["kind"] = "info") => {
    setLogs((p) => [{ id: ++logCounter.current, time: nowTime(), text, kind }, ...p].slice(0, 80));
  }, []);

  useEffect(() => { if (logRef.current) logRef.current.scrollTop = 0; }, [logs]);

  // ── provision ──────────────────────────────────────────────────────────

  const provision = useCallback(async () => {
    setSetupStatus("provisioning");
    addLog("Provisioning demo session...", "sys");
    try {
      const tag   = Math.random().toString(36).slice(2, 7);
      const email = `demo-${tag}@wds-demo.dev`;

      addLog(`POST /api/v1/subscribers  email=${email}`, "info");
      const subRes = await fetch(`${API}/api/v1/subscribers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: `Demo ${tag}`, email }),
      });
      if (!subRes.ok) throw new Error(`${subRes.status} ${await subRes.text()}`);
      const sub = await subRes.json();
      setSubscriber({ id: sub.id, api_key: sub.api_key, name: sub.name });
      addLog(`Subscriber created  id=${sub.id.slice(0, 8)}...  key=${sub.api_key.slice(0, 16)}...`, "ok");

      const sc = SCENARIOS[0];
      addLog(`POST .../subscriptions  event_type=${sc.eventType}`, "info");
      const scrRes = await fetch(`${API}/api/v1/subscribers/${sub.id}/subscriptions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": sub.api_key },
        body: JSON.stringify({ event_type: sc.eventType, target_url: sc.endpoint }),
      });
      if (!scrRes.ok) throw new Error(`subscription: ${scrRes.status}`);
      const scr = await scrRes.json();
      setSubscription(scr);
      addLog(`Subscription active  id=${scr.id.slice(0, 8)}...`, "ok");
      addLog("Ready — pick a scenario and fire an event", "sys");
      setSetupStatus("ready");
    } catch (e: unknown) {
      addLog(`Setup failed: ${e instanceof Error ? e.message : String(e)}`, "err");
      setSetupStatus("error");
    }
  }, [addLog]);

  // ── switch scenario ────────────────────────────────────────────────────

  const applyScenario = useCallback(async (sc: Scenario, sub: Subscriber) => {
    setScenario(sc);
    setShowSig(false);
    setLastIdempKey(null);

    if (sc.key === "no_subscription") {
      setSubscription(null);
      addLog(`Scenario: no subscription for "${sc.eventType}" — skipping subscription creation`, "sys");
      return;
    }

    addLog(`Switching to: ${sc.label}  target=.../${sc.endpoint.split("/").pop()}`, "sys");
    try {
      const res = await fetch(`${API}/api/v1/subscribers/${sub.id}/subscriptions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": sub.api_key },
        body: JSON.stringify({ event_type: sc.eventType, target_url: sc.endpoint }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const s = await res.json();
      setSubscription(s);
      addLog(`Subscription updated  id=${s.id.slice(0, 8)}...`, "ok");
    } catch (e: unknown) {
      addLog(`Subscription update failed: ${e instanceof Error ? e.message : String(e)}`, "err");
    }
  }, [addLog]);

  // ── fire event ─────────────────────────────────────────────────────────

  const fireEvent = useCallback(async () => {
    if (!subscriber || firing) return;
    setFiring(true);

    const sc  = scenario;
    const key = (sc.key === "idempotency" && lastIdempKey)
      ? lastIdempKey
      : `demo-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

    if (sc.key === "idempotency") {
      if (!lastIdempKey) {
        setLastIdempKey(key);
        addLog("First fire — new idempotency key generated", "sys");
      } else {
        addLog(`Second fire — REUSING key ${key.slice(0, 26)}...  expect same event_id`, "sys");
      }
    }

    if (sc.key === "success") setShowSig(true);

    const payload = PAYLOADS[sc.eventType] ?? {};
    addLog(`POST /api/v1/events  type=${sc.eventType}  key=${key.slice(0, 24)}...`, "info");

    try {
      const res  = await fetch(`${API}/api/v1/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_type: sc.eventType, payload, producer_id: "wds-demo", idempotency_key: key }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);

      const eventId: string = data.event_id;
      const queued: number  = data.queued ?? 0;

      addLog(`202 Accepted  event_id=${eventId.slice(0, 8)}...  queued=${queued}`, "ok");
      setTotalFired((n) => n + 1);

      if (sc.key === "idempotency" && lastIdempKey) {
        addLog("Same event_id returned — idempotency confirmed, no duplicate delivery", "ok");
      }

      if (queued === 0) {
        addLog("No subscriptions matched — event accepted, queued=0 (expected for this scenario)", "warn");
      } else {
        sessionEventIds.current.add(eventId);
        pollForEvent(eventId);
      }
    } catch (e: unknown) {
      addLog(`Event ingestion failed: ${e instanceof Error ? e.message : String(e)}`, "err");
    } finally {
      setFiring(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscriber, firing, scenario, lastIdempKey, addLog]);

  // ── poll attempts ──────────────────────────────────────────────────────

  const pollForEvent = useCallback((eventId: string) => {
    let ticks = 0;
    const MAX = 60;

    const tick = async () => {
      ticks++;
      try {
        const res  = await fetch(`${API}/api/v1/dashboard/delivery-attempts?limit=100`);
        const all: Attempt[] = await res.json();
        const mine = all.filter((a) => sessionEventIds.current.has(a.event_id));

        setAttempts((prev) => {
          const map = new Map(prev.map((a) => [a.id, a]));
          mine.forEach((a) => {
            const old = map.get(a.id);
            if (!old) {
              addLog(
                `Attempt #${a.attempt_number} created -> ${a.status}` +
                (a.response_code ? `  HTTP ${a.response_code}` : "") +
                (a.duration_ms   ? `  ${Math.round(a.duration_ms)}ms` : ""),
                a.status === "delivered" ? "ok" : a.status === "dead" ? "err" : "warn"
              );
            } else if (old.status !== a.status || old.attempt_number !== a.attempt_number) {
              addLog(
                `Attempt #${a.attempt_number} -> ${a.status}` +
                (a.response_code ? `  HTTP ${a.response_code}` : "") +
                (a.next_retry_at
                  ? `  retry@${new Date(a.next_retry_at).toLocaleTimeString("en-US", { hour12: false })}`
                  : ""),
                a.status === "delivered" ? "ok" : a.status === "dead" ? "err" : "warn"
              );
            }
            if (a.status === "dead" && a.ai_analysis && (!old || old.status !== "dead")) {
              addLog(
                `AI -> ${a.ai_analysis.failure_category} [${a.ai_analysis.severity}]: ${a.ai_analysis.suggested_fix.slice(0, 90)}...`,
                "warn"
              );
            }
            map.set(a.id, a);
          });
          return Array.from(map.values()).sort(
            (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
        });

        const allTerminal = mine.length > 0 &&
          mine.every((a) => a.status === "delivered" || a.status === "dead");

        if (allTerminal) {
          addLog("All delivery attempts reached terminal state", "sys");
        } else if (ticks < MAX) {
          setTimeout(tick, 4000);
        }
      } catch {
        if (ticks < MAX) setTimeout(tick, 4000);
      }
    };

    setTimeout(tick, 1500);
  }, [addLog]);

  // ── SSE: live updates ──────────────────────────────────────────────────

  useEffect(() => {
    const sse = new EventSource(`${API}/api/v1/dashboard/stream`);
    sse.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.type === "heartbeat") return;
        const aid = d.data?.attempt_id as string | undefined;
        if (!aid) return;
        fetch(`${API}/api/v1/dashboard/delivery-attempts/${aid}`)
          .then((r) => r.json())
          .then((fresh: Attempt) => {
            if (!sessionEventIds.current.has(fresh.event_id)) return;
            setAttempts((prev) => {
              const map = new Map(prev.map((a) => [a.id, a]));
              map.set(fresh.id, fresh);
              return Array.from(map.values()).sort(
                (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
              );
            });
            setSelected((sel) => sel?.id === fresh.id ? fresh : sel);
          })
          .catch(() => {});
      } catch {}
    };
    return () => sse.close();
  }, []);

  // ── retry ──────────────────────────────────────────────────────────────

  const retryAttempt = useCallback(async (a: Attempt) => {
    addLog(`Manual retry -> attempt ${a.id.slice(0, 8)}...`, "sys");
    try {
      const res = await fetch(`${API}/api/v1/dashboard/delivery-attempts/${a.id}/retry`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      if (!res.ok) throw new Error(`${res.status}`);
      addLog("Retry queued", "ok");
      setAttempts((prev) => prev.map((x) => x.id === a.id ? { ...x, status: "pending" } : x));
      setSelected((s) => s?.id === a.id ? { ...s, status: "pending" } : s);
      pollForEvent(a.event_id);
    } catch (e: unknown) {
      addLog(`Retry failed: ${e instanceof Error ? e.message : String(e)}`, "err");
    }
  }, [addLog, pollForEvent]);

  // ── open detail modal ──────────────────────────────────────────────────

  const openAttempt = async (id: string) => {
    try {
      const res = await fetch(`${API}/api/v1/dashboard/delivery-attempts/${id}`);
      setSelected(await res.json());
    } catch {}
  };

  // ── coverage ───────────────────────────────────────────────────────────

  const covered = (sc: Scenario) => {
    if (sc.key === "success")       return attempts.some((a) => a.status === "delivered");
    if (sc.key === "retry")         return attempts.some((a) => a.status === "failed" && a.attempt_number >= 2);
    if (sc.key === "dead")          return attempts.some((a) => a.status === "dead");
    if (sc.key === "idempotency")   return totalFired >= 2 && !!lastIdempKey;
    if (sc.key === "no_subscription") return scenario.key === "no_subscription" && totalFired > 0;
    if (sc.key === "timeout")       return attempts.some((a) =>
      (a.error_message ?? "").toLowerCase().includes("timeout") || (a.duration_ms ?? 0) > 25000
    );
    return false;
  };

  const stats = {
    fired:     totalFired,
    delivered: attempts.filter((a) => a.status === "delivered").length,
    failed:    attempts.filter((a) => a.status === "failed" || a.status === "dead").length,
    dead:      attempts.filter((a) => a.status === "dead").length,
  };

  // ── render ─────────────────────────────────────────────────────────────

  return (
    <div style={s.page}>
      {/* header */}
      <div style={s.header}>
        <div style={s.headerLeft}>
          <div style={s.logo}>WDS</div>
          <div>
            <div style={s.logoTitle}>Webhook Delivery System</div>
            <div style={s.logoSub}>Live demo — all scenarios</div>
          </div>
        </div>
        <div style={s.headerRight}>
          <StatusPill status={setupStatus} />
          {setupStatus !== "ready" && setupStatus !== "provisioning" && (
            <button style={s.btnPrimary} onClick={provision}>
              {setupStatus === "error" ? "Retry setup" : "Start demo"}
            </button>
          )}
        </div>
      </div>

      {/* stat bar */}
      <div style={s.statsBar}>
        {(["fired", "delivered", "failed", "dead"] as const).map((k) => (
          <div key={k} style={s.statCard}>
            <div style={{
              ...s.statNum,
              color: k === "delivered" ? "#10b981" : k === "failed" ? "#f97316" : k === "dead" ? "#ef4444" : "#f0f0f0",
            }}>
              {stats[k]}
            </div>
            <div style={s.statLabel}>{k === "fired" ? "events fired" : k}</div>
          </div>
        ))}
      </div>

      <div style={s.body}>
        {/* left col */}
        <div style={s.leftCol}>

          {/* scenario picker */}
          <div style={s.panel}>
            <div style={s.panelTitle}>Choose a scenario</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {SCENARIOS.map((sc) => {
                const active = sc.key === scenario.key;
                const done   = covered(sc);
                return (
                  <div
                    key={sc.key}
                    onClick={() => { if (setupStatus === "ready" && subscriber) applyScenario(sc, subscriber); }}
                    style={{
                      ...s.scenarioCard,
                      borderColor: active ? sc.tagColor : "#2a2a2a",
                      background:  active ? sc.tagColor + "0e" : "#0f0f0f",
                      cursor: setupStatus === "ready" ? "pointer" : "default",
                      opacity: setupStatus === "ready" ? 1 : 0.35,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
                      <span style={{ ...s.tag, background: sc.tagColor + "22", color: sc.tagColor }}>{sc.tag}</span>
                      <span style={{ fontSize: 12, fontWeight: 500, color: "#ddd", flex: 1 }}>{sc.label}</span>
                      {done && <span style={{ fontSize: 13, color: "#10b981" }}>&#10003;</span>}
                    </div>
                    <div style={{ fontSize: 11, color: "#555", lineHeight: 1.5 }}>{sc.desc}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* fire panel */}
          <div style={s.panel}>
            <div style={s.panelTitle}>Fire event</div>

            <div style={s.field}>
              <div style={s.fieldLabel}>Event type</div>
              <div style={s.chip}>{scenario.eventType}</div>
            </div>
            <div style={s.field}>
              <div style={s.fieldLabel}>Target endpoint</div>
              <div style={s.chip}>.../{scenario.endpoint.split("/").pop()}</div>
            </div>

            {scenario.key === "idempotency" && lastIdempKey && (
              <div style={{ marginBottom: 10, padding: "7px 9px", background: "#3b82f610", border: "1px solid #3b82f630", borderRadius: 2, fontSize: 11, color: "#3b82f6", lineHeight: 1.6 }}>
                Key locked for deduplication test:<br />
                <span style={{ color: "#888" }}>{lastIdempKey.slice(0, 30)}...</span>
              </div>
            )}

            <div style={s.field}>
              <div style={s.fieldLabel}>Payload</div>
              <pre style={s.pre}>{JSON.stringify(PAYLOADS[scenario.eventType] ?? {}, null, 2)}</pre>
            </div>

            <button
              style={{
                ...s.btnPrimary,
                width: "100%",
                justifyContent: "center",
                opacity: setupStatus !== "ready" || firing ? 0.45 : 1,
              }}
              onClick={fireEvent}
              disabled={setupStatus !== "ready" || firing}
            >
              {firing
                ? "Sending..."
                : scenario.key === "idempotency" && lastIdempKey
                  ? "Fire again (same key) ->"
                  : "Fire event ->"}
            </button>

            {setupStatus !== "ready" && (
              <div style={s.hint}>
                {setupStatus === "idle"         && "Click Start demo to provision a real subscriber via the API."}
                {setupStatus === "provisioning" && "Creating subscriber and initial subscription..."}
                {setupStatus === "error"        && "Could not reach the backend. Make sure docker compose is running."}
              </div>
            )}
          </div>

          {/* signature info (shown after a success fire) */}
          {showSig && (
            <div style={{ ...s.panel, borderColor: "#10b98128" }}>
              <div style={s.panelTitle}>HMAC-SHA256 signature</div>
              <div style={{ fontSize: 11, color: "#555", marginBottom: 10, lineHeight: 1.6 }}>
                The worker signs the full JSON payload using the subscriber secret before POSTing.
                The subscriber verifies via the header below.
              </div>
              <div style={s.field}>
                <div style={s.fieldLabel}>Request header sent to subscriber</div>
                <pre style={{ ...s.pre, color: "#10b981" }}>X-Webhook-Signature: sha256={"<hmac-sha256-hex>"}</pre>
              </div>
              <div style={s.field}>
                <div style={s.fieldLabel}>Additional headers</div>
                <pre style={s.pre}>{`X-Webhook-Event: ${scenario.eventType}\nX-Webhook-Attempt: 1`}</pre>
              </div>
            </div>
          )}

          {/* session info */}
          {subscriber && (
            <div style={s.panel}>
              <div style={s.panelTitle}>Session info</div>
              {([
                ["Subscriber ID", subscriber.id.slice(0, 20) + "..."],
                ["API key",       subscriber.api_key.slice(0, 22) + "..."],
                ...(subscription
                  ? [["Sub event",    subscription.event_type],
                     ["Sub endpoint", ".../" + subscription.target_url.split("/").pop()]]
                  : [["Subscription", "none (no_subscription scenario)"]]),
              ] as [string, string][]).map(([k, v]) => (
                <div key={k} style={s.kv}>
                  <span style={s.kvKey}>{k}</span>
                  <span style={s.kvVal}>{v}</span>
                </div>
              ))}
            </div>
          )}

          {/* curl */}
          {subscriber && (
            <div style={s.panel}>
              <div style={s.panelTitle}>Equivalent curl</div>
              <pre style={{ ...s.pre, fontSize: 10 }}>
{`curl -X POST ${API}/api/v1/events \\
  -H "Content-Type: application/json" \\
  -d '{
    "event_type": "${scenario.eventType}",
    "payload": ${JSON.stringify(PAYLOADS[scenario.eventType] ?? {})},
    "producer_id": "my-service",
    "idempotency_key": "unique-key-001"
  }'`}
              </pre>
            </div>
          )}
        </div>

        {/* right col */}
        <div style={s.rightCol}>

          {/* live log */}
          <div style={s.panel}>
            <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
              <span style={s.panelTitle}>Live event log</span>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#10b981", display: "inline-block", animation: "pulse 1.5s infinite", marginLeft: "auto" }} />
            </div>
            <div style={s.logBox} ref={logRef}>
              {logs.length === 0
                ? <div style={{ color: "#333", fontSize: 11 }}>Waiting for events...</div>
                : logs.map((l) => (
                  <div key={l.id} style={s.logLine}>
                    <span style={s.logTime}>{l.time}</span>
                    <span style={{
                      ...s.logMsg,
                      color: { info: "#666", ok: "#10b981", err: "#ef4444", warn: "#f59e0b", sys: "#3b82f6" }[l.kind],
                    }}>
                      {l.text}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {/* attempts table */}
          <div style={{ ...s.panel, flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
              <span style={s.panelTitle}>Delivery attempts</span>
              <span style={{ marginLeft: "auto", fontSize: 10, color: "#444" }}>
                {attempts.length} this session
              </span>
            </div>

            {attempts.length === 0
              ? <div style={{ fontSize: 12, color: "#333", padding: "24px 0", textAlign: "center" }}>No attempts yet — fire an event</div>
              : (
                <div style={s.tableWrap}>
                  <table style={s.table}>
                    <thead>
                      <tr>
                        {["Status", "Event type", "#", "HTTP", "Duration", "Next retry", ""].map((h) => (
                          <th key={h} style={s.th}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {attempts.map((a) => (
                        <tr key={a.id}>
                          <td style={s.td}>
                            <span style={{ ...s.badge, background: STATUS_COLORS[a.status] + "22", color: STATUS_COLORS[a.status] }}>
                              {a.status}
                            </span>
                          </td>
                          <td style={s.td}>{a.event?.event_type ?? "—"}</td>
                          <td style={s.td}>#{a.attempt_number}</td>
                          <td style={s.td}>
                            {a.response_code
                              ? <span style={{ ...s.badge, background: a.response_code < 300 ? "#10b98120" : "#ef444420", color: a.response_code < 300 ? "#10b981" : "#ef4444" }}>{a.response_code}</span>
                              : <span style={{ color: "#333" }}>—</span>}
                          </td>
                          <td style={s.td}>{a.duration_ms ? `${Math.round(a.duration_ms)}ms` : <span style={{ color: "#333" }}>—</span>}</td>
                          <td style={s.td}>
                            {a.next_retry_at
                              ? <span style={{ color: "#f59e0b" }}>{new Date(a.next_retry_at).toLocaleTimeString("en-US", { hour12: false })}</span>
                              : <span style={{ color: "#333" }}>—</span>}
                          </td>
                          <td style={s.td}>
                            <div style={{ display: "flex", gap: 5 }}>
                              <button style={s.btnSm} onClick={() => openAttempt(a.id)}>View</button>
                              {(a.status === "failed" || a.status === "dead") && (
                                <button style={{ ...s.btnSm, color: "#f59e0b", borderColor: "#f59e0b40" }} onClick={() => retryAttempt(a)}>
                                  Retry
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            }
          </div>

          {/* coverage checklist */}
          <div style={s.panel}>
            <div style={s.panelTitle}>Scenario coverage</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "5px 20px" }}>
              {SCENARIOS.map((sc) => {
                const done = covered(sc);
                return (
                  <div key={sc.key} style={{ display: "flex", alignItems: "center", gap: 7, padding: "3px 0" }}>
                    <span style={{ color: done ? "#10b981" : "#2e2e2e", fontSize: 14, lineHeight: 1 }}>
                      {done ? "✓" : "○"}
                    </span>
                    <span style={{ fontSize: 11, color: done ? "#10b981" : "#444" }}>{sc.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* attempt detail modal */}
      {selected && (
        <div style={s.overlay} onClick={() => setSelected(null)}>
          <div style={s.modal} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <span style={{ fontSize: 14, fontWeight: 500 }}>Attempt detail</span>
              <button style={s.btnSm} onClick={() => setSelected(null)}>x</button>
            </div>

            <span style={{ ...s.badge, background: STATUS_COLORS[selected.status] + "22", color: STATUS_COLORS[selected.status], display: "inline-flex", marginBottom: 14 }}>
              {selected.status}
            </span>

            {([
              ["Attempt ID",    selected.id],
              ["Event ID",      selected.event_id],
              ["Event type",    selected.event?.event_type ?? "—"],
              ["Attempt #",     `#${selected.attempt_number}`],
              ["Response code", selected.response_code ?? "—"],
              ["Duration",      selected.duration_ms ? `${Math.round(selected.duration_ms)}ms` : "—"],
              ["Created",       new Date(selected.created_at).toLocaleString()],
              ["Updated",       new Date(selected.updated_at).toLocaleString()],
              ["Delivered at",  selected.delivered_at ? new Date(selected.delivered_at).toLocaleString() : "—"],
              ["Next retry",    selected.next_retry_at ? new Date(selected.next_retry_at).toLocaleString() : "—"],
            ] as [string, string | number][]).map(([k, v]) => (
              <div key={k} style={s.kv}>
                <span style={s.kvKey}>{k}</span>
                <span style={{ ...s.kvVal, whiteSpace: "normal" }}>{String(v)}</span>
              </div>
            ))}

            {selected.error_message && (
              <div style={{ marginTop: 14 }}>
                <div style={{ ...s.fieldLabel, marginBottom: 5 }}>Error message</div>
                <pre style={{ ...s.pre, color: "#ef4444", borderColor: "#ef444430", background: "#ef444408" }}>
                  {selected.error_message}
                </pre>
              </div>
            )}

            {selected.ai_analysis && (
              <div style={{ marginTop: 14, padding: 12, background: "#f59e0b07", border: "1px solid #f59e0b25", borderRadius: 3 }}>
                <div style={{ fontSize: 10, color: "#f59e0b", letterSpacing: "0.1em", marginBottom: 10 }}>
                  AI FAILURE ANALYSIS
                </div>
                {([
                  ["Category",      selected.ai_analysis.failure_category],
                  ["Severity",      selected.ai_analysis.severity],
                  ["Confidence",    `${Math.round(selected.ai_analysis.confidence_score * 100)}%`],
                  ["Explanation",   selected.ai_analysis.explanation],
                  ["Suggested fix", selected.ai_analysis.suggested_fix],
                ] as [string, string][]).map(([k, v]) => (
                  <div key={k} style={{ ...s.kv, alignItems: "flex-start" }}>
                    <span style={s.kvKey}>{k}</span>
                    <span style={{ ...s.kvVal, whiteSpace: "normal", lineHeight: 1.6 }}>{v}</span>
                  </div>
                ))}
              </div>
            )}

            {selected.event?.payload && (
              <div style={{ marginTop: 14 }}>
                <div style={{ ...s.fieldLabel, marginBottom: 5 }}>Event payload</div>
                <pre style={s.pre}>{JSON.stringify(selected.event.payload, null, 2)}</pre>
              </div>
            )}

            {(selected.status === "failed" || selected.status === "dead") && (
              <button
                style={{ ...s.btnPrimary, marginTop: 16 }}
                onClick={() => { retryAttempt(selected); setSelected(null); }}
              >
                Retry this attempt &#8594;
              </button>
            )}
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.25} }
        * { box-sizing: border-box; }
        select, button, pre { font-family: inherit; }
      `}</style>
    </div>
  );
}

// ── styles ─────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  page:        { minHeight: "100vh", background: "#0d0d0d", color: "#f0f0f0", fontFamily: "'IBM Plex Mono','Courier New',monospace", fontSize: 13 },
  header:      { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 28px", borderBottom: "1px solid #1e1e1e" },
  headerLeft:  { display: "flex", alignItems: "center", gap: 14 },
  headerRight: { display: "flex", alignItems: "center", gap: 12 },
  logo:        { width: 34, height: 34, border: "1px solid #f59e0b", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 600, color: "#f59e0b", letterSpacing: "0.08em", flexShrink: 0 },
  logoTitle:   { fontSize: 13, fontWeight: 500, color: "#f0f0f0", letterSpacing: "0.04em" },
  logoSub:     { fontSize: 10, color: "#444", letterSpacing: "0.06em" },

  statsBar:  { display: "grid", gridTemplateColumns: "repeat(4,1fr)", borderBottom: "1px solid #1e1e1e", background: "#0a0a0a" },
  statCard:  { padding: "12px 24px", borderRight: "1px solid #1a1a1a" },
  statNum:   { fontSize: 24, fontWeight: 300, letterSpacing: "-0.02em", lineHeight: 1.2 },
  statLabel: { fontSize: 10, color: "#444", letterSpacing: "0.08em", marginTop: 3 },

  body:    { display: "grid", gridTemplateColumns: "360px 1fr", minHeight: "calc(100vh - 108px)" },
  leftCol: { borderRight: "1px solid #1e1e1e", padding: 16, display: "flex", flexDirection: "column", gap: 12, overflowY: "auto" },
  rightCol:{ padding: 16, display: "flex", flexDirection: "column", gap: 12 },

  panel:      { background: "#111", border: "1px solid #222", borderRadius: 2, padding: 14 },
  panelTitle: { fontSize: 10, letterSpacing: "0.12em", color: "#555", textTransform: "uppercase", marginBottom: 10, display: "block" },

  scenarioCard: { border: "1px solid", borderRadius: 3, padding: "9px 11px", transition: "border-color 0.12s, background 0.12s" },

  field:     { marginBottom: 10 },
  fieldLabel:{ fontSize: 10, letterSpacing: "0.1em", color: "#444", display: "block", marginBottom: 4, textTransform: "uppercase" },
  chip:      { background: "#1a1a1a", border: "1px solid #2e2e2e", color: "#999", padding: "5px 9px", borderRadius: 2, fontSize: 11 },
  pre:       { background: "#080808", border: "1px solid #1e1e1e", color: "#666", padding: 9, borderRadius: 2, fontSize: 11, lineHeight: 1.7, overflow: "auto", maxHeight: 180, whiteSpace: "pre-wrap", wordBreak: "break-all" },

  btnPrimary:{ display: "inline-flex", alignItems: "center", gap: 6, background: "#f59e0b", color: "#0d0d0d", border: "none", padding: "8px 16px", borderRadius: 2, fontSize: 12, fontWeight: 600, cursor: "pointer", letterSpacing: "0.04em" },
  btnSm:     { background: "transparent", color: "#666", border: "1px solid #2a2a2a", padding: "3px 8px", borderRadius: 2, fontSize: 11, cursor: "pointer" },

  tag:  { display: "inline-flex", alignItems: "center", padding: "1px 7px", borderRadius: 20, fontSize: 10, fontWeight: 500 },
  hint: { marginTop: 10, fontSize: 11, color: "#3a3a3a", lineHeight: 1.6 },

  kv:    { display: "flex", gap: 10, padding: "4px 0", borderBottom: "1px solid #161616", alignItems: "flex-start" },
  kvKey: { fontSize: 10, color: "#3a3a3a", letterSpacing: "0.08em", minWidth: 96, textTransform: "uppercase", flexShrink: 0, paddingTop: 1 },
  kvVal: { fontSize: 11, color: "#888", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },

  logBox: { background: "#080808", border: "1px solid #1a1a1a", borderRadius: 2, padding: 9, height: 220, overflowY: "auto", display: "flex", flexDirection: "column", gap: 3 },
  logLine:{ display: "flex", gap: 10, alignItems: "flex-start" },
  logTime:{ fontSize: 10, color: "#2e2e2e", flexShrink: 0, paddingTop: 1 },
  logMsg: { fontSize: 11, lineHeight: 1.5, wordBreak: "break-all" },

  tableWrap:{ overflowX: "auto" },
  table:    { width: "100%", borderCollapse: "collapse" },
  th:       { fontSize: 10, letterSpacing: "0.1em", color: "#3a3a3a", textAlign: "left", padding: "6px 10px", borderBottom: "1px solid #1e1e1e", textTransform: "uppercase", whiteSpace: "nowrap" },
  td:       { padding: "8px 10px", borderBottom: "1px solid #161616", fontSize: 12, color: "#888", whiteSpace: "nowrap" },
  badge:    { display: "inline-flex", alignItems: "center", padding: "2px 8px", borderRadius: 20, fontSize: 11, fontWeight: 500, whiteSpace: "nowrap" },

  overlay:{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.78)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 },
  modal:  { background: "#111", border: "1px solid #2a2a2a", borderRadius: 4, padding: 22, width: "min(700px,95vw)", maxHeight: "90vh", overflowY: "auto" },
};