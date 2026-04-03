"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, DeliveryAttempt } from "@/lib/api";
import { use } from "react";

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

  if (loading) return <div className="flex items-center justify-center min-h-screen text-gray-400">Loading...</div>;
  if (!attempt) return <div className="flex items-center justify-center min-h-screen text-gray-400">Not found</div>;

  const severityColors: Record<string, string> = {
    low: "text-green-400", medium: "text-yellow-400",
    high: "text-orange-400", critical: "text-red-400",
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <Link href="/dashboard/attempts" className="text-gray-500 hover:text-gray-300">← Back</Link>
          <h1 className="text-2xl font-bold">Delivery Attempt Detail</h1>
        </div>

        {/* Status Card */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div><p className="text-gray-500 text-sm">Status</p><p className="font-bold text-lg capitalize">{attempt.status}</p></div>
            <div><p className="text-gray-500 text-sm">Attempt #</p><p className="font-bold text-lg">{attempt.attempt_number}</p></div>
            <div><p className="text-gray-500 text-sm">Response Code</p><p className="font-bold text-lg">{attempt.response_code || "—"}</p></div>
            <div><p className="text-gray-500 text-sm">Duration</p><p className="font-bold text-lg">{attempt.duration_ms ? `${attempt.duration_ms.toFixed(0)}ms` : "—"}</p></div>
          </div>

          {(attempt.status === "failed" || attempt.status === "dead") && (
            <button
              onClick={handleRetry}
              disabled={retrying}
              className="mt-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-4 py-2 rounded-lg text-sm"
            >
              {retrying ? "Retrying..." : "Retry Delivery"}
            </button>
          )}
        </div>

        {/* Error */}
        {attempt.error_message && (
          <div className="bg-red-950 border border-red-800 rounded-xl p-4 mb-6">
            <p className="text-red-400 text-sm font-medium mb-1">Error</p>
            <p className="text-red-300 text-sm font-mono">{attempt.error_message}</p>
          </div>
        )}

        {/* AI Analysis */}
        {attempt.ai_analysis && (
          <div className="bg-gray-900 rounded-xl border border-purple-800 p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-purple-400">🤖</span>
              <h2 className="font-semibold text-purple-400">AI Failure Analysis</h2>
              <span className={`ml-auto text-sm font-medium ${severityColors[attempt.ai_analysis.severity]}`}>
                {attempt.ai_analysis.severity.toUpperCase()}
              </span>
            </div>
            <div className="space-y-3">
              <div>
                <p className="text-gray-500 text-xs mb-1">Category</p>
                <p className="text-sm bg-gray-800 px-3 py-1 rounded inline-block">{attempt.ai_analysis.failure_category}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs mb-1">Explanation</p>
                <p className="text-sm text-gray-300">{attempt.ai_analysis.explanation}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs mb-1">Suggested Fix</p>
                <p className="text-sm text-gray-300">{attempt.ai_analysis.suggested_fix}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Confidence: {(attempt.ai_analysis.confidence_score * 100).toFixed(0)}%</p>
              </div>
            </div>
          </div>
        )}

        {/* Event Payload */}
        {attempt.event && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h2 className="font-semibold mb-4 text-gray-300">Event Payload</h2>
            <pre className="text-sm text-gray-300 bg-gray-800 p-4 rounded-lg overflow-auto">
              {JSON.stringify(attempt.event.payload, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
