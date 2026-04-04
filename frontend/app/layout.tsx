import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WDS — Webhook Delivery System",
  description: "Reliable async webhook delivery with AI failure analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}