const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  async get(path: string, headers?: Record<string, string>) {
    const res = await fetch(`${API_URL}${path}`, {
      headers: { ...headers },
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  },

  async post(path: string, body: unknown, headers?: Record<string, string>) {
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
  },
};

export type DeliveryAttempt = {
  id: string;
  event_id: string;
  subscription_id: string;
  status: "pending" | "delivering" | "delivered" | "failed" | "dead";
  attempt_number: number;
  next_retry_at: string | null;
  response_code: number | null;
  response_body: string | null;
  error_message: string | null;
  duration_ms: number | null;
  delivered_at: string | null;
  created_at: string;
  updated_at: string;
  ai_analysis?: {
    failure_category: string;
    explanation: string;
    suggested_fix: string;
    confidence_score: number;
    severity: string;
  };
  event?: {
    event_type: string;
    payload: Record<string, unknown>;
  };
};

export type DashboardStats = {
  /** Unique ingested events */
  total_events: number;
  /** Total delivery attempts across all events */
  total_attempts: number;
  delivered: number;
  failed: number;
  pending: number;
  delivering: number;
  dead: number;
  success_rate: number;
};

export type Subscriber = {
  id: string;
  name: string;
  email: string;
  is_active: boolean;
  created_at: string;
};

export type Event = {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  producer_id: string;
  idempotency_key: string;
  created_at: string;
};