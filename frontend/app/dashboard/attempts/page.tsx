"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DeliveryAttempt } from "@/lib/api";

const statusColors: Record<string, string> = {
  delivered: "text-green-400",
  failed: "text-red-400",
  pending: "text-yellow-400",
  delivering: "text-blue-400",
  dead: "text-gray-400",
};

export default function AttemptsPage() {
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAttempts = async () => {
      try {
        const url = filter
          ? `/api/v1/dashboard/delivery-attempts?status=${filter}&limit=50`
          : "/api/v1/dashboard/delivery-attempts?limit=50";
        const data = await api.get(url);
        setAttempts(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchAttempts();
  }, [filter]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-300">← Back</Link>
          <h1 className="text-2xl font-bold">Delivery Attempts</h1>
        </div>

        {/* Filter */}
        <div className="flex gap-2 mb-6">
          {["", "pending", "delivering", "delivered", "failed", "dead"].map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1 rounded-lg text-sm ${filter === s ? "bg-blue-600" : "bg-gray-800 hover:bg-gray-700"}`}
            >
              {s || "All"}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="text-gray-400">Loading...</p>
        ) : (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 text-sm">
                  <th className="text-left p-4">Event Type</th>
                  <th className="text-left p-4">Status</th>
                  <th className="text-left p-4">Attempt</th>
                  <th className="text-left p-4">Response</th>
                  <th className="text-left p-4">Duration</th>
                  <th className="text-left p-4">Time</th>
                  <th className="text-left p-4"></th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((a) => (
                  <tr key={a.id} className="border-b border-gray-800 hover:bg-gray-800">
                    <td className="p-4 text-sm">{a.event?.event_type || "—"}</td>
                    <td className={`p-4 text-sm font-medium ${statusColors[a.status]}`}>{a.status}</td>
                    <td className="p-4 text-sm text-gray-400">#{a.attempt_number}</td>
                    <td className="p-4 text-sm text-gray-400">{a.response_code || "—"}</td>
                    <td className="p-4 text-sm text-gray-400">{a.duration_ms ? `${a.duration_ms.toFixed(0)}ms` : "—"}</td>
                    <td className="p-4 text-sm text-gray-400">{new Date(a.created_at).toLocaleString()}</td>
                    <td className="p-4">
                      <Link href={`/dashboard/attempts/${a.id}`} className="text-blue-400 text-sm hover:underline">View</Link>
                    </td>
                  </tr>
                ))}
                {attempts.length === 0 && (
                  <tr><td colSpan={7} className="p-8 text-center text-gray-500">No attempts found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
