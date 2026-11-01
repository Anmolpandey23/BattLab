"use client";
import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, FolderOpen, Library, Settings,
  ChevronRight, Activity, Cpu,
  Car, Play, Layers, BarChart2, FileText, PanelLeft, PanelLeftClose
} from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Design Dashboard", icon: LayoutDashboard },
  { href: "/library", label: "Cell Chemistry Library", icon: Library },
  { href: "/settings", label: "System Config", icon: Settings },
];

function AppLayoutInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Initialize to true on both SSR and initial client hydration to prevent any hydration mismatch
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Sync with localStorage strictly after mount (post-hydration)
  useEffect(() => {
    const syncId = requestAnimationFrame(() => {
      try {
        const val = localStorage.getItem("battlab_sidebar_open");
        if (val === "false") {
          setSidebarOpen(false);
        }
      } catch { /* ignore */ }
    });

    const handleSync = () => {
      try {
        const val = localStorage.getItem("battlab_sidebar_open");
        setSidebarOpen(val !== "false");
      } catch { /* ignore */ }
    };

    window.addEventListener("storage", handleSync);
    window.addEventListener("battlab_sidebar_change", handleSync);
    return () => {
      cancelAnimationFrame(syncId);
      window.removeEventListener("storage", handleSync);
      window.removeEventListener("battlab_sidebar_change", handleSync);
    };
  }, []);

  const toggleSidebar = () => {
    setSidebarOpen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("battlab_sidebar_open", String(next));
        window.dispatchEvent(new Event("battlab_sidebar_change"));
      } catch { /* ignore */ }
      return next;
    });
  };

  const closeSidebarOnMobile = () => {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setSidebarOpen(false);
      try {
        localStorage.setItem("battlab_sidebar_open", "false");
        window.dispatchEvent(new Event("battlab_sidebar_change"));
      } catch { /* ignore */ }
    }
  };

  // Keyboard shortcut ⌘B / Ctrl+B to toggle sidebar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#030712" }}>

      {/* ── Sidebar overlay backdrop (mobile) ── Always in DOM to prevent hydration mismatch */}
      <div
        onClick={toggleSidebar}
        className="md:hidden"
        style={{
          position: "fixed", inset: 0, zIndex: 98,
          background: "rgba(0,0,0,0.7)", backdropFilter: "blur(6px)",
          opacity: sidebarOpen ? 1 : 0,
          pointerEvents: sidebarOpen ? "auto" : "none",
          transition: "opacity 0.25s ease",
        }}
      />

      {/* ── Sidebar ── */}
      <aside
        style={{
          position: "relative",
          top: 0, left: 0, bottom: 0,
          width: sidebarOpen ? 260 : 0,
          minWidth: sidebarOpen ? 260 : 0,
          flexShrink: 0,
          flexDirection: "column",
          background: "rgba(6, 13, 26, 0.97)",
          backdropFilter: "blur(20px)",
          borderRight: sidebarOpen ? "1px solid var(--border)" : "none",
          padding: sidebarOpen ? "1.25rem 1rem" : 0,
          boxShadow: sidebarOpen ? "4px 0 24px rgba(0,0,0,0.7)" : "none",
          transition: "width 0.28s cubic-bezier(0.16,1,0.3,1), min-width 0.28s cubic-bezier(0.16,1,0.3,1), padding 0.28s cubic-bezier(0.16,1,0.3,1), transform 0.28s cubic-bezier(0.16,1,0.3,1)",
          transform: sidebarOpen ? "translateX(0)" : "translateX(-260px)",
          opacity: 1,
          pointerEvents: sidebarOpen ? "auto" : "none",
          overflow: "hidden",
          whiteSpace: "nowrap",
          zIndex: 99,
          display: "flex",
        }}
      >
        <div style={{ width: 228, display: "flex", flexDirection: "column", height: "100%", flexShrink: 0 }}>

          {/* Clean Brand Header (No cramped X/hamburger next to logo) */}
          <div style={{ display: "flex", alignItems: "center", marginBottom: "1.75rem", padding: "0 0.25rem" }}>
            <Link href="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "0.75rem", width: "100%" }}>
              <div style={{
                width: 40, height: 40, borderRadius: 9,
                background: "rgba(0, 240, 255, 0.06)",
                border: "1px solid rgba(0, 240, 255, 0.3)",
                boxShadow: "0 0 16px rgba(0, 240, 255, 0.2)",
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                padding: "2px",
              }}>
                <Image src="/logo-mark.png" alt="BattLab" width={34} height={34} style={{ objectFit: "contain" }} priority />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 800, fontSize: "1.1rem", letterSpacing: "0.06em", color: "#f8fafc", lineHeight: 1.1 }}>
                  <span style={{ color: "var(--arc-cyan)" }}>BATT</span>LAB
                </div>
                <div style={{ fontSize: "0.62rem", color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase", marginTop: "2px" }}>
                  Battery Design Software
                </div>
              </div>
            </Link>
          </div>

          {/* Engine status */}
          <div style={{
            background: "rgba(0,240,255,0.05)",
            border: "1px solid rgba(0,240,255,0.18)",
            borderRadius: 6, padding: "0.5rem 0.75rem", marginBottom: "1.5rem",
            display: "flex", alignItems: "center", gap: "0.5rem",
          }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981" }} />
            <div style={{ fontSize: "0.7rem", color: "#94a3b8", fontFamily: "monospace" }}>
              ENGINE: <span style={{ color: "#10b981", fontWeight: 700 }}>SOLVER ONLINE</span>
            </div>
          </div>

          {/* Navigation */}
          <nav style={{ display: "flex", flexDirection: "column", gap: "0.4rem", flex: 1 }}>
            <p className="section-title" style={{ padding: "0 0.5rem", marginBottom: "0.5rem" }}>Architecture</p>
            {NAV.map((item) => {
              const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
              return (
                <Link key={item.href} href={item.href} style={{ textDecoration: "none" }}>
                  <button
                    onClick={closeSidebarOnMobile}
                    style={{
                      display: "flex", alignItems: "center", gap: "0.625rem",
                      width: "100%", padding: "0.6rem 0.75rem", borderRadius: 6,
                      border: `1px solid ${active ? "var(--arc-cyan)" : "transparent"}`,
                      background: active ? "rgba(0,240,255,0.12)" : "transparent",
                      color: active ? "var(--arc-cyan)" : "var(--text-secondary)",
                      fontSize: "0.825rem", fontWeight: active ? 700 : 500,
                      cursor: "pointer", transition: "all 0.2s",
                      textAlign: "left",
                      boxShadow: active ? "0 0 12px rgba(0,240,255,0.2)" : "none",
                    }}
                  >
                    <item.icon size={17} />
                    {item.label}
                  </button>
                </Link>
              );
            })}

            <hr className="divider" style={{ margin: "1rem 0" }} />
            <p className="section-title" style={{ padding: "0 0.5rem", marginBottom: "0.5rem" }}>Projects</p>
            <Link href="/projects/new" style={{ textDecoration: "none" }}>
              <button
                onClick={closeSidebarOnMobile}
                style={{
                  display: "flex", alignItems: "center", gap: "0.625rem",
                  width: "100%", padding: "0.6rem 0.75rem", borderRadius: 6,
                  border: "1px dashed rgba(0,240,255,0.35)",
                  background: "rgba(0,240,255,0.04)",
                  color: "var(--arc-cyan)",
                  fontSize: "0.825rem", fontWeight: 600,
                  cursor: "pointer", transition: "all 0.2s",
                  textAlign: "left",
                }}
              >
                <FolderOpen size={17} />
                + New Battery Design
              </button>
            </Link>

            {/* Active Project Sub-navigation */}
            {(() => {
              const match = pathname.match(/^\/projects\/(\d+)/);
              if (!match) return null;
              const activePid = match[1];
              return (
                <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                  <hr className="divider" style={{ margin: "0.5rem 0" }} />
                  <p className="section-title" style={{ padding: "0 0.5rem", marginBottom: "0.4rem" }}>
                    Active Design #{activePid}
                  </p>
                  {[
                    { href: `/projects/${activePid}/design`, label: "3D CAD & Cell Layout", icon: Layers },
                    { href: `/projects/${activePid}/simulation`, label: "Multi-Physics Simulation", icon: Play },
                    { href: `/projects/${activePid}/vehicle-load`, label: "Vehicle Tractive Load", icon: Car },
                    { href: `/projects/${activePid}/compare`, label: "Compare Alternatives", icon: BarChart2 },
                    { href: `/projects/${activePid}/report`, label: "Engineering Report", icon: FileText },
                  ].map((item) => {
                    const active = pathname.startsWith(item.href);
                    return (
                      <Link key={item.href} href={item.href} style={{ textDecoration: "none" }}>
                        <button
                          onClick={closeSidebarOnMobile}
                          style={{
                            display: "flex", alignItems: "center", gap: "0.55rem",
                            width: "100%", padding: "0.45rem 0.65rem", borderRadius: 6,
                            border: `1px solid ${active ? "var(--arc-cyan)" : "transparent"}`,
                            background: active ? "rgba(0,240,255,0.12)" : "transparent",
                            color: active ? "var(--arc-cyan)" : "var(--text-secondary)",
                            fontSize: "0.76rem", fontWeight: active ? 700 : 500,
                            cursor: "pointer", transition: "all 0.15s",
                            textAlign: "left",
                          }}
                        >
                          <item.icon size={14} />
                          {item.label}
                        </button>
                      </Link>
                    );
                  })}
                </div>
              );
            })()}
          </nav>

          {/* Footer */}
          <div style={{
            padding: "0.875rem 0.5rem 1.5rem",
            borderTop: "1px solid var(--border-subtle)",
            marginTop: "auto",
            fontFamily: "monospace",
            fontSize: "0.68rem",
            color: "var(--text-muted)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
              <span>SOLVER STATUS</span>
              <span style={{ color: "#10b981" }}>READY</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>ENGINE VERSION</span>
              <span>v2.4.0</span>
            </div>

            {/* Collapse sidebar action in footer */}
            <button
              onClick={toggleSidebar}
              style={{
                width: "100%",
                marginTop: "0.75rem",
                padding: "0.5rem 0.65rem",
                borderRadius: 6,
                background: "rgba(0, 240, 255, 0.05)",
                border: "1px solid rgba(0, 240, 255, 0.15)",
                color: "var(--text-secondary)",
                fontSize: "0.72rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(0, 240, 255, 0.12)";
                e.currentTarget.style.color = "var(--arc-cyan)";
                e.currentTarget.style.borderColor = "var(--arc-cyan)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(0, 240, 255, 0.05)";
                e.currentTarget.style.color = "var(--text-secondary)";
                e.currentTarget.style.borderColor = "rgba(0, 240, 255, 0.15)";
              }}
              title="Collapse sidebar (⌘B)"
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <PanelLeftClose size={13} />
                <span>Collapse Panel</span>
              </div>
              <span style={{ fontSize: "0.62rem", padding: "1px 5px", borderRadius: 3, background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)" }}>
                ⌘B
              </span>
            </button>
          </div>

        </div>
      </aside>

      {/* ── Main viewport ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: "#030712" }}>

        {/* Top header bar */}
        <header style={{
          height: 56, flexShrink: 0,
          borderBottom: "1px solid var(--border)",
          background: "rgba(6, 13, 26, 0.9)",
          backdropFilter: "blur(16px)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 1.5rem",
          zIndex: 40,
        }}>
          {/* Left: Brand (when sidebar collapsed) + Sidebar toggle + breadcrumb */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            {/* Docked brand logo when sidebar is closed */}
            {!sidebarOpen && (
              <Link href="/" className="hidden md:flex" style={{ textDecoration: "none", alignItems: "center", gap: "0.55rem", paddingRight: "0.5rem" }}>
                <div style={{
                  width: 30, height: 30, borderRadius: 7,
                  background: "rgba(0, 240, 255, 0.06)",
                  border: "1px solid rgba(0, 240, 255, 0.3)",
                  boxShadow: "0 0 12px rgba(0, 240, 255, 0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  padding: "2px",
                }}>
                  <Image src="/logo-mark.png" alt="BattLab" width={24} height={24} style={{ objectFit: "contain" }} />
                </div>
                <span style={{ fontWeight: 800, fontSize: "0.95rem", color: "#f8fafc", letterSpacing: "0.04em" }}>
                  <span style={{ color: "var(--arc-cyan)" }}>BATT</span>LAB
                </span>
              </Link>
            )}

            {/* Modern, streamlined Sidebar Toggle */}
            <button
              onClick={toggleSidebar}
              aria-label={sidebarOpen ? "Collapse sidebar (⌘B)" : "Expand sidebar (⌘B)"}
              title={sidebarOpen ? "Collapse sidebar (⌘B)" : "Expand sidebar (⌘B)"}
              style={{
                width: 32, height: 32, borderRadius: 6,
                background: "rgba(0, 240, 255, 0.06)",
                border: "1px solid rgba(0, 240, 255, 0.18)",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: sidebarOpen ? "var(--text-secondary)" : "var(--arc-cyan)",
                cursor: "pointer",
                transition: "all 0.18s ease",
                flexShrink: 0,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(0,240,255,0.14)";
                e.currentTarget.style.borderColor = "var(--arc-cyan)";
                e.currentTarget.style.color = "var(--arc-cyan)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(0,240,255,0.06)";
                e.currentTarget.style.borderColor = "rgba(0,240,255,0.18)";
                e.currentTarget.style.color = sidebarOpen ? "var(--text-secondary)" : "var(--arc-cyan)";
              }}
            >
              {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeft size={16} />}
            </button>

            <div style={{ width: 1, height: 16, background: "rgba(0,240,255,0.15)", margin: "0 0.15rem" }} />

            <Breadcrumb pathname={pathname} />
          </div>

          {/* Right: Status badges */}
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <div className="hidden sm:flex" style={{
              alignItems: "center", gap: "0.5rem",
              background: "rgba(16,185,129,0.08)",
              border: "1px solid rgba(16,185,129,0.25)",
              borderRadius: 20, padding: "0.3rem 0.75rem",
              fontSize: "0.72rem", fontFamily: "monospace", color: "#10b981",
            }}>
              <Activity size={12} className="animate-pulse" />
              <span>SIMULATION SOLVER: ACTIVE</span>
            </div>

            <Link href="/" style={{ textDecoration: "none" }}>
              <button className="btn-secondary" style={{ padding: "0.35rem 0.75rem", fontSize: "0.75rem" }}>
                <Cpu size={13} color="var(--arc-cyan)" />
                <span>Overview Portal</span>
              </button>
            </Link>
          </div>
        </header>

        {/* Content body */}
        <main style={{ flex: 1, overflow: "auto", padding: "1.5rem", background: "#030712" }}>
          {children}
        </main>
      </div>
    </div>
  );
}

function Breadcrumb({ pathname }: { pathname: string }) {
  const parts = pathname.split("/").filter(Boolean);
  if (!parts.length) return <span style={{ color: "var(--arc-cyan)", fontWeight: 700, fontSize: "0.85rem", letterSpacing: "0.04em" }}>DASHBOARD</span>;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
      <Link href="/dashboard" style={{ color: "var(--text-muted)", textDecoration: "none" }}>MAIN</Link>
      {parts.map((p, i) => {
        const isLast = i === parts.length - 1;
        return (
          <span key={i} style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
            <ChevronRight size={12} />
            <span style={{
              color: isLast ? "var(--text-primary)" : "var(--text-muted)",
              fontWeight: isLast ? 700 : 400,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              fontFamily: "monospace",
            }}>
              {p}
            </span>
          </span>
        );
      })}
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#030712", color: "var(--arc-cyan)" }}>
        <div className="spinner" style={{ width: 36, height: 36 }} />
      </div>
    }>
      <AppLayoutInner>{children}</AppLayoutInner>
    </Suspense>
  );
}
