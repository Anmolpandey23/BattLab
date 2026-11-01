"use client";
import { use, useEffect, useState } from "react";
import { api, SimulationMeta } from "@/lib/api";
import { Download, FileText, FileSpreadsheet, Code2, AlertCircle } from "lucide-react";

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = +id;

  const [runs, setRuns] = useState<SimulationMeta[]>([]);
  const [selectedRun, setSelectedRun] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const sims = await api.projects.simulations(projectId);
        if (active) {
          const completed = sims.filter((r) => r.status === "completed");
          setRuns(completed);
          if (completed.length > 0) setSelectedRun(completed[completed.length - 1].id);
          setLoading(false);
        }
      } catch (e: unknown) {
        if (active) {
          setError(e instanceof Error ? e.message : "Failed to load simulations");
          setLoading(false);
        }
      }
    })();
    return () => { active = false; };
  }, [projectId]);

  async function generate(format: "pdf" | "csv" | "json") {
    if (!selectedRun) { setError("Select a simulation run first."); return; }
    setGenerating(format);
    setError(null);
    try {
      const rep = await api.projects.report(projectId, { format, simulation_run_id: selectedRun });
      window.open(api.reports.downloadUrl(rep.report_id), "_blank");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Report generation failed");
    } finally {
      setGenerating(null);
    }
  }

  return (
    <div style={{ maxWidth: 720 }} className="fade-in">
      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.375rem" }}>Export Reports</h1>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginBottom: "1.5rem" }}>
        Generate engineering reports from completed simulation runs.
      </p>

      {/* Disclaimer */}
      <div style={{
        display: "flex", gap: "0.625rem", alignItems: "flex-start",
        background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)",
        borderRadius: 8, padding: "0.75rem 1rem", marginBottom: "1.25rem", fontSize: "0.78rem", color: "#d97706",
      }}>
        <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
        Reports clearly label all results as simulated estimates from provisional data.
        They include prominent disclaimers: not experimental measurements, not a safety certification.
      </div>

      {loading ? (
        <div className="spinner" />
      ) : runs.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem" }}>
          <p style={{ color: "var(--text-muted)" }}>No completed simulations found. Run a simulation first.</p>
        </div>
      ) : (
        <>
          {/* Run selector */}
          <div className="card" style={{ marginBottom: "1.25rem" }}>
            <p className="section-title">Select Simulation Run</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {[...runs].reverse().map((r) => (
                <button key={r.id}
                  onClick={() => setSelectedRun(r.id)}
                  style={{
                    textAlign: "left", padding: "0.75rem",
                    borderRadius: 8, cursor: "pointer",
                    border: `1px solid ${selectedRun === r.id ? "var(--accent)" : "var(--border-subtle)"}`,
                    background: selectedRun === r.id ? "rgba(0,212,255,0.08)" : "var(--bg-surface)",
                  }}>
                  <div style={{ fontWeight: 600, fontSize: "0.875rem", color: selectedRun === r.id ? "var(--accent)" : "var(--text-primary)", marginBottom: "0.25rem" }}>
                    {r.run_label ?? `Run #${r.id}`}
                  </div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                    {r.result_nominal_voltage_v?.toFixed(1)} V · {r.result_nominal_energy_wh?.toFixed(0)} Wh · Max {r.result_max_temp_c?.toFixed(1)}°C
                    · {r.constraint_fail}F/{r.constraint_warning}W · {new Date(r.created_at).toLocaleDateString()}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Format buttons */}
          <div className="card">
            <p className="section-title">Export Format</p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "0.875rem" }}>
              {[
                {
                  fmt: "pdf" as const,
                  icon: FileText,
                  label: "PDF Report",
                  desc: "Full engineering report with charts, constraints, and methodology notes. Includes disclaimers.",
                  color: "#ef4444",
                },
                {
                  fmt: "csv" as const,
                  icon: FileSpreadsheet,
                  label: "CSV Timeseries",
                  desc: "Raw time-domain simulation data (SOC, temperature, current, losses) for external analysis.",
                  color: "#22c55e",
                },
                {
                  fmt: "json" as const,
                  icon: Code2,
                  label: "JSON Config",
                  desc: "Machine-readable configuration and result snapshot for integration with other tools.",
                  color: "#a78bfa",
                },
              ].map((f) => (
                <div key={f.fmt} style={{
                  background: "var(--bg-surface)", borderRadius: 10, padding: "1.125rem",
                  border: "1px solid var(--border-subtle)",
                  display: "flex", flexDirection: "column", gap: "0.625rem",
                }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 8,
                    background: `${f.color}15`, border: `1px solid ${f.color}25`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <f.icon size={20} color={f.color} />
                  </div>
                  <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{f.label}</div>
                  <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: 1.5, flex: 1 }}>{f.desc}</p>
                  <button
                    className="btn-primary"
                    style={{ fontSize: "0.8rem", justifyContent: "center" }}
                    disabled={!!generating || !selectedRun}
                    onClick={() => generate(f.fmt)}
                  >
                    {generating === f.fmt
                      ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Generating…</>
                      : <><Download size={13} /> Download {f.fmt.toUpperCase()}</>
                    }
                  </button>
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div style={{
              marginTop: "0.875rem", display: "flex", gap: "0.5rem",
              alignItems: "center", color: "var(--danger)", fontSize: "0.875rem",
            }}>
              <AlertCircle size={15} /> {error}
            </div>
          )}
        </>
      )}
    </div>
  );
}
