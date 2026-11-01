"use client";
import { use, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { api, SimulationResults, ProvenanceCatalog, ValidationReport, UncertaintyReport, ExperimentalValidationResult } from "@/lib/api";
import {
  CheckCircle, XCircle, AlertTriangle, HelpCircle,
  Download, ChevronDown, ChevronUp, ArrowLeft, Play, Pause,
  RotateCcw, Orbit, Thermometer, Box, Activity, ShieldCheck,
  Database, Sliders, Dna, Upload, FileSpreadsheet,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";

const StarkBatteryVisualizer = dynamic(
  () => import("@/components/battery-3d/StarkBatteryVisualizer").then((m) => m.StarkBatteryVisualizer),
  { ssr: false, loading: () => <div className="spinner" style={{ margin: "auto" }} /> }
);

function ConstraintBadge({ status }: { status: string }) {
  if (status === "pass") return <span className="badge-pass"><CheckCircle size={10} /> Pass</span>;
  if (status === "fail") return <span className="badge-fail"><XCircle size={10} /> Fail</span>;
  if (status === "warning") return <span className="badge-warn"><AlertTriangle size={10} /> Warning</span>;
  return <span className="badge-unverified"><HelpCircle size={10} /> Unverified</span>;
}

function MetricCard({ label, value, unit, note, highlight }: { label: string; value?: number | null; unit?: string; note?: string; highlight?: boolean }) {
  return (
    <div className="card-surface" style={{ border: highlight ? "1px solid var(--border-glow)" : undefined }}>
      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>
        {label}
      </div>
      <div style={{ fontSize: "1.35rem", fontWeight: 800, color: highlight ? "var(--arc-cyan)" : "var(--text-primary)", fontVariantNumeric: "tabular-nums", fontFamily: "monospace" }}>
        {value != null ? `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit ?? ""}` : "—"}
      </div>
      {note && <div style={{ fontSize: "0.65rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>{note}</div>}
    </div>
  );
}

export default function ResultsPage({ params }: { params: Promise<{ id: string; runId: string }> }) {
  const { id, runId } = use(params);
  const [results, setResults] = useState<SimulationResults | null>(null);
  const [provenance, setProvenance] = useState<ProvenanceCatalog | null>(null);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [customValidation, setCustomValidation] = useState<ExperimentalValidationResult | null>(null);
  const [showValidationUpload, setShowValidationUpload] = useState(false);
  const [csvContent, setCsvContent] = useState("");
  const [isPhysicalLabData, setIsPhysicalLabData] = useState(false);
  const [valUploadLoading, setValUploadLoading] = useState(false);
  const [valUploadError, setValUploadError] = useState<string | null>(null);
  const [uncertainty, setUncertainty] = useState<UncertaintyReport | null>(null);
  const [runningUncertainty, setRunningUncertainty] = useState(false);
  const [showProvenanceDrawer, setShowProvenanceDrawer] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedConstraint, setExpandedConstraint] = useState<number | null>(null);
  const [downloading, setDownloading] = useState(false);

  // 3D Replay Controls
  const [playbackIdx, setPlaybackIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState<1 | 2 | 5>(2);
  const [exploded, setExploded] = useState(false);
  const [explodeAmount, setExplodeAmount] = useState(0);
  const [showEnclosure, setShowEnclosure] = useState(true);
  const [colorMode, setColorMode] = useState<"default" | "thermal" | "simulation">("simulation");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [resData, provData, valData] = await Promise.allSettled([
          api.simulations.results(+runId),
          api.simulations.provenance(+runId),
          api.simulations.validation(+runId),
        ]);
        if (active) {
          if (resData.status === "fulfilled") setResults(resData.value);
          if (provData.status === "fulfilled") setProvenance(provData.value);
          if (valData.status === "fulfilled") setValidation(valData.value);
          setLoading(false);
        }
      } catch (e: unknown) {
        if (active) {
          setError(e instanceof Error ? e.message : "Failed to load telemetry");
          setLoading(false);
        }
      }
    })();
    return () => { active = false; };
  }, [runId]);

  async function runMonteCarlo() {
    setRunningUncertainty(true);
    try {
      const data = await api.simulations.uncertainty(+runId, { n_iterations: 50, random_seed: 42 });
      setUncertainty(data);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Uncertainty calculation failed");
    } finally {
      setRunningUncertainty(false);
    }
  }

  // Synchronized 3D Simulation Timeline Player
  useEffect(() => {
    if (!isPlaying || !results || results.timeseries.length === 0) return;
    const interval = setInterval(() => {
      setPlaybackIdx((idx) => {
        if (idx >= results.timeseries.length - 1) {
          setIsPlaying(false);
          return idx;
        }
        return Math.min(results.timeseries.length - 1, idx + playSpeed);
      });
    }, 100);
    return () => clearInterval(interval);
  }, [isPlaying, playSpeed, results]);

  async function downloadReport(format: "pdf" | "csv" | "json") {
    setDownloading(true);
    try {
      const rep = await api.projects.report(+id, { format, simulation_run_id: +runId });
      window.open(api.reports.downloadUrl(rep.report_id), "_blank");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  }

  async function handleValidateDataset() {
    if (!csvContent.trim()) {
      setValUploadError("Please provide CSV content to evaluate.");
      return;
    }
    setValUploadLoading(true);
    setValUploadError(null);
    try {
      const res = await api.simulations.validateDataset(+runId, {
        csv_content: csvContent,
        is_physical_laboratory_data: isPhysicalLabData,
        dataset_name: isPhysicalLabData ? "Physical Hardware Testbench" : "Benchmark Test Dataset",
      });
      setCustomValidation(res.validation_result);
    } catch (e: unknown) {
      setValUploadError(e instanceof Error ? e.message : "Failed to evaluate dataset against simulation run.");
    } finally {
      setValUploadLoading(false);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", gap: "1rem", alignItems: "center", justifyContent: "center", height: "60vh", color: "var(--arc-cyan)" }}>
        <div className="spinner" style={{ width: 36, height: 36 }} />
        <span style={{ fontFamily: "monospace", letterSpacing: "0.1em" }}>RETRIEVING SIMULATION TELEMETRY…</span>
      </div>
    );
  }

  if (error) return <div style={{ color: "var(--danger)", padding: "2rem" }}>⚠ {error}</div>;
  if (!results) return null;

  const ts = results.timeseries;
  const currentPoint = ts[playbackIdx] ?? ts[0] ?? { t_s: 0, soc: 1, temp_c: 25, current_a: 0, power_loss_w: 0 };

  const sortedConstraints = [...results.constraints].sort((a, b) => {
    const order = { fail: 0, warning: 1, unverified: 2, pass: 3 };
    return (order[a.status as keyof typeof order] ?? 4) - (order[b.status as keyof typeof order] ?? 4);
  });

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }} className="fade-in">
      {/* ── Top Header ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.5rem" }}>
        <div>
          <Link href={`/projects/${id}/design`} style={{ color: "var(--arc-cyan)", textDecoration: "none", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.3rem", marginBottom: "0.5rem" }}>
            <ArrowLeft size={14} /> Back to 3D Design Rig
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <h1 style={{ fontSize: "1.65rem", fontWeight: 800, letterSpacing: "-0.02em" }}>Simulation Telemetry</h1>
            <span className="badge-pass" style={{ fontSize: "0.7rem" }}>
              <Activity size={10} /> COMPLETED
            </span>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginTop: "0.25rem", fontFamily: "monospace" }}>
            SIMULATION RUN #{runId} · SOLVER MODEL {results.model_version} · {results.completed_at ? new Date(results.completed_at).toLocaleString() : "—"}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {(["pdf", "csv", "json"] as const).map((fmt) => (
            <button key={fmt} className="btn-secondary" style={{ fontSize: "0.78rem", padding: "0.4rem 0.875rem" }}
              disabled={downloading} onClick={() => downloadReport(fmt)}>
              <Download size={13} /> {fmt.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* ── Centerpiece: Interactive 3D Simulation Replay Holotable ── */}
      <div className="card hud-bracket" style={{ padding: "1rem", marginBottom: "1.5rem", position: "relative", overflow: "hidden" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontWeight: 800, fontSize: "0.95rem", color: "var(--arc-cyan)", letterSpacing: "0.05em" }}>
              3D SIMULATION PLAYBACK & THERMAL REPLAY
            </span>
            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontFamily: "monospace" }}>
              [t = {(currentPoint.t_s / 60).toFixed(1)} min / {(ts[ts.length - 1]?.t_s / 60 || 60).toFixed(0)} min]
            </span>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <button
              onClick={() => {
                const next = !exploded;
                setExploded(next);
                setExplodeAmount(next ? 0.8 : 0);
              }}
              style={{
                background: exploded ? "rgba(0, 240, 255, 0.2)" : "rgba(8, 20, 42, 0.6)",
                border: `1px solid ${exploded ? "var(--arc-cyan)" : "var(--border)"}`,
                borderRadius: 6, padding: "0.3rem 0.65rem",
                cursor: "pointer", display: "flex", alignItems: "center", gap: "0.35rem",
                color: exploded ? "var(--arc-cyan)" : "var(--text-secondary)", fontSize: "0.72rem", fontWeight: 700,
              }}
            >
              <Orbit size={13} />
              <span>EXPLODED VIEW</span>
            </button>
            <button
              onClick={() => setColorMode((m) => m === "thermal" ? "simulation" : "thermal")}
              style={{
                background: colorMode === "thermal" ? "rgba(255, 42, 95, 0.2)" : "rgba(8, 20, 42, 0.6)",
                border: `1px solid ${colorMode === "thermal" ? "var(--danger)" : "var(--border)"}`,
                borderRadius: 6, padding: "0.3rem 0.65rem",
                cursor: "pointer", display: "flex", alignItems: "center", gap: "0.35rem",
                color: colorMode === "thermal" ? "var(--danger)" : "var(--text-secondary)", fontSize: "0.72rem", fontWeight: 700,
              }}
            >
              <Thermometer size={13} />
              <span>THERMAL IR</span>
            </button>
            <button
              onClick={() => setShowEnclosure((v) => !v)}
              style={{
                background: "rgba(8, 20, 42, 0.6)",
                border: "1px solid var(--border)",
                borderRadius: 6, padding: "0.3rem 0.65rem",
                cursor: "pointer", display: "flex", alignItems: "center", gap: "0.35rem",
                color: showEnclosure ? "var(--arc-cyan)" : "var(--text-secondary)", fontSize: "0.72rem",
              }}
            >
              <Box size={13} />
              <span>ENCLOSURE</span>
            </button>
          </div>
        </div>

        {/* 3D Canvas Box */}
        <div style={{ height: "360px", width: "100%", position: "relative", borderRadius: 8, overflow: "hidden", background: "#030814" }}>
          <StarkBatteryVisualizer
            ns={results.configuration_ns ?? 14}
            np={results.configuration_np ?? 8}
            coolingType={results.cooling_type ?? "passive"}
            showEnclosure={showEnclosure}
            colorMode={colorMode}
            exploded={exploded}
            explodeAmount={explodeAmount}
            isSimulating={isPlaying || playbackIdx > 0}
            simTimeS={currentPoint.t_s}
            simCurrentA={currentPoint.current_a}
            simSoc={currentPoint.soc}
            simTempC={currentPoint.temp_c}
          />

          {/* Floating In-Scene Telemetry */}
          <div style={{
            position: "absolute", bottom: 12, left: 12,
            background: "rgba(4, 10, 24, 0.85)", backdropFilter: "blur(12px)",
            border: "1px solid var(--border)", borderRadius: 6,
            padding: "0.5rem 0.75rem", fontFamily: "monospace", fontSize: "0.75rem",
            display: "flex", gap: "1rem", color: "#e6f7ff",
          }}>
            <div>VOLTAGE: <span style={{ color: "var(--arc-cyan)" }}>{((currentPoint.voltage_v ?? results.result_nominal_voltage_v) ?? 51.8).toFixed(1)}V</span></div>
            <div>CURRENT: <span style={{ color: "#00ffaa" }}>{currentPoint.current_a.toFixed(1)}A</span></div>
            <div>SOC: <span style={{ color: "var(--arc-cyan)" }}>{(currentPoint.soc * 100).toFixed(1)}%</span></div>
            <div>TEMP: <span style={{ color: currentPoint.temp_c > 45 ? "var(--danger)" : "var(--stark-gold)" }}>{currentPoint.temp_c.toFixed(1)}°C</span></div>
            <div>LOSS: <span style={{ color: "var(--danger)" }}>{currentPoint.power_loss_w.toFixed(1)}W</span></div>
          </div>
        </div>

        {/* Timeline Player Scrubber Bar */}
        <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="btn-primary"
            style={{ padding: "0.35rem 0.875rem", fontSize: "0.75rem" }}
          >
            {isPlaying ? <Pause size={14} /> : <Play size={14} />}
            <span>{isPlaying ? "PAUSE" : "PLAY 3D"}</span>
          </button>
          <button
            onClick={() => { setPlaybackIdx(0); setIsPlaying(false); }}
            className="btn-secondary"
            style={{ padding: "0.35rem 0.65rem", fontSize: "0.75rem" }}
          >
            <RotateCcw size={13} />
          </button>

          {/* Scrubber slider */}
          <input
            type="range"
            min={0}
            max={Math.max(1, ts.length - 1)}
            value={playbackIdx}
            onChange={(e) => {
              setPlaybackIdx(+e.target.value);
              setIsPlaying(false);
            }}
            style={{ flex: 1, accentColor: "var(--arc-cyan)", cursor: "pointer" }}
          />

          <span style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "var(--arc-cyan)", minWidth: 60 }}>
            {((playbackIdx / Math.max(1, ts.length - 1)) * 100).toFixed(0)}%
          </span>

          {/* Speed Buttons */}
          <div style={{ display: "flex", gap: "0.25rem" }}>
            {([1, 2, 5] as const).map((spd) => (
              <button
                key={spd}
                onClick={() => setPlaySpeed(spd)}
                style={{
                  background: playSpeed === spd ? "var(--arc-cyan)" : "rgba(8, 20, 42, 0.6)",
                  color: playSpeed === spd ? "#000" : "var(--text-secondary)",
                  border: "1px solid var(--border)",
                  borderRadius: 4, padding: "0.2rem 0.45rem",
                  fontSize: "0.7rem", fontWeight: 700, cursor: "pointer",
                }}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Summary Metrics ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.875rem", marginBottom: "1.25rem" }}>
        <MetricCard label="Nominal Pack Voltage" value={results.result_nominal_voltage_v} unit="V" note="Ns × V_cell (Nameplate)" highlight />
        <MetricCard label="Nominal Energy" value={results.result_nominal_energy_wh} unit="Wh" note="V × Ah (Calculated)" />
        <MetricCard label="Usable Energy" value={results.result_usable_energy_wh} unit="Wh" note="SOC window applied" />
        <MetricCard label="Energy Delivered" value={results.result_energy_delivered_wh} unit="Wh" note="Simulated discharge" />
      </div>

      {/* ── Battery Health & SOH Metrics ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.875rem", marginBottom: "1.25rem" }}>
        <MetricCard label="State of Health (Capacity)" value={results.result_soh_capacity_pct ?? 100.0} unit="%" note="SEI Diffusional Model" highlight />
        <MetricCard label="State of Health (Resistance)" value={results.result_soh_resistance_pct ?? 100.0} unit="%" note="Interfacial Film Growth" />
        <MetricCard label="Mission Throughput" value={results.result_throughput_ah ?? 0.0} unit="Ah" note="Integrated |I| dt" />
        <MetricCard label="Full Cycle Equivalent" value={results.result_efc ?? 0.0} unit="EFC" note="Throughput / (2 × Cap)" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.875rem", marginBottom: "1.5rem" }}>
        <MetricCard
          label={results.multi_node_thermal?.enabled ? "Peak Core Temp" : "Peak Modelled Temp"}
          value={results.multi_node_thermal?.enabled ? (results.multi_node_thermal.max_core_temp_c ?? results.result_max_temp_c) : results.result_max_temp_c}
          unit="°C"
          note={results.multi_node_thermal?.enabled ? `Surface: ${results.multi_node_thermal.max_surface_temp_c?.toFixed(1) ?? "—"}°C (Grad: ${results.multi_node_thermal.max_gradient_c?.toFixed(1) ?? "—"}°C)` : "Single-node lumped thermal"}
        />
        <MetricCard label="Minimum End SOC" value={results.result_min_soc != null ? results.result_min_soc * 100 : undefined} unit="%" />
        <div className="card-surface">
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
            Constraint Checks
          </div>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <span className="badge-pass"><CheckCircle size={10} /> {results.constraint_pass} PASS</span>
            {results.constraint_fail > 0 && <span className="badge-fail"><XCircle size={10} /> {results.constraint_fail} FAIL</span>}
            {results.constraint_warning > 0 && <span className="badge-warn"><AlertTriangle size={10} /> {results.constraint_warning} WARN</span>}
          </div>
        </div>
        <div className="card-surface">
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>
            System Verdict
          </div>
          {results.constraint_fail > 0
            ? <span className="badge-fail"><XCircle size={10} /> {results.constraint_fail} FAILED</span>
            : results.constraint_warning > 0
            ? <span className="badge-warn"><AlertTriangle size={10} /> TOLERANCE WARNING</span>
            : <span className="badge-pass"><CheckCircle size={10} /> ALL SPEC CHECKS PASSED</span>
          }
        </div>
      </div>

      {/* ── 3-Column / 2-Row Telemetry Graph Deck (including ECM Pack Voltage) ── */}
      {ts.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "1.25rem", marginBottom: "1.5rem" }}>
          <ChartCard title="Terminal Pack Voltage vs Time" note="1-RC Thevenin ECM with dynamic IR sag">
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={ts} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#162e4a" />
                <XAxis dataKey="t_s" tickFormatter={(v) => `${(v / 60).toFixed(0)}m`} tick={{ fontSize: 10, fill: "#90b8d8" }} />
                <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "#90b8d8" }} unit="V" />
                <Tooltip formatter={(v) => [`${(v as number ?? 0).toFixed(2)} V`, "Pack V"]} labelFormatter={(t) => `t=${(Number(t) / 60).toFixed(1)} min`} contentStyle={{ background: "#050b14", border: "1px solid var(--border)", borderRadius: 6, fontSize: "0.8rem" }} />
                <Line type="monotone" dataKey="voltage_v" stroke="#00d2ff" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="SOC vs Time" note="Coulomb-counting">
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={ts} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#162e4a" />
                <XAxis dataKey="t_s" tickFormatter={(v) => `${(v / 60).toFixed(0)}m`} tick={{ fontSize: 10, fill: "#90b8d8" }} />
                <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 10, fill: "#90b8d8" }} />
                <Tooltip formatter={(v) => [`${((v as number ?? 0) * 100).toFixed(1)}%`, "SOC"]} labelFormatter={(t) => `t=${(Number(t) / 60).toFixed(1)} min`} contentStyle={{ background: "#050b14", border: "1px solid var(--border)", borderRadius: 6, fontSize: "0.8rem" }} />
                <Line type="monotone" dataKey="soc" stroke="#00f0ff" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title={results.multi_node_thermal?.enabled ? "Multi-Node Thermal Network vs Time" : "Temperature vs Time"}
            note={results.multi_node_thermal?.enabled ? "3-Node Network: Core (Jelly-Roll) vs Surface vs Plate" : "Lumped 1st-order thermal model"}
          >
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={ts} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#162e4a" />
                <XAxis dataKey="t_s" tickFormatter={(v) => `${(v / 60).toFixed(0)}m`} tick={{ fontSize: 10, fill: "#90b8d8" }} />
                <YAxis tick={{ fontSize: 10, fill: "#90b8d8" }} unit="°C" />
                <Tooltip
                  formatter={(v, name) => [
                    `${(v as number ?? 0).toFixed(1)} °C`,
                    name === "temp_core_c" ? "Core" : name === "temp_surface_c" ? "Surface" : name === "temp_plate_c" ? "Plate" : "Temp"
                  ]}
                  labelFormatter={(t) => `t=${(Number(t) / 60).toFixed(1)} min`}
                  contentStyle={{ background: "#050b14", border: "1px solid var(--border)", borderRadius: 6, fontSize: "0.8rem" }}
                />
                <Line type="monotone" dataKey={ts[0]?.temp_core_c != null ? "temp_core_c" : "temp_c"} name="Core" stroke="#ffb800" strokeWidth={2} dot={false} />
                {ts[0]?.temp_surface_c != null && (
                  <Line type="monotone" dataKey="temp_surface_c" name="Surface" stroke="#ff7a00" strokeWidth={1.75} dot={false} strokeDasharray="4 2" />
                )}
                {ts[0]?.temp_plate_c != null && (
                  <Line type="monotone" dataKey="temp_plate_c" name="Plate" stroke="#00d2ff" strokeWidth={1.75} dot={false} strokeDasharray="2 2" />
                )}
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Discharge Current vs Time" note="Duty cycle profile">
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={ts} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#162e4a" />
                <XAxis dataKey="t_s" tickFormatter={(v) => `${(v / 60).toFixed(0)}m`} tick={{ fontSize: 10, fill: "#90b8d8" }} />
                <YAxis tick={{ fontSize: 10, fill: "#90b8d8" }} unit="A" />
                <Tooltip formatter={(v) => [`${(v as number ?? 0).toFixed(1)} A`, "Current"]} contentStyle={{ background: "#050b14", border: "1px solid var(--border)", borderRadius: 6, fontSize: "0.8rem" }} />
                <Line type="monotone" dataKey="current_a" stroke="#00ffaa" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Resistive Ohmic Losses" note="I²×R pack losses">
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={ts} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#162e4a" />
                <XAxis dataKey="t_s" tickFormatter={(v) => `${(v / 60).toFixed(0)}m`} tick={{ fontSize: 10, fill: "#90b8d8" }} />
                <YAxis tick={{ fontSize: 10, fill: "#90b8d8" }} unit="W" />
                <Tooltip formatter={(v) => [`${(v as number ?? 0).toFixed(2)} W`, "Losses"]} contentStyle={{ background: "#050b14", border: "1px solid var(--border)", borderRadius: 6, fontSize: "0.8rem" }} />
                <Line type="monotone" dataKey="power_loss_w" stroke="#ff2a5f" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {/* ── Predictive Validation & Benchmark Metrics Deck ── */}
      {validation && (
        <div className="card hud-bracket" style={{ padding: "1.25rem", marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <ShieldCheck size={16} color="var(--arc-cyan)" />
              <span style={{ fontWeight: 800, fontSize: "0.95rem", color: "var(--arc-cyan)", letterSpacing: "0.04em" }}>
                MODEL VALIDATION &amp; STATISTICAL ACCURACY
              </span>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <button
                onClick={() => setShowValidationUpload((v) => !v)}
                className="btn-secondary"
                style={{ fontSize: "0.72rem", padding: "0.25rem 0.6rem" }}
              >
                <Upload size={12} /> {showValidationUpload ? "Hide Ingestion Panel" : "Evaluate Measured CSV"}
              </button>
              <span style={{ fontSize: "0.7rem", padding: "0.2rem 0.6rem", borderRadius: 12, background: "rgba(0, 240, 255, 0.1)", border: "1px solid rgba(0, 240, 255, 0.3)", color: "var(--arc-cyan)", fontFamily: "monospace" }}>
                {customValidation ? customValidation.status : validation.status}
              </span>
            </div>
          </div>

          {/* Ingestion & Upload Drawer */}
          {showValidationUpload && (
            <div style={{ background: "rgba(4, 10, 24, 0.85)", border: "1px solid var(--border)", borderRadius: 8, padding: "1rem", marginBottom: "1rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.5rem", fontSize: "0.75rem", fontWeight: 700, color: "var(--arc-cyan)", fontFamily: "monospace" }}>
                <FileSpreadsheet size={14} /> INGEST BATTERY TESTBENCH CSV (ARBIN / MACCOR / BIOLOGIC)
              </div>
              <textarea
                className="input"
                rows={4}
                style={{ fontFamily: "monospace", fontSize: "0.75rem", marginBottom: "0.6rem" }}
                placeholder={`t_s,current_a,voltage_v,temp_surface_c\n0.0,10.0,4.20,25.0\n10.0,10.0,4.15,25.4\n20.0,10.0,4.10,25.8`}
                value={csvContent}
                onChange={(e) => setCsvContent(e.target.value)}
              />
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.75rem", color: "var(--text-secondary)", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={isPhysicalLabData}
                    onChange={(e) => setIsPhysicalLabData(e.target.checked)}
                  />
                  <span>Physical Laboratory Cycler Data (Uncheck for Synthetic Benchmark)</span>
                </label>
                <button
                  className="btn-primary"
                  style={{ fontSize: "0.75rem", padding: "0.35rem 0.85rem" }}
                  disabled={valUploadLoading}
                  onClick={handleValidateDataset}
                >
                  {valUploadLoading ? "Aligning & Evaluating…" : "Evaluate Dataset"}
                </button>
              </div>
              {valUploadError && (
                <div style={{ marginTop: "0.5rem", color: "var(--danger)", fontSize: "0.75rem" }}>
                  ⚠ {valUploadError}
                </div>
              )}
            </div>
          )}

          {/* If custom validation evaluated, display its error moments */}
          {customValidation?.voltage_metrics ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.75rem", marginBottom: "0.75rem" }}>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>MAE (MEAN ABS ERROR)</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--arc-cyan)", fontFamily: "monospace" }}>{customValidation.voltage_metrics.mae} V</div>
              </div>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>RMSE (ROOT MEAN SQ)</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "monospace" }}>{customValidation.voltage_metrics.rmse} V</div>
              </div>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>MBE (MEAN BIAS)</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "monospace" }}>{customValidation.voltage_metrics.mbe} V</div>
              </div>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>MAX ERROR</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "monospace" }}>{customValidation.voltage_metrics.max_error} V</div>
              </div>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>COEFFICIENT R²</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "#10b981", fontFamily: "monospace" }}>{customValidation.voltage_metrics.r_squared}</div>
              </div>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.75rem", marginBottom: "0.75rem" }}>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>MAE (MEAN ABS ERROR)</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--arc-cyan)", fontFamily: "monospace" }}>{validation.metrics.mae} V</div>
              </div>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>RMSE (ROOT MEAN SQ)</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "monospace" }}>{validation.metrics.rmse} V</div>
              </div>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>MBE (MEAN BIAS)</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "monospace" }}>{validation.metrics.mbe} V</div>
              </div>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>MAX ERROR</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "monospace" }}>{validation.metrics.max_error} V</div>
              </div>
              <div className="card-surface" style={{ padding: "0.6rem" }}>
                <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>COEFFICIENT R²</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "#10b981", fontFamily: "monospace" }}>{validation.metrics.r_squared}</div>
              </div>
            </div>
          )}

          {customValidation?.blockers && customValidation.blockers.length > 0 && (
            <div style={{ background: "rgba(245, 158, 11, 0.08)", border: "1px solid rgba(245, 158, 11, 0.3)", borderRadius: 6, padding: "0.5rem 0.75rem", marginBottom: "0.6rem", fontSize: "0.75rem", color: "#fbbf24" }}>
              {customValidation.blockers.map((b, i) => (
                <div key={i}>⚠ {b}</div>
              ))}
            </div>
          )}

          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontStyle: "italic", lineHeight: 1.4 }}>
            ℹ {customValidation?.disclaimer ?? validation.disclaimer}
          </div>
        </div>
      )}

      {/* ── Parameter Provenance & Confidence Inspector ── */}
      {provenance && (
        <div className="card hud-bracket" style={{ padding: "1.25rem", marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Database size={16} color="var(--arc-cyan)" />
              <span style={{ fontWeight: 800, fontSize: "0.95rem", color: "var(--arc-cyan)", letterSpacing: "0.04em" }}>
                PARAMETER PROVENANCE & CONFIDENCE CATALOG
              </span>
            </div>
            <button
              onClick={() => setShowProvenanceDrawer((v) => !v)}
              className="btn-secondary"
              style={{ fontSize: "0.72rem", padding: "0.25rem 0.6rem" }}
            >
              <Sliders size={12} /> {showProvenanceDrawer ? "Hide Details" : `Inspect (${provenance.parameters.length} Parameters)`}
            </button>
          </div>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", marginBottom: showProvenanceDrawer ? "1rem" : 0 }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
              Overall Confidence: <span style={{ color: "var(--arc-cyan)", fontWeight: 700 }}>{provenance.summary.confidence_rating}</span>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              High: <span style={{ color: "#10b981", fontWeight: 700 }}>{provenance.summary.high_confidence_count}</span>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Medium: <span style={{ color: "#ffb800", fontWeight: 700 }}>{provenance.summary.medium_confidence_count}</span>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Provisional/Low: <span style={{ color: "var(--danger)", fontWeight: 700 }}>{provenance.summary.provisional_count}</span>
            </div>
          </div>

          {showProvenanceDrawer && (
            <div style={{ overflowX: "auto", marginTop: "0.75rem" }}>
              <table style={{ width: "100%", fontSize: "0.75rem", borderCollapse: "collapse", textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-muted)" }}>
                    <th style={{ padding: "0.4rem 0.5rem" }}>Parameter</th>
                    <th style={{ padding: "0.4rem 0.5rem" }}>Value</th>
                    <th style={{ padding: "0.4rem 0.5rem" }}>Category</th>
                    <th style={{ padding: "0.4rem 0.5rem" }}>Confidence</th>
                    <th style={{ padding: "0.4rem 0.5rem" }}>Tolerance</th>
                    <th style={{ padding: "0.4rem 0.5rem" }}>Source Note</th>
                  </tr>
                </thead>
                <tbody>
                  {provenance.parameters.map((p) => (
                    <tr key={p.key} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                      <td style={{ padding: "0.45rem 0.5rem", fontWeight: 600, color: "var(--text-primary)" }}>{p.label}</td>
                      <td style={{ padding: "0.45rem 0.5rem", fontFamily: "monospace", color: "var(--arc-cyan)" }}>
                        {String(p.value ?? "—")} {p.unit}
                      </td>
                      <td style={{ padding: "0.45rem 0.5rem", fontFamily: "monospace", textTransform: "uppercase", fontSize: "0.68rem" }}>
                        {p.category.replace(/_/g, " ")}
                      </td>
                      <td style={{ padding: "0.45rem 0.5rem" }}>
                        <span style={{
                          fontSize: "0.68rem", padding: "0.15rem 0.45rem", borderRadius: 4,
                          background: p.confidence === "high" ? "rgba(16,185,129,0.15)" : p.confidence === "medium" ? "rgba(255,184,0,0.15)" : "rgba(255,42,95,0.15)",
                          color: p.confidence === "high" ? "#10b981" : p.confidence === "medium" ? "#ffb800" : "var(--danger)",
                          fontWeight: 700, textTransform: "uppercase",
                        }}>
                          {p.confidence}
                        </span>
                      </td>
                      <td style={{ padding: "0.45rem 0.5rem", fontFamily: "monospace" }}>
                        {p.uncertainty_pct != null ? `±${p.uncertainty_pct}%` : "—"}
                      </td>
                      <td style={{ padding: "0.45rem 0.5rem", color: "var(--text-muted)", maxWidth: 260 }}>{p.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Monte Carlo Parameter Uncertainty Analysis Deck ── */}
      <div className="card hud-bracket" style={{ padding: "1.25rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Dna size={16} color="var(--arc-cyan)" />
            <span style={{ fontWeight: 800, fontSize: "0.95rem", color: "var(--arc-cyan)", letterSpacing: "0.04em" }}>
              MONTE CARLO UNCERTAINTY PROPAGATION & SENSITIVITY
            </span>
          </div>
          <button
            onClick={runMonteCarlo}
            disabled={runningUncertainty}
            className="btn-primary"
            style={{ fontSize: "0.72rem", padding: "0.3rem 0.75rem" }}
          >
            {runningUncertainty ? "Simulating 50 Draws…" : "Run Monte Carlo (N=50)"}
          </button>
        </div>

        {uncertainty ? (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0.875rem", marginBottom: "1rem" }}>
              <div className="card-surface" style={{ padding: "0.75rem" }}>
                <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>PACK ENERGY BOUNDS</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--arc-cyan)", fontFamily: "monospace" }}>
                  {uncertainty.distributions.nominal_energy_wh.p50} Wh
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "0.25rem", fontFamily: "monospace" }}>
                  P05: {uncertainty.distributions.nominal_energy_wh.p05} Wh | P95: {uncertainty.distributions.nominal_energy_wh.p95} Wh
                </div>
              </div>

              <div className="card-surface" style={{ padding: "0.75rem" }}>
                <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>CELL MASS BOUNDS</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--text-primary)", fontFamily: "monospace" }}>
                  {uncertainty.distributions.total_cell_mass_kg.p50} kg
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "0.25rem", fontFamily: "monospace" }}>
                  P05: {uncertainty.distributions.total_cell_mass_kg.p05} kg | P95: {uncertainty.distributions.total_cell_mass_kg.p95} kg
                </div>
              </div>

              <div className="card-surface" style={{ padding: "0.75rem" }}>
                <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>PEAK TEMPERATURE BOUNDS</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#ffb800", fontFamily: "monospace" }}>
                  {uncertainty.distributions.simulated_max_temp_c.p50} °C
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "0.25rem", fontFamily: "monospace" }}>
                  P05: {uncertainty.distributions.simulated_max_temp_c.p05} °C | P95: {uncertainty.distributions.simulated_max_temp_c.p95} °C
                </div>
              </div>

              <div className="card-surface" style={{ padding: "0.75rem" }}>
                <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>TERMINAL VOLTAGE BOUNDS</div>
                <div style={{ fontSize: "1.2rem", fontWeight: 800, color: "#10b981", fontFamily: "monospace" }}>
                  {uncertainty.distributions.end_terminal_voltage_v.p50} V
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "0.25rem", fontFamily: "monospace" }}>
                  P05: {uncertainty.distributions.end_terminal_voltage_v.p05} V | P95: {uncertainty.distributions.end_terminal_voltage_v.p95} V
                </div>
              </div>
            </div>

            {/* Sensitivity table */}
            <div style={{ marginTop: "0.75rem", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.75rem" }}>
              <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: "0.5rem" }}>
                Parameter Sensitivity Correlation (Pearson |r|)
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                {uncertainty.sensitivity_ranking.map((s, idx) => (
                  <div key={idx} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.74rem", background: "rgba(6,14,30,0.5)", padding: "0.35rem 0.65rem", borderRadius: 4 }}>
                    <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{s.parameter} → {s.target}</span>
                    <span style={{ fontFamily: "monospace", color: "var(--arc-cyan)", fontWeight: 700 }}>r = {s.correlation_coefficient}</span>
                    <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{s.impact_direction}</span>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontStyle: "italic", marginTop: "0.75rem" }}>
              ℹ {uncertainty.disclaimer}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", padding: "0.5rem 0" }}>
            Click &apos;Run Monte Carlo&apos; to propagate manufacturing tolerances (capacity ±2%, internal resistance ±5%, mass ±1.5%, ambient temp ±1°C) and estimate P05/P50/P95 confidence intervals.
          </div>
        )}
      </div>

      {/* ── Engineering Constraints Deck ── */}
      <div className="card hud-bracket" style={{ marginBottom: "1.5rem" }}>
        <p className="section-title">Constraint Verification Protocol</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {sortedConstraints.map((c, i) => (
            <div key={c.id ?? i} style={{
              border: `1px solid ${c.status === "fail" ? "rgba(255,42,95,0.4)" : c.status === "warning" ? "rgba(255,184,0,0.3)" : "var(--border-subtle)"}`,
              borderRadius: 6, overflow: "hidden",
            }}>
              <button style={{
                width: "100%", display: "flex", alignItems: "center", gap: "0.75rem",
                padding: "0.75rem 1rem", cursor: "pointer",
                background: c.status === "fail" ? "rgba(255,42,95,0.08)" : "rgba(8,20,42,0.5)",
                border: "none", textAlign: "left",
              }}
                onClick={() => setExpandedConstraint(expandedConstraint === i ? null : i)}>
                <ConstraintBadge status={c.status} />
                <span style={{ fontWeight: 600, fontSize: "0.85rem", flex: 1, fontFamily: "monospace" }}>{c.rule_id}</span>
                {c.observed_value != null ? (
                  <span style={{ fontSize: "0.8rem", color: "var(--arc-cyan)", fontFamily: "monospace" }}>
                    {c.observed_value.toFixed(2)} {c.units}
                    {c.threshold != null && ` / ${c.threshold.toFixed(2)} ${c.units}`}
                  </span>
                ) : (
                  <span style={{
                    fontSize: "0.72rem",
                    color: "var(--text-muted)",
                    fontFamily: "monospace",
                    background: "rgba(100, 116, 139, 0.12)",
                    padding: "2px 8px",
                    borderRadius: 4,
                    border: "1px solid rgba(100, 116, 139, 0.25)",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}>
                    <span>{c.rule_id === "CURR_CONTINUOUS" ? "Target continuous current omitted in project specs" : c.rule_id === "COST_BOM" ? "BOM cost budget ceiling omitted in project specs" : "Parameter omitted — click for details"}</span>
                  </span>
                )}
                {expandedConstraint === i ? <ChevronUp size={14} color="var(--text-muted)" /> : <ChevronDown size={14} color="var(--text-muted)" />}
              </button>
              {expandedConstraint === i && (
                <div style={{ padding: "0.85rem 1rem", fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.6, background: "rgba(4,10,24,0.75)", borderTop: "1px solid var(--border-subtle)" }}>
                  <p style={{ marginBottom: "0.375rem", color: "#f8fafc" }}>{c.explanation}</p>
                  {c.source_assumption && <p style={{ color: "var(--text-muted)", fontStyle: "italic" }}>Source: {c.source_assumption}</p>}
                  {c.corrective_action && c.corrective_action.trim() && (
                    <p style={{ marginTop: "0.375rem", color: "var(--arc-cyan)" }}>→ Corrective Action: {c.corrective_action}</p>
                  )}
                  {c.status === "unverified" && (
                    <div style={{ marginTop: "0.5rem", padding: "0.45rem 0.65rem", background: "rgba(0, 240, 255, 0.05)", borderRadius: 4, border: "1px solid rgba(0, 240, 255, 0.15)", fontSize: "0.72rem", color: "var(--arc-cyan)" }}>
                      💡 <strong>Why UNVERIFIED?</strong> BattLab enforces strict engineering honesty. When an input threshold or datasheet value is omitted during project setup, BattLab marks the constraint as unverified rather than falsely assuming pass or fail.
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ padding: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.75rem" }}>
        <span style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--text-primary)" }}>{title}</span>
        {note && <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "monospace" }}>{note}</span>}
      </div>
      {children}
    </div>
  );
}
