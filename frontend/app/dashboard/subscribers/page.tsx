"use client";
import { useEffect, useState } from "react";
import { api, Subscriber } from "@/lib/api";

export default function SubscribersPage() {
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    api.get("/api/v1/subscribers")
      .then(setSubscribers)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!name.trim() || !email.trim()) {
      setError("Name and email are required.");
      return;
    }
    setError(null);
    setCreating(true);
    try {
      const result = await api.post("/api/v1/subscribers", { name, email });
      setNewApiKey(result.api_key);
      setSubscribers((prev) => [result, ...prev]);
      setName("");
      setEmail("");
    } catch (e: unknown) {
      setError("Failed to create subscriber. Email may already be in use.");
    } finally {
      setCreating(false);
    }
  };

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
          <h1 style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Subscribers</h1>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{subscribers.length} registered</span>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setNewApiKey(null); setError(null); }}
          className="btn btn-primary btn-sm"
        >
          {showForm ? "Cancel" : "+ Register Subscriber"}
        </button>
      </div>

      <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Create form */}
        {showForm && (
          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
              <span className="section-label">Register New Subscriber</span>
            </div>
            <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 10, letterSpacing: "0.1em", color: "var(--text-muted)", display: "block", marginBottom: 5, textTransform: "uppercase" }}>
                    Name
                  </label>
                  <input
                    className="input"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Payments Service"
                    onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 10, letterSpacing: "0.1em", color: "var(--text-muted)", display: "block", marginBottom: 5, textTransform: "uppercase" }}>
                    Email
                  </label>
                  <input
                    className="input"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="e.g. ops@company.com"
                    onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                  />
                </div>
              </div>

              {error && (
                <div style={{ fontSize: 11, color: "var(--red)", padding: "6px 10px", background: "var(--red-glow)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "var(--radius)" }}>
                  {error}
                </div>
              )}

              <div>
                <button
                  onClick={handleCreate}
                  disabled={creating}
                  className="btn btn-primary"
                >
                  {creating ? "Creating..." : "Register"}
                </button>
              </div>

              {newApiKey && (
                <div style={{
                  padding: "12px 16px",
                  background: "var(--green-glow)",
                  border: "1px solid rgba(16,185,129,0.2)",
                  borderRadius: "var(--radius)",
                }}>
                  <div style={{ fontSize: 10, letterSpacing: "0.1em", color: "var(--green)", marginBottom: 6, textTransform: "uppercase" }}>
                    ✓ Subscriber Created — Save This API Key
                  </div>
                  <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-secondary)", wordBreak: "break-all" }}>
                    {newApiKey}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 5 }}>
                    This key will not be shown again.
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Table */}
        {loading ? (
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading...</div>
        ) : (
          <div className="card" style={{ overflow: "hidden" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Registered</th>
                </tr>
              </thead>
              <tbody>
                {subscribers.map((s) => (
                  <tr key={s.id}>
                    <td style={{ color: "var(--text-primary)", fontWeight: 400 }}>{s.name}</td>
                    <td style={{ color: "var(--text-secondary)" }}>{s.email}</td>
                    <td>
                      <span className={`tag ${s.is_active ? "tag-green" : "tag-gray"}`}>
                        {s.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td style={{ color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                      {new Date(s.created_at).toLocaleDateString("en-US", {
                        year: "numeric", month: "short", day: "2-digit"
                      })}
                    </td>
                  </tr>
                ))}
                {subscribers.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
                      No subscribers registered yet.
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