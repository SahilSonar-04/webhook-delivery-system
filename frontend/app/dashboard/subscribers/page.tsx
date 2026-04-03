"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Subscriber } from "@/lib/api";

export default function SubscribersPage() {
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [newApiKey, setNewApiKey] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.get("/api/v1/subscribers")
      .then(setSubscribers)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!name || !email) return;
    setCreating(true);
    try {
      const result = await api.post("/api/v1/subscribers", { name, email });
      setNewApiKey(result.api_key);
      setSubscribers((prev) => [result, ...prev]);
      setName("");
      setEmail("");
    } catch (e) {
      console.error(e);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-300">← Back</Link>
          <h1 className="text-2xl font-bold">Subscribers</h1>
        </div>

        {/* Create Form */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
          <h2 className="font-semibold mb-4 text-gray-300">Register New Subscriber</h2>
          <div className="flex gap-3">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm flex-1 focus:outline-none focus:border-blue-500" />
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm flex-1 focus:outline-none focus:border-blue-500" />
            <button onClick={handleCreate} disabled={creating} className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-4 py-2 rounded-lg text-sm">
              {creating ? "Creating..." : "Create"}
            </button>
          </div>

          {newApiKey && (
            <div className="mt-4 bg-green-950 border border-green-800 rounded-lg p-3">
              <p className="text-green-400 text-sm font-medium mb-1">✅ API Key (save this — shown only once)</p>
              <p className="text-green-300 text-sm font-mono break-all">{newApiKey}</p>
            </div>
          )}
        </div>

        {/* List */}
        {loading ? <p className="text-gray-400">Loading...</p> : (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500 text-sm">
                  <th className="text-left p-4">Name</th>
                  <th className="text-left p-4">Email</th>
                  <th className="text-left p-4">Status</th>
                  <th className="text-left p-4">Created</th>
                </tr>
              </thead>
              <tbody>
                {subscribers.map((s) => (
                  <tr key={s.id} className="border-b border-gray-800">
                    <td className="p-4 text-sm">{s.name}</td>
                    <td className="p-4 text-sm text-gray-400">{s.email}</td>
                    <td className="p-4"><span className={`text-xs px-2 py-1 rounded-full ${s.is_active ? "bg-green-900 text-green-400" : "bg-gray-800 text-gray-400"}`}>{s.is_active ? "Active" : "Inactive"}</span></td>
                    <td className="p-4 text-sm text-gray-400">{new Date(s.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
                {subscribers.length === 0 && <tr><td colSpan={4} className="p-8 text-center text-gray-500">No subscribers yet</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
