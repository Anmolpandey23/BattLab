"use client";
import { useEffect, useState, use, useCallback } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { api, Configuration, CellSpec, Requirement, PackMassBreakdown } from "@/lib/api";
import {
  Thermometer, Box, Save, Play, Pause, Orbit, ChevronDown, ChevronUp, Layers, Trash2, Ruler
} from "lucide-react";

const StarkBatteryVisualizer = dynamic(
  () => import("@/components/battery-3d/StarkBatteryVisualizer").then((m) => m.StarkBatteryVisualizer),
  { ssr: false, loading: () => <SceneLoader /> }
);

function SceneLoader() {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1rem", color: "var(--arc-cyan)" }}>
      <div className="spinner" style={{ width: 40, height: 40 }} />
      <span style={{ fontSize: "0.85rem", letterSpacing: "0.1em", textTransform: "uppercase", fontFamily: "monospace" }}>
        INITIALIZING 3D BATTERY DESIGN STUDIO…
      </span>
    </div>
  );
}

export default function DesignStudio({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = +id;

  const [configs, setConfigs] = useState<Configuration[]>([]);
  const [cells, setCells] = useState<CellSpec[]>([]);
  const [req, setReq] = useState<Requirement | null>(null);
  const [activeConfig, setActiveConfig] = useState<Configuration | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [configToDelete, setConfigToDelete] = useState<{ id: number; label: string } | null>(null);
  const [deletingConfigId, setDeletingConfigId] = useState<number | null>(null);

  async function confirmDeleteConfig() {
    if (!configToDelete) return;
    const { id } = configToDelete;
    setDeletingConfigId(id);
    try {
      await api.projects.configurations.delete(projectId, id);
      const remaining = configs.filter((c) => c.id !== id);
      setConfigs(remaining);
      if (activeConfig?.id === id) {
        if (remaining.length > 0) {
          selectConfig(remaining[0]);
        } else {
          setActiveConfig(null);
        }
      }
      setConfigToDelete(null);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to delete configuration");
    } finally {
      setDeletingConfigId(null);
    }
  }

  // 3D Controls
  const [showEnclosure, setShowEnclosure] = useState(true);
  const [colorMode, setColorMode] = useState<"default" | "thermal" | "simulation">("default");
  const [exploded, setExploded] = useState(false);
  const [explodeAmount, setExplodeAmount] = useState(0);
  const [showDimensions, setShowDimensions] = useState(true);

  // 3D Simulation Mode Controls
  const [isSimulating, setIsSimulating] = useState(false);
  const [simTimeS, setSimTimeS] = useState(0);

  // Editable Configuration Fields
  const [ns, setNs] = useState("14");
  const [np, setNp] = useState("8");
  const [selectedCellId, setSelectedCellId] = useState<number | null>(null);
  const [cooling, setCooling] = useState("passive");
  const [socWindow, setSocWindow] = useState("0.80");
  const [label, setLabel] = useState("");
  const [massBreakdown, setMassBreakdown] = useState<PackMassBreakdown | null>(null);
  const [showMassDetails, setShowMassDetails] = useState(false);

  const fetchMass = useCallback(async (cfgId: number) => {
    try {
      const data = await api.projects.configurations.massBreakdown(cfgId);
      setMassBreakdown(data);
    } catch {
      setMassBreakdown(null);
    }
  }, []);

  const selectConfig = useCallback((cfg: Configuration) => {
    setActiveConfig(cfg);
    setNs(String(cfg.ns));
    setNp(String(cfg.np));
    setSelectedCellId(cfg.cell_spec_id ?? null);
    setCooling(cfg.cooling_type);
    setSocWindow(String(cfg.usable_soc_window));
    setLabel(cfg.label);
    fetchMass(cfg.id);
  }, [fetchMass, setActiveConfig, setNs, setNp, setSelectedCellId, setCooling, setSocWindow, setLabel]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [cfgData, cellData, reqData] = await Promise.all([
          api.projects.configurations.list(projectId),
          api.library.cells(),
          api.projects.requirements.list(projectId),
        ]);
        if (active) {
          setConfigs(cfgData);
          setCells(cellData);
          setReq(reqData[0] ?? null);
          const baseline = cfgData.find((c) => c.is_baseline) ?? cfgData[0];
          if (baseline) selectConfig(baseline);
          setLoading(false);
        }
      } catch (e: unknown) {
        if (active) {
          setError(e instanceof Error ? e.message : "Failed to load");
          setLoading(false);
        }
      }
    })();
    return () => { active = false; };
  }, [projectId, selectConfig]);

  // 3D Simulation Loop Effect
  useEffect(() => {
    if (!isSimulating) return;
    const interval = setInterval(() => {
      setSimTimeS((t) => {
        if (t >= 1800) {
          setIsSimulating(false);
          return 0;
        }
        return t + 10;
      });
    }, 50);
    return () => clearInterval(interval);
  }, [isSimulating]);

  const [saveSuccess, setSaveSuccess] = useState(false);

  async function saveConfig() {
    if (!activeConfig) return;
    setSaving(true);
    setError(null);
    setSaveSuccess(false);
    try {
      const updated = await api.projects.configurations.update(activeConfig.id, {
        ns: +ns,
        np: +np,
        cell_spec_id: selectedCellId ?? undefined,
        cooling_type: cooling,
        usable_soc_window: +socWindow,
        label,
      });
      setActiveConfig(updated);
      fetchMass(updated.id);
      setConfigs((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function addConfig() {
    try {
      const newCfg = await api.projects.configurations.create(projectId, {
        label: `Pack Variant ${configs.length + 1}`,
        ns: +ns, np: +np,
        cell_spec_id: selectedCellId ?? undefined,
        cooling_type: cooling,
        is_baseline: false,
      });
      setConfigs((prev) => [...prev, newCfg]);
      selectConfig(newCfg);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add configuration");
    }
  }

  const selectedCell = cells.find((c) => c.id === selectedCellId);
  const calcV = +ns * (selectedCell?.nominal_voltage_v ?? 3.7);
  const calcAh = +np * (selectedCell?.nominal_capacity_ah ?? 5.0);
  const calcWh = calcV * calcAh;
  const totalCells = +ns * +np;

  // 3D Physical Geometry & Cell Specifications
  const cellDiamMm = selectedCell?.diameter_mm ?? (selectedCell?.form_factor === "18650" ? 18.4 : 21.4);
  const cellHeightMm = selectedCell?.length_mm ?? (selectedCell?.form_factor === "18650" ? 65.0 : 70.0);
  const interCellSpacingMm = 1.5;
  const enclosureWallMm = 4.0;
  const busbarClearanceMm = 4.0;

  const packLengthMm = Math.max(1, +ns) * (cellDiamMm + interCellSpacingMm) - interCellSpacingMm + 2 * enclosureWallMm;
  const packWidthMm = Math.max(1, +np) * (cellDiamMm + interCellSpacingMm) - interCellSpacingMm + 2 * enclosureWallMm;
  const packHeightMm = cellHeightMm + busbarClearanceMm + 2 * enclosureWallMm;

  // Real-time simulated physics values based on simTimeS
  const simProgress = simTimeS / 1800;
  const liveSoc = Math.max(0.1, 1.0 - simProgress * 0.85);
  const liveVoltage = calcV * (0.95 - simProgress * 0.15);
  const liveTempC = 25 + simProgress * 28 + (cooling === "liquid" ? -8 : 0);
  const liveCurrentA = 35 + Math.sin(simTimeS * 0.05) * 8;
  const livePowerLossW = Math.pow(liveCurrentA, 2) * 0.045;

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "80vh", gap: "1rem", color: "var(--arc-cyan)" }}>
        <div className="spinner" style={{ width: 44, height: 44 }} />
        <span style={{ letterSpacing: "0.1em", textTransform: "uppercase", fontFamily: "monospace" }}>
          INITIALIZING 3D BATTERY CAD STUDIO…
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "calc(100vh - 56px)", gap: 0, overflow: "hidden", margin: "-1.5rem" }}>
      {/* ── Left Holographic Control Console ── */}
      <div style={{
        width: 310, flexShrink: 0, overflowY: "auto",
        background: "rgba(5, 12, 26, 0.95)", backdropFilter: "blur(20px)",
        borderRight: "1px solid var(--border)",
        padding: "1.25rem 1rem",
        display: "flex", flexDirection: "column", gap: "1.25rem",
      }}>
        {/* Configurations List */}
        <div>
          <p className="section-title">Design Blueprints</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
            {configs.map((c) => (
              <div key={c.id} style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
                <button
                  onClick={() => selectConfig(c)}
                  style={{
                    flex: 1, textAlign: "left", padding: "0.6rem 0.75rem",
                    borderRadius: 6,
                    border: `1px solid ${activeConfig?.id === c.id ? "var(--arc-cyan)" : "var(--border-subtle)"}`,
                    background: activeConfig?.id === c.id ? "rgba(0, 240, 255, 0.12)" : "rgba(8, 20, 42, 0.5)",
                    color: activeConfig?.id === c.id ? "var(--arc-cyan)" : "var(--text-secondary)",
                    cursor: "pointer", fontSize: "0.825rem", fontWeight: 600,
                    boxShadow: activeConfig?.id === c.id ? "0 0 15px rgba(0, 240, 255, 0.2)" : "none",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    minWidth: 0,
                  }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {c.is_baseline && <span style={{ color: "var(--success)", marginRight: "0.4rem" }}>●</span>}
                    {c.label}
                  </span>
                  <span style={{ fontSize: "0.7rem", fontFamily: "monospace", color: "var(--text-muted)", flexShrink: 0, marginLeft: "0.35rem" }}>
                    {c.ns}S×{c.np}P
                  </span>
                </button>
                {configs.length > 1 && (
                  <button
                    className="btn-danger"
                    style={{ padding: "0.55rem 0.5rem", borderRadius: 6, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfigToDelete({ id: c.id, label: c.label });
                    }}
                    title="Delete design variant"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            ))}
            <button className="btn-secondary" style={{ fontSize: "0.78rem", padding: "0.45rem", justifyContent: "center" }} onClick={addConfig}>
              + Clone / New Variant
            </button>
          </div>
        </div>

        <hr className="divider" style={{ margin: 0 }} />

        {/* Cell Specification */}
        <div>
          <p className="section-title">Core Chemistry</p>
          <select className="select" style={{ fontSize: "0.825rem", marginBottom: "0.5rem" }}
            value={selectedCellId ?? ""}
            onChange={(e) => setSelectedCellId(e.target.value ? +e.target.value : null)}>
            <option value="">— Select Cell Model —</option>
            {cells.map((c) => (
              <option key={c.id} value={c.id}>
                {c.manufacturer} {c.model} ({c.form_factor || "21700"} · {c.nominal_capacity_ah}Ah)
              </option>
            ))}
          </select>
        </div>

        {/* Pack Topology (Ns x Np) */}
        <div>
          <p className="section-title">Pack Architecture</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <div className="field">
              <label className="label">Series (Ns)</label>
              <input className="input" type="number" min={1} max={32} value={ns} onChange={(e) => setNs(e.target.value)} />
            </div>
            <div className="field">
              <label className="label">Parallel (Np)</label>
              <input className="input" type="number" min={1} max={24} value={np} onChange={(e) => setNp(e.target.value)} />
            </div>
          </div>
          <div style={{ fontSize: "0.72rem", color: "var(--arc-cyan)", fontFamily: "monospace", display: "flex", justifyContent: "space-between" }}>
            <span>TOTAL CELLS:</span>
            <span style={{ fontWeight: 700 }}>{totalCells} UNITS</span>
          </div>
        </div>

        {/* Thermal System */}
        <div>
          <p className="section-title">Thermal Dissipation</p>
          <select className="select" style={{ fontSize: "0.825rem", marginBottom: "0.75rem" }}
            value={cooling} onChange={(e) => setCooling(e.target.value)}>
            <option value="passive">Passive Convection</option>
            <option value="fan">Forced Air / Fan-Cooled</option>
            <option value="liquid">Liquid Cooling Cold Plate</option>
            <option value="phase_change">Phase-Change Matrix</option>
          </select>
        </div>

        <button className="btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={saveConfig} disabled={saving}>
          {saving ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Syncing Rig…</> : <><Save size={15} /> Save Blueprint</>}
        </button>

        {saveSuccess && (
          <div style={{
            fontSize: "0.75rem",
            color: "#10b981",
            background: "rgba(16, 185, 129, 0.12)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            borderRadius: 6,
            padding: "0.4rem 0.6rem",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            fontWeight: 600,
          }}>
            <span>✓</span> Blueprint Synced to Database
          </div>
        )}

        {error && <div style={{ fontSize: "0.75rem", color: "var(--danger)" }}>{error}</div>}
      </div>

      {/* ── Center 3D Stark Holotable Viewport ── */}
      <div style={{ flex: 1, position: "relative", overflow: "hidden", background: "#020408" }}>
        {/* Background Arc Hologram Aura */}
        <div style={{
          position: "absolute", inset: 0,
          background: "radial-gradient(circle at 50% 50%, rgba(0, 240, 255, 0.12) 0%, rgba(0, 100, 200, 0.04) 50%, transparent 80%)",
          pointerEvents: "none",
        }} />

        {/* 3D Visualizer Canvas */}
        <StarkBatteryVisualizer
          key={`${ns}-${np}-${cooling}`}
          ns={+ns || 14}
          np={+np || 8}
          coolingType={cooling}
          showEnclosure={showEnclosure}
          colorMode={isSimulating ? "simulation" : colorMode}
          exploded={exploded}
          explodeAmount={explodeAmount}
          isSimulating={isSimulating}
          simTimeS={simTimeS}
          simCurrentA={liveCurrentA}
          simSoc={liveSoc}
          simTempC={liveTempC}
          showDimensions={showDimensions}
          cellDiameterMm={cellDiamMm}
          cellHeightMm={cellHeightMm}
          packLengthMm={packLengthMm}
          packWidthMm={packWidthMm}
          packHeightMm={packHeightMm}
        />

        {/* ── Top HUD Floating Command Bar ── */}
        <div style={{
          position: "absolute", top: 16, left: "50%", transform: "translateX(-50%)",
          display: "flex", gap: "0.625rem", alignItems: "center",
          background: "rgba(5, 12, 26, 0.85)", backdropFilter: "blur(16px)",
          border: "1px solid var(--border)", borderRadius: 8, padding: "0.4rem 0.875rem",
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.8)",
          zIndex: 20,
        }}>
          {/* Exploded View Toggle */}
          <button
            onClick={() => {
              const next = !exploded;
              setExploded(next);
              setExplodeAmount(next ? 0.85 : 0);
            }}
            style={{
              background: exploded ? "rgba(0, 240, 255, 0.2)" : "transparent",
              border: `1px solid ${exploded ? "var(--arc-cyan)" : "transparent"}`,
              borderRadius: 6, padding: "0.4rem 0.75rem",
              cursor: "pointer", display: "flex", alignItems: "center", gap: "0.4rem",
              color: exploded ? "var(--arc-cyan)" : "var(--text-secondary)",
              fontSize: "0.78rem", fontWeight: 700,
              boxShadow: exploded ? "0 0 15px rgba(0, 240, 255, 0.3)" : "none",
            }}
          >
            <Orbit size={15} />
            <span>EXPLODED ASSEMBLY</span>
          </button>

          {/* Thermal Vision Mode Toggle */}
          <button
            onClick={() => setColorMode((m) => m === "thermal" ? "default" : "thermal")}
            style={{
              background: colorMode === "thermal" ? "rgba(239, 68, 68, 0.2)" : "transparent",
              border: `1px solid ${colorMode === "thermal" ? "var(--danger)" : "transparent"}`,
              borderRadius: 6, padding: "0.4rem 0.75rem",
              cursor: "pointer", display: "flex", alignItems: "center", gap: "0.4rem",
              color: colorMode === "thermal" ? "var(--danger)" : "var(--text-secondary)",
              fontSize: "0.78rem", fontWeight: 700,
            }}
          >
            <Thermometer size={15} />
            <span>THERMAL GRADIENT</span>
          </button>

          {/* Enclosure Shell Toggle */}
          <button
            onClick={() => setShowEnclosure((v) => !v)}
            style={{
              background: showEnclosure ? "rgba(0, 240, 255, 0.1)" : "transparent",
              border: `1px solid ${showEnclosure ? "rgba(0, 240, 255, 0.3)" : "transparent"}`,
              borderRadius: 6, padding: "0.4rem 0.75rem",
              cursor: "pointer", display: "flex", alignItems: "center", gap: "0.4rem",
              color: showEnclosure ? "var(--arc-cyan)" : "var(--text-secondary)",
              fontSize: "0.78rem", fontWeight: 600,
            }}
          >
            <Box size={15} />
            <span>ENCLOSURE CASING</span>
          </button>

          {/* 3D Physical CAD & Cell Dimensions Toggle */}
          <button
            onClick={() => setShowDimensions((v) => !v)}
            style={{
              background: showDimensions ? "rgba(0, 240, 255, 0.2)" : "transparent",
              border: `1px solid ${showDimensions ? "var(--arc-cyan)" : "transparent"}`,
              borderRadius: 6, padding: "0.4rem 0.75rem",
              cursor: "pointer", display: "flex", alignItems: "center", gap: "0.4rem",
              color: showDimensions ? "var(--arc-cyan)" : "var(--text-secondary)",
              fontSize: "0.78rem", fontWeight: 700,
              boxShadow: showDimensions ? "0 0 15px rgba(0, 240, 255, 0.3)" : "none",
            }}
          >
            <Ruler size={15} />
            <span>3D DIMENSIONS</span>
          </button>

          {/* 3D Animated Simulation Trigger */}
          <button
            onClick={() => {
              setIsSimulating(!isSimulating);
              if (!isSimulating) setColorMode("simulation");
            }}
            className={isSimulating ? "btn-danger" : "btn-gold"}
            style={{ padding: "0.4rem 0.875rem", fontSize: "0.78rem" }}
          >
            {isSimulating ? <Pause size={14} /> : <Play size={14} />}
            <span>{isSimulating ? "HALT SIMULATION" : "RUN SIMULATION"}</span>
          </button>
        </div>

        {/* ── Explode Granular Slider ── */}
        <div style={{
          position: "absolute", top: 76, left: "50%", transform: "translateX(-50%)",
          display: "flex", alignItems: "center", gap: "0.75rem",
          background: "rgba(5, 12, 26, 0.8)", backdropFilter: "blur(12px)",
          border: "1px solid var(--border-subtle)", borderRadius: 20, padding: "0.25rem 1rem",
          fontSize: "0.72rem", color: "var(--arc-cyan)", fontFamily: "monospace",
          zIndex: 20,
        }}>
          <span>EXPLODED OFFSET:</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={explodeAmount}
            onChange={(e) => {
              const val = +e.target.value;
              setExplodeAmount(val);
              setExploded(val > 0.05);
            }}
            style={{ width: 140, accentColor: "var(--arc-cyan)", cursor: "pointer" }}
          />
          <span>{(explodeAmount * 100).toFixed(0)}%</span>
        </div>

        {/* ── Real-time Simulation Telemetry HUD Overlay ── */}
        {isSimulating && (
          <div style={{
            position: "absolute", bottom: 20, left: 20,
            background: "rgba(4, 10, 24, 0.9)", backdropFilter: "blur(16px)",
            border: "1px solid var(--arc-cyan)", borderRadius: 8,
            padding: "0.875rem 1.25rem", color: "#e6f7ff",
            boxShadow: "0 0 30px rgba(0, 240, 255, 0.3)",
            fontFamily: "monospace", minWidth: 260,
            zIndex: 20,
          }} className="hud-bracket">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid rgba(0,240,255,0.3)", paddingBottom: 4, marginBottom: 8 }}>
              <span style={{ color: "var(--arc-cyan)", fontWeight: 800 }}>LIVE 3D SIMULATION</span>
              <span style={{ color: "#00ffaa", fontSize: "0.7rem", animation: "pulse 1.5s infinite" }}>● ACTIVE</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: "0.8rem" }}>
              <span style={{ color: "var(--text-muted)" }}>TIMESTAMP:</span>
              <span style={{ color: "var(--arc-cyan)" }}>{(simTimeS / 60).toFixed(1)} MIN</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: "0.8rem" }}>
              <span style={{ color: "var(--text-muted)" }}>PACK VOLTAGE:</span>
              <span>{liveVoltage.toFixed(1)} V</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: "0.8rem" }}>
              <span style={{ color: "var(--text-muted)" }}>DISCHARGE CURRENT:</span>
              <span style={{ color: "#00ffaa" }}>{liveCurrentA.toFixed(1)} A</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: "0.8rem" }}>
              <span style={{ color: "var(--text-muted)" }}>CORE TEMP:</span>
              <span style={{ color: liveTempC > 45 ? "var(--danger)" : "var(--stark-gold)" }}>{liveTempC.toFixed(1)} °C</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: "0.8rem" }}>
              <span style={{ color: "var(--text-muted)" }}>OHMIC LOSS:</span>
              <span style={{ color: "var(--danger)" }}>{livePowerLossW.toFixed(1)} W</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
              <span style={{ color: "var(--text-muted)" }}>SOC REMAINING:</span>
              <span style={{ color: "var(--arc-cyan)" }}>{(liveSoc * 100).toFixed(1)} %</span>
            </div>
          </div>
        )}

        {/* ── Thermal Colormap Legend ── */}
        {colorMode === "thermal" && (
          <div style={{
            position: "absolute", bottom: 20, right: 20,
            background: "rgba(4, 10, 24, 0.85)", backdropFilter: "blur(12px)",
            border: "1px solid var(--border)", borderRadius: 8,
            padding: "0.75rem 1rem", color: "#e6f7ff",
            fontFamily: "monospace", fontSize: "0.75rem",
            zIndex: 20,
          }}>
            <div style={{ color: "var(--arc-cyan)", fontWeight: 700, marginBottom: 6 }}>THERMAL IR COLORTEMP</div>
            <div style={{
              width: 140, height: 12, borderRadius: 3,
              background: "linear-gradient(90deg, #0055ff, #00f0ff, #00ff88, #ffbb00, #ff0044)",
              marginBottom: 4,
            }} />
            <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-muted)", fontSize: "0.7rem" }}>
              <span>20°C</span>
              <span>35°C</span>
              <span>50°C</span>
              <span>65°C+</span>
            </div>
          </div>
        )}

        <div style={{
          position: "absolute", bottom: 12, left: "50%", transform: "translateX(-50%)",
          fontSize: "0.7rem", color: "var(--text-muted)", fontFamily: "monospace",
          background: "rgba(3, 8, 20, 0.75)", padding: "0.3rem 0.875rem", borderRadius: 100,
          border: "1px solid rgba(0, 240, 255, 0.15)",
          zIndex: 10,
        }}>
          DRAG TO ORBIT · SCROLL TO ZOOM · CLICK ANY CELL FOR TELEMETRY
        </div>
      </div>

      {/* ── Right Telemetry Panel ── */}
      <div style={{
        width: 290, flexShrink: 0, overflowY: "auto",
        background: "rgba(5, 12, 26, 0.95)", backdropFilter: "blur(20px)",
        borderLeft: "1px solid var(--border)",
        padding: "1.25rem 1rem",
        display: "flex", flexDirection: "column", gap: "1.25rem",
      }}>
        <div>
          <p className="section-title">Pack Telemetry</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {[
              { label: "Nominal Pack Voltage", value: `${calcV.toFixed(1)} V`, note: `${ns}S × ${selectedCell?.nominal_voltage_v ?? 3.7}V` },
              { label: "Capacity", value: `${calcAh.toFixed(1)} Ah`, note: `${np}P × ${selectedCell?.nominal_capacity_ah ?? 5}Ah` },
              { label: "Gross Energy", value: `${(calcWh / 1000).toFixed(2)} kWh`, note: `${calcWh.toFixed(0)} Wh` },
              { label: "Usable Energy", value: `${((calcWh * +socWindow) / 1000).toFixed(2)} kWh`, note: `${(+socWindow * 100).toFixed(0)}% SOC window` },
              {
                label: "Total Cell Mass",
                value: selectedCell?.mass_kg != null
                  ? `${(totalCells * selectedCell.mass_kg).toFixed(2)} kg`
                  : "— (cell mass not in library)",
                note: selectedCell?.mass_kg != null
                  ? `${totalCells} cells × ${(selectedCell.mass_kg * 1000).toFixed(0)}g (Manufacturer Spec)`
                  : "⚠ Cell mass missing from library",
                badge: selectedCell?.mass_kg != null ? "Manufacturer Spec" : "Unavailable",
                badgeColor: selectedCell?.mass_kg != null ? "var(--arc-cyan)" : "var(--danger)",
              },
              {
                label: "Total Pack Mass",
                value: massBreakdown?.total_pack_mass_kg != null
                  ? `${massBreakdown.total_pack_mass_kg.toFixed(2)} kg`
                  : selectedCell?.mass_kg != null
                    ? `${(totalCells * selectedCell.mass_kg).toFixed(2)} kg (cells only)`
                    : "Unavailable",
                note: massBreakdown?.total_pack_mass_kg != null
                  ? `${(massBreakdown.cell_to_pack_mass_ratio! * 100).toFixed(1)}% cell ratio · ${massBreakdown.gravimetric_energy_density_pack_wh_per_kg?.toFixed(0)} Wh/kg pack`
                  : "Pack hardware sizing unmodeled",
                badge: massBreakdown?.total_pack_mass_kg != null ? "Engineering Model" : "Cells Only",
                badgeColor: massBreakdown?.total_pack_mass_kg != null ? "#10b981" : "#f59e0b",
              },
            ].map((m) => (
              <div key={m.label} style={{
                background: "rgba(8, 20, 42, 0.6)", border: "1px solid var(--border-subtle)",
                borderRadius: 6, padding: "0.6rem 0.75rem",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 2 }}>
                  <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>{m.label}</span>
                  {m.badge && (
                    <span style={{
                      fontSize: "0.62rem", padding: "0.1rem 0.35rem", borderRadius: 4,
                      background: "rgba(255,255,255,0.05)", border: `1px solid ${m.badgeColor}`,
                      color: m.badgeColor, fontWeight: 600,
                    }}>
                      {m.badge}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--arc-cyan)", fontFamily: "monospace" }}>{m.value}</div>
                {m.note && <div style={{ fontSize: "0.65rem", color: "var(--text-secondary)", marginTop: 2 }}>{m.note}</div>}
              </div>
            ))}

            {/* Expandable Transparent Component Mass Breakdown */}
            {massBreakdown?.components && (
              <div style={{
                background: "rgba(6, 15, 32, 0.7)", border: "1px solid rgba(0, 240, 255, 0.2)",
                borderRadius: 6, padding: "0.6rem 0.75rem", fontSize: "0.75rem",
              }}>
                <button
                  onClick={() => setShowMassDetails(!showMassDetails)}
                  style={{
                    background: "transparent", border: "none", color: "var(--arc-cyan)",
                    cursor: "pointer", padding: 0, width: "100%", display: "flex",
                    justifyContent: "space-between", alignItems: "center", fontWeight: 700,
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                    <Layers size={13} /> Pack Mass Breakdown
                  </span>
                  {showMassDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>

                {showMassDetails && (
                  <div style={{ marginTop: "0.6rem", display: "flex", flexDirection: "column", gap: "0.35rem", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.5rem" }}>
                    {Object.entries(massBreakdown.components).map(([key, comp]) => (
                      <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.7rem" }}>
                        <span style={{ color: "var(--text-secondary)" }}>{comp.label}</span>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontFamily: "monospace" }}>
                          <span style={{ color: "#f8fafc", fontWeight: 600 }}>{comp.mass_kg != null ? `${comp.mass_kg.toFixed(2)} kg` : "—"}</span>
                          <span style={{ color: "var(--text-muted)", fontSize: "0.65rem" }}>{comp.fraction_pct != null ? `(${comp.fraction_pct.toFixed(1)}%)` : ""}</span>
                        </div>
                      </div>
                    ))}
                    <div style={{ marginTop: "0.3rem", fontSize: "0.63rem", color: "#64748b", fontStyle: "italic", borderTop: "1px dashed rgba(255,255,255,0.08)", paddingTop: "0.3rem" }}>
                      * Cell mass from manufacturer datasheet; structural and cooling hardware from 1st-principles engineering sizing.
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <hr className="divider" style={{ margin: 0 }} />

        {/* Requirements Delta Check */}
        {req && (
          <div>
            <p className="section-title">Specification Targets</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem" }}>
                <span style={{ color: "var(--text-muted)" }}>Target Voltage:</span>
                <span style={{ color: calcV >= (req.target_voltage_v ?? 48) ? "var(--success)" : "var(--warning)" }}>
                  {calcV.toFixed(1)}V / {req.target_voltage_v}V
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem" }}>
                <span style={{ color: "var(--text-muted)" }}>Target Energy:</span>
                <span style={{ color: calcWh >= (req.target_energy_wh ?? 2000) ? "var(--success)" : "var(--warning)" }}>
                  {calcWh.toFixed(0)}Wh / {req.target_energy_wh}Wh
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <Link href={`/projects/${projectId}/simulation`} style={{ textDecoration: "none" }}>
            <button className="btn-primary" style={{ width: "100%", justifyContent: "center" }}>
              <Play size={15} /> Run Simulation
            </button>
          </Link>
          <Link href={`/projects/${projectId}/compare`} style={{ textDecoration: "none" }}>
            <button className="btn-secondary" style={{ width: "100%", justifyContent: "center" }}>
              Compare Blueprints
            </button>
          </Link>
        </div>
      </div>

      {/* ── Delete Configuration Confirmation Modal ── */}
      {configToDelete && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 100,
          background: "rgba(3, 7, 18, 0.8)", backdropFilter: "blur(8px)",
          display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem",
        }}>
          <div
            className="card hud-bracket"
            style={{
              maxWidth: 440, width: "100%", background: "rgba(6, 14, 28, 0.98)",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              boxShadow: "0 24px 64px rgba(0, 0, 0, 0.9), 0 0 32px rgba(239, 68, 68, 0.15)",
              padding: "1.75rem", borderRadius: 10,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.85rem", marginBottom: "1rem" }}>
              <div style={{
                width: 40, height: 40, borderRadius: 8,
                background: "rgba(239, 68, 68, 0.14)", border: "1px solid rgba(239, 68, 68, 0.4)",
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}>
                <Trash2 size={20} color="var(--danger)" />
              </div>
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                  Delete Design Variant
                </h3>
                <span style={{ fontSize: "0.68rem", fontFamily: "monospace", color: "var(--danger)", letterSpacing: "0.05em" }}>
                  IRREVERSIBLE ACTION
                </span>
              </div>
            </div>

            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: "1.5rem" }}>
              Are you sure you want to delete <strong style={{ color: "#f8fafc" }}>&ldquo;{configToDelete.label}&rdquo;</strong>?
              This CAD configuration and its multi-physics parameters will be permanently removed.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
              <button
                className="btn-secondary"
                onClick={() => setConfigToDelete(null)}
                disabled={deletingConfigId !== null}
                style={{ padding: "0.55rem 1.1rem" }}
              >
                Cancel
              </button>
              <button
                className="btn-danger"
                style={{
                  padding: "0.55rem 1.25rem", fontSize: "0.825rem", fontWeight: 700,
                  display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer",
                }}
                disabled={deletingConfigId !== null}
                onClick={confirmDeleteConfig}
              >
                <Trash2 size={14} />
                {deletingConfigId === configToDelete.id ? "Deleting…" : "Confirm Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
