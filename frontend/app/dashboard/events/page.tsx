"use client";
import { useEffect, useState } from "react";
import { api, Event } from "@/lib/api";

export default function EventsPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.get("/api/v1/events?limit=50")
      .then(setEvents)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = events.filter(
    (e) =>
      !search ||
      e.event_type.toLowerCase().includes(search.toLowerCase()) ||
      e.producer_id.toLowerCase().includes(search.toLowerCase()) ||
      e.idempotency_key.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      {/* Header */}
      <div style={{
        padding: "20px 28px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <h1 style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Events</h1>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{events.length} total</span>
        </div>
        <input
          className="input"
          style={{ width: 240 }}
          placeholder="Search events..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Table */}
      <div style={{ padding: 28 }}>
        {loading ? (
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading...</div>
        ) : (
          <div className="card" style={{ overflow: "hidden" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Event Type</th>
                  <th>Producer ID</th>
                  <th>Idempotency Key</th>
                  <th>Payload Preview</th>
                  <th>Ingested</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((e) => (
                  <tr key={e.id}>
                    <td>
                      <span className="tag tag-amber">{e.event_type}</span>
                    </td>
                    <td style={{ color: "var(--text-secondary)" }}>{e.producer_id}</td>
                    <td style={{ color: "var(--text-muted)", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {e.idempotency_key}
                    </td>
                    <td style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", color: "var(--text-muted)" }}>
                      {JSON.stringify(e.payload).slice(0, 60)}…
                    </td>
                    <td style={{ color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                      {new Date(e.created_at).toLocaleString("en-US", {
                        month: "short", day: "2-digit",
                        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
                      })}
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
                      {search ? "No events match your search." : "No events ingested yet."}
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