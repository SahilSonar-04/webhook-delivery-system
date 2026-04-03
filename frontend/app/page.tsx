import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold mb-4">Webhook Delivery System</h1>
      <p className="text-gray-400 mb-8">Reliable async webhook delivery with AI failure analysis</p>
      <Link
        href="/dashboard"
        className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium"
      >
        Go to Dashboard
      </Link>
    </main>
  );
}
