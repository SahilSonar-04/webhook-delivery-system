"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DashboardStats, DeliveryAttempt } from "@/lib/api";

const statusColors: Record<string, string> = {
  delivered: "bg-green-500",
  failed: "bg-red-500",
  pending: "bg-yellow-500",
  delivering: "bg-blue-500",
  dead: "bg-gray-500",
};

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);
  const [liveEvents, setLiveEvents] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, attemptsData] = await Promise.all([
          api.get("/api/v1/dashboard/stats"),
          api.get("/api/v1/dashboard/delivery-attempts?limit=10"),
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

    // SSE for live events
    const sse = new EventSource("http://localhost:8000/api/v1/dashboard/stream");
    sse.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type !== "heartbeat") {
        setLiveEvents((prev) => [`${new Date().toLocaleTimeString()} — ${data.type}: ${JSON.stringify(data.data).slice(0, 80)}`, ...prev.slice(0, 19)]);
      }
    };

    return () => {
      clearInterval(interval);
      sse.close();
    };
  }, []);

  if (loading) return <div className="flex items-center justify-center min-h-screen text-gray-400">Loading...</div>;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Webhook Dashboard</h1>
          <div className="flex gap-3">
            <Link href="/dashboard/events" className="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm">Events</Link>
            <Link href="/dashboard/attempts" className="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm">Attempts</Link>
            <Link href="/dashboard/dead-letter" className="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm">Dead Letter</Link>
            <Link href="/dashboard/subscribers" className="bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm">Subscribers</Link>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            {[
              { label: "Total", value: stats.total_events, color: "text-white" },
              { label: "Delivered", value: stats.delivered, color: "text-green-400" },
              { label: "Failed", value: stats.failed, color: "text-red-400" },
              { label: "Pending", value: stats.pending, color: "text-yellow-400" },
              { label: "Dead", value: stats.dead, color: "text-gray-400" },
            ].map((s) => (
              <div key={s.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
                <p className="text-gray-500 text-sm">{s.label}</p>
                <p className={`text-3xl font-bold ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Attempts */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <h2 className="font-semibold mb-4 text-gray-300">Recent Delivery Attempts</h2>
            <div className="space-y-2">
              {attempts.map((a) => (
                <Link key={a.id} href={`/dashboard/attempts/${a.id}`}>
                  <div className="flex items-center justify-between p-3 bg-gray-800 rounded-lg hover:bg-gray-750 cursor-pointer">
                    <div className="flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${statusColors[a.status] || "bg-gray-500"}`} />
                      <div>
                        <p className="text-sm font-medium">{a.event?.event_type || "unknown"}</p>
                        <p className="text-xs text-gray-500">{new Date(a.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">#{a.attempt_number}</span>
                      <span className={`text-xs px-2 py-1 rounded-full ${statusColors[a.status]} bg-opacity-20 text-${a.status === "delivered" ? "green" : a.status === "failed" || a.status === "dead" ? "red" : "yellow"}-400`}>
                        {a.status}
                      </span>
                    </div>
                  </div>
                </Link>
              ))}
              {attempts.length === 0 && <p className="text-gray-500 text-sm text-center py-4">No delivery attempts yet</p>}
            </div>
          </div>

          {/* Live Events Feed */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <h2 className="font-semibold text-gray-300">Live Event Stream</h2>
            </div>
            <div className="space-y-1 font-mono text-xs">
              {liveEvents.length === 0 && <p className="text-gray-500 text-center py-4">Waiting for events...</p>}
              {liveEvents.map((e, i) => (
                <div key={i} className="text-gray-400 p-2 bg-gray-800 rounded truncate">{e}</div>
              ))}
            </div>
          </div>
        </div>

        {/* Success Rate */}
        {stats && (
          <div className="mt-6 bg-gray-900 rounded-xl border border-gray-800 p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-gray-400 text-sm">Success Rate</span>
              <span className="text-green-400 font-bold">{stats.success_rate}%</span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-2">
              <div className="bg-green-500 h-2 rounded-full transition-all" style={{ width: `${stats.success_rate}%` }} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
