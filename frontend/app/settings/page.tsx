"use client";
import AppLayout from "@/components/layout/AppLayout";
import { Activity, ShieldAlert, Wrench } from "lucide-react";

export default function SettingsPage() {
  return (
    <AppLayout>
      <div style={{ maxWidth: 780, margin: "0 auto" }} className="fade-in">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
          <Wrench size={20} color="var(--arc-cyan)" />
          <h1 style={{ fontSize: "1.65rem", fontWeight: 800, letterSpacing: "-0.02em" }}>System Configuration</h1>
        </div>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.75rem", fontFamily: "monospace" }}>
          ENVIRONMENT &amp; SOLVER CONFIGURATION // BATTLAB
        </p>

        {/* API Connection */}
        <div className="card hud-bracket" style={{ marginBottom: "1.5rem" }}>
          <p className="section-title">Backend Simulation API Gateway</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "0.875rem", alignItems: "end" }}>
            <div className="field">
              <label className="label">Uvicorn API Endpoint</label>
              <input className="input" readOnly value={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"} />
            </div>
            <button className="btn-secondary" style={{ whiteSpace: "nowrap" }}
              onClick={() => fetch((process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api") + "/health").then(r => r.json()).then(d => alert(`BattLab Gateway Status: ${d.status.toUpperCase()} · API v${d.version}`)).catch(() => alert("Gateway offline — ensure FastAPI daemon is running."))}>
              <Activity size={14} /> Ping Gateway
            </button>
          </div>
        </div>

        {/* System Specifications */}
        <div className="card hud-bracket" style={{ marginBottom: "1.5rem" }}>
          <p className="section-title">BattLab Engineering Platform Architecture</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", fontSize: "0.85rem", fontFamily: "monospace" }}>
            {[
              ["System Identifier", "BattLab Professional Virtual Battery Lab"],
              ["Runtime Framework", "Next.js 16 + React 19 + TypeScript"],
              ["3D Visualization Engine", "React Three Fiber 9 + Three.js r187"],
              ["Multi-Physics Backend", "FastAPI + SQLModel + SQLite (48/48 Verification Passes)"],
              ["Topology Solver", "Series/Parallel matrix, Coulomb-counting SOC, R_pack = Ns·R_cell/Np"],
              ["Thermal Simulation", "First-order lumped node: m·cp·dT/dt = Q_gen − hA·(T−T_amb)"],
            ].map(([k, v]) => (
              <div key={k} style={{ display: "flex", gap: "1rem", justifyContent: "space-between", borderBottom: "1px solid rgba(0,240,255,0.06)", paddingBottom: 4 }}>
                <span style={{ color: "var(--text-muted)" }}>{k}</span>
                <span style={{ fontWeight: 600, textAlign: "right", color: "var(--arc-cyan)" }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Safety & Engineering Advisory */}
        <div className="card hud-bracket" style={{ background: "rgba(255,42,95,0.04)", border: "1px solid rgba(255,42,95,0.25)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <ShieldAlert size={18} color="var(--danger)" />
            <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--danger)", letterSpacing: "0.08em" }}>
              ENGINEERING SCREENING & SAFETY PROTOCOL
            </span>
          </div>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.7 }}>
            BattLab is an interactive virtual design and screening suite. All metrics represent computed numerical estimates.
            Thermal analysis uses a lumped node solver and spatial 3D infrared simulation. Always corroborate pack topologies
            with physical multi-cell calorimeter testing and verified manufacturer cell datasheets.
          </p>
        </div>
      </div>
    </AppLayout>
  );
}
