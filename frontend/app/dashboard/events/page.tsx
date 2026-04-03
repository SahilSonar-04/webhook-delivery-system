"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Event } from "@/lib/api";

export default function EventsPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/v1/events?limit=50")
      .then(setEvents)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-300">← Back</Link>
          <h1 className="text-2xl font-bold">Events</h1>
          <span className="bg-gray-800 text-gray-400 text-sm px-3 py-1 rounded-full">{events.length} total</span>
        </div>

        {loading ? <p className="text-gray-400">Loading...</p> : (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 text-sm">
                  <th className="text-left p-4">Event Type</th>
                  <th className="text-left p-4">Producer</th>
                  <th className="text-left p-4">Idempotency Key</th>
                  <th className="text-left p-4">Payload</th>
                  <th className="text-left p-4">Time</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className="border-b border-gray-800 hover:bg-gray-800">
                    <td className="p-4">
                      <span className="bg-blue-900 text-blue-300 text-xs px-2 py-1 rounded">{e.event_type}</span>
                    </td>
                    <td className="p-4 text-sm text-gray-400">{e.producer_id}</td>
                    <td className="p-4 text-sm text-gray-500 font-mono">{e.idempotency_key}</td>
                    <td className="p-4 text-sm text-gray-400 max-w-xs truncate">
                      {JSON.stringify(e.payload).slice(0, 60)}...
                    </td>
                    <td className="p-4 text-sm text-gray-400">{new Date(e.created_at).toLocaleString()}</td>
                  </tr>
                ))}
                {events.length === 0 && (
                  <tr><td colSpan={5} className="p-8 text-center text-gray-500">No events yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
