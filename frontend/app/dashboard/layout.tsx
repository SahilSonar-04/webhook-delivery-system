"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const NAV = [
  { href: "/dashboard", label: "Overview", short: "OVR" },
  { href: "/dashboard/events", label: "Events", short: "EVT" },
  { href: "/dashboard/attempts", label: "Attempts", short: "ATT" },
  { href: "/dashboard/dead-letter", label: "Dead Letter", short: "DLQ" },
  { href: "/dashboard/subscribers", label: "Subscribers", short: "SUB" },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-base)" }}>
      {/* Sidebar */}
      <aside style={{
        width: 200,
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        position: "sticky",
        top: 0,
        height: "100vh",
        background: "var(--bg-base)",
      }}>
        {/* Logo */}
        <div style={{
          padding: "16px 20px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}>
          <div style={{
            width: 28, height: 28,
            border: "1px solid var(--amber)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 10, fontWeight: 600, color: "var(--amber)",
            letterSpacing: "0.05em",
            flexShrink: 0,
          }}>
            WDS
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 500, color: "var(--text-primary)", letterSpacing: "0.04em" }}>
              Webhook
            </div>
            <div style={{ fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.04em" }}>
              Delivery System
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ padding: "12px 0", flex: 1 }}>
          <div style={{ padding: "4px 20px 8px", fontSize: 9, letterSpacing: "0.12em", color: "var(--text-dim)", textTransform: "uppercase" }}>
            Navigation
          </div>
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "7px 20px",
                  fontSize: 12,
                  color: active ? "var(--amber)" : "var(--text-secondary)",
                  background: active ? "var(--amber-glow)" : "transparent",
                  borderLeft: active ? "2px solid var(--amber)" : "2px solid transparent",
                  transition: "all 0.1s",
                  textDecoration: "none",
                }}
              >
                <span style={{
                  fontSize: 9, fontWeight: 600,
                  letterSpacing: "0.08em",
                  color: active ? "var(--amber)" : "var(--text-muted)",
                  minWidth: 28,
                }}>
                  {item.short}
                </span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div style={{
          padding: "12px 20px",
          borderTop: "1px solid var(--border)",
          fontSize: 10,
          color: "var(--text-dim)",
          letterSpacing: "0.06em",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <span className="status-dot status-delivered" style={{ width: 5, height: 5 }} />
            SYS ONLINE
          </div>
          <div>v1.0.0</div>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, minWidth: 0, overflow: "auto" }}>
        {children}
      </main>
    </div>
  );
}