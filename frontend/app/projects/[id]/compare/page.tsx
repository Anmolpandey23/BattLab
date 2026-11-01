"use client";
import { use, useEffect, useState } from "react";
import { api, CompareResult, SimulationMeta } from "@/lib/api";
import { BarChart3, Trophy, XCircle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

export default function ComparePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = +id;

  const [runs, setRuns] = useState<SimulationMeta[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await api.projects.simulations(projectId);
        if (active) {
          const completed = data.filter((r) => r.status === "completed");
          setRuns(completed);
          setLoadingRuns(false);
        }
      } catch {
        if (active) setLoadingRuns(false);
      }
    })();
    return () => { active = false; };
  }, [projectId]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function compare() {
    if (selected.size < 2) { setError("Select at least 2 runs to compare."); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await api.projects.compare(projectId, { simulation_run_ids: Array.from(selected) });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  }

  // Prep chart data
  const chartData = result ? result.metrics_table.filter((m) =>
    ["Nominal Energy Wh", "Usable Energy Wh", "Max Temp °C"].some((k) => m.metric.includes(k.split(" ")[0]))
  ).map((m) => ({
    name: m.metric.replace(/\s\([^)]+\)/, ""),
    ...Object.fromEntries(Object.entries(m.values).map(([k, v]) => [k, typeof v === "number" ? +v.toFixed(2) : v])),
  })) : [];

  return (
    <div style={{ maxWidth: 1100 }} className="fade-in">
      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.375rem" }}>Design Comparison</h1>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginBottom: "1.5rem" }}>
        Compare completed simulation runs. Select 2+ runs then click Compare.
      </p>

      {/* Run selector */}
      <div className="card" style={{ marginBottom: "1.25rem" }}>
        <p className="section-title">Select Runs to Compare</p>
        {loadingRuns ? (
          <div className="spinner" />
        ) : runs.length === 0 ? (
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>No completed simulations found. Run at least two simulations first.</p>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "0.625rem", marginBottom: "0.875rem" }}>
              {runs.map((r) => (
                <button key={r.id}
                  onClick={() => toggle(r.id)}
                  style={{
                    textAlign: "left", padding: "0.75rem",
                    borderRadius: 8, border: `1px solid ${selected.has(r.id) ? "var(--accent)" : "var(--border-subtle)"}`,
                    background: selected.has(r.id) ? "rgba(0,212,255,0.08)" : "var(--bg-surface)",
                    cursor: "pointer",
                  }}>
                  <div style={{ fontWeight: 600, fontSize: "0.8rem", color: selected.has(r.id) ? "var(--accent)" : "var(--text-primary)", marginBottom: "0.25rem" }}>
                    Run #{r.id}: {r.run_label || "Simulation Run"}
                  </div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                    {r.result_nominal_energy_wh?.toFixed(0)} Wh · {r.result_max_temp_c?.toFixed(1)}°C
                    · <span className={r.constraint_fail > 0 ? "" : r.constraint_warning > 0 ? "" : ""} style={{ color: r.constraint_fail > 0 ? "var(--danger)" : r.constraint_warning > 0 ? "var(--warning)" : "var(--success)" }}>
                      {r.constraint_fail}F / {r.constraint_warning}W
                    </span>
                  </div>
                </button>
              ))}
            </div>
            <button className="btn-primary" onClick={compare} disabled={selected.size < 2 || loading}>
              {loading ? <><div className="spinner" style={{ width: 15, height: 15 }} /> Comparing…</> : <><BarChart3 size={15} /> Compare {selected.size} Runs</>}
            </button>
          </>
        )}
        {error && <div style={{ marginTop: "0.75rem", color: "var(--danger)", fontSize: "0.875rem" }}>{error}</div>}
      </div>

      {/* Results */}
      {result && (
        <div className="fade-in">
          {/* Ranking */}
          <div className="card" style={{ marginBottom: "1.25rem" }}>
            <p className="section-title">Ranking</p>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "0.875rem" }}>
              Weighted score (lower = better). Configurations with constraint failures are always ranked last.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {result.ranking.map((r, i) => (
                <div key={r.run_id} style={{
                  display: "flex", alignItems: "center", gap: "1rem",
                  padding: "0.75rem 1rem", borderRadius: 8,
                  background: i === 0 ? "rgba(0,212,255,0.07)" : "var(--bg-surface)",
                  border: `1px solid ${i === 0 ? "rgba(0,212,255,0.25)" : "var(--border-subtle)"}`,
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: "50%",
                    background: i === 0 ? "var(--accent)" : "var(--bg-secondary)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontWeight: 800, color: i === 0 ? "#000" : "var(--text-muted)",
                    flexShrink: 0,
                  }}>
                    {i === 0 ? <Trophy size={16} /> : r.rank}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: "0.875rem" }}>Run #{r.run_id}: {r.run_label}</div>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{r.rank_note}</div>
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    {r.constraint_fail > 0 && <span className="badge-fail"><XCircle size={10} /> {r.constraint_fail}F</span>}
                    <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>Score: {r.score.toFixed(3)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Metrics table */}
          <div className="card" style={{ marginBottom: "1.25rem" }}>
            <p className="section-title">Metrics Comparison</p>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Unit</th>
                    {runs.filter((r) => selected.has(r.id)).map((r) => (
                      <th key={r.id}>Run #{r.id}: {r.run_label || "Simulation Run"}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.metrics_table.map((m) => (
                    <tr key={m.metric}>
                      <td style={{ fontWeight: 500 }}>{m.metric}</td>
                      <td style={{ color: "var(--text-muted)" }}>{m.unit}</td>
                      {Object.values(m.values).map((v, i) => (
                        <td key={i}>{typeof v === "number" ? v.toFixed(2) : String(v ?? "—")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Bar chart */}
          {chartData.length > 0 && (
            <div className="card">
              <p className="section-title">Visual Comparison</p>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a2f4a" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#8ba3c4" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#8ba3c4" }} />
                  <Tooltip contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", borderRadius: 6, fontSize: "0.8rem" }} />
                  <Legend wrapperStyle={{ fontSize: "0.8rem" }} />
                  {runs.filter((r) => selected.has(r.id)).map((r, i) => {
                    const COLORS = ["#00d4ff", "#22c55e", "#f59e0b", "#ef4444", "#a78bfa"];
                    return <Bar key={r.id} dataKey={r.run_label ?? `Run #${r.id}`} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} />;
                  })}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "0.875rem" }}>
            ⚠ Comparison uses simulated provisional results. Weighted scoring is a heuristic ranking aid only.
          </p>
        </div>
      )}
    </div>
  );
}
