"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DeliveryAttempt } from "@/lib/api";

export default function DeadLetterPage() {
  const [attempts, setAttempts] = useState<DeliveryAttempt[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDead = async () => {
    try {
      const data = await api.get("/api/v1/dashboard/dead-letter");
      setAttempts(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDead(); }, []);

  const handleRetry = async (id: string) => {
    try {
      await api.post(`/api/v1/dashboard/delivery-attempts/${id}/retry`, {});
      await fetchDead();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-300">← Back</Link>
          <h1 className="text-2xl font-bold">Dead Letter Queue</h1>
          <span className="bg-red-900 text-red-300 text-sm px-3 py-1 rounded-full">{attempts.length} items</span>
        </div>

        {loading ? <p className="text-gray-400">Loading...</p> : (
          <div className="space-y-4">
            {attempts.length === 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center text-gray-500">
                No dead letter events 🎉
              </div>
            )}
            {attempts.map((a) => (
              <div key={a.id} className="bg-gray-900 rounded-xl border border-red-900 p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium">{a.event?.event_type || "unknown"}</p>
                    <p className="text-sm text-gray-500 mt-1">Failed after {a.attempt_number} attempts</p>
                    {a.error_message && <p className="text-sm text-red-400 mt-1 font-mono">{a.error_message}</p>}
                    {a.ai_analysis && (
                      <div className="mt-2 bg-gray-800 rounded-lg p-3">
                        <p className="text-xs text-purple-400 mb-1">🤖 AI Analysis: {a.ai_analysis.failure_category}</p>
                        <p className="text-xs text-gray-400">{a.ai_analysis.suggested_fix}</p>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Link href={`/dashboard/attempts/${a.id}`} className="bg-gray-800 hover:bg-gray-700 px-3 py-1 rounded text-sm">View</Link>
                    <button onClick={() => handleRetry(a.id)} className="bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded text-sm">Retry</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
