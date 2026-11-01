"use client";

import { use, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  Configuration,
  ScenarioRead,
  DutyCycleSegment,
} from "@/lib/api";
import {
  Play,
  AlertCircle,
  Thermometer,
  Zap,
  Clock,
  Orbit,
  Activity,
  Box,
  Car,
  Plus,
  Trash2,
} from "lucide-react";

const StarkBatteryVisualizer = dynamic(
  () => import("@/components/battery-3d/StarkBatteryVisualizer").then((m) => m.StarkBatteryVisualizer),
  { ssr: false, loading: () => <div className="spinner" style={{ margin: "auto" }} /> }
);

export default function SimulationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = +id;
  const router = useRouter();

  const [configs, setConfigs] = useState<Configuration[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioRead[]>([]);
  const [selectedCfg, setSelectedCfg] = useState<number | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<number | null>(null);
  const [runLabel, setRunLabel] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Duty cycle segments for active scenario
  const [segments, setSegments] = useState<DutyCycleSegment[]>([]);
  const [showAddSegment, setShowAddSegment] = useState(false);
  const [newSegDuration, setNewSegDuration] = useState(60);
  const [newSegType, setNewSegType] = useState("steady_cruise");
  const [newSegCurrent, setNewSegCurrent] = useState<number | undefined>(undefined);

  // New Custom Scenario quick-create state
  const [showNewScenario, setShowNewScenario] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customAmbTemp, setCustomAmbTemp] = useState(25.0);
  const [customDuration, setCustomDuration] = useState(3600);
  const [customCurrent, setCustomCurrent] = useState<number | undefined>(40.0);
  const [customAgeingR, setCustomAgeingR] = useState(1.0);
  const [customAgeingC, setCustomAgeingC] = useState(0.0);

  // 3D Preview Toggles
  const [exploded, setExploded] = useState(false);
  const [showEnclosure, setShowEnclosure] = useState(true);

  // Multi-Node Thermal & Aging Mode State
  const [thermalModel, setThermalModel] = useState<"lumped" | "multi_node">("multi_node");
  const [isCommitted, setIsCommitted] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [cfgData, scData] = await Promise.all([
          api.projects.configurations.list(projectId),
          api.scenarios.list(),
        ]);
        if (active) {
          setConfigs(cfgData);
          setScenarios(scData);
          const baseline = cfgData.find((c) => c.is_baseline) ?? cfgData[0];
          if (baseline) setSelectedCfg(baseline.id);
          if (scData[0]) setSelectedScenario(scData[0].id);
          setLoading(false);
        }
      } catch (e: unknown) {
        if (active) {
          setError(e instanceof Error ? e.message : "Failed to load simulation environment");
          setLoading(false);
        }
      }
    })();
    return () => { active = false; };
  }, [projectId]);

  // Load segments whenever selectedScenario changes
  useEffect(() => {
    if (!selectedScenario) return;
    let active = true;
    api.scenarios.listSegments(selectedScenario)
      .then((data) => {
        if (active) setSegments(data);
      })
      .catch(() => {
        if (active) setSegments([]);
      });
    return () => { active = false; };
  }, [selectedScenario]);

  async function runSim() {
    if (!selectedCfg || !selectedScenario) {
      setError("Please select both a configuration and a test scenario.");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const result = await api.simulations.run(selectedCfg, {
        configuration_id: selectedCfg,
        scenario_id: selectedScenario,
        run_label: runLabel || undefined,
        enable_multi_node_thermal: thermalModel === "multi_node",
        is_committed: isCommitted,
      });
      router.push(`/projects/${projectId}/results/${result.simulation_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Simulation execution failed");
      setRunning(false);
    }
  }

  // Create scenario handler
  const handleCreateScenario = async () => {
    if (!customName.trim()) {
      setError("Scenario name is required");
      return;
    }
    setError(null);
    try {
      const created = await api.scenarios.create({
        name: customName.trim(),
        ambient_temp_c: customAmbTemp,
        initial_cell_temp_c: customAmbTemp,
        duration_s: customDuration,
        discharge_current_a: customCurrent && customCurrent > 0 ? customCurrent : undefined,
        resistance_multiplier: customAgeingR,
        capacity_variation_pct: customAgeingC,
        profile_type: "steady_cruise",
      });
      setScenarios((prev) => [created, ...prev]);
      setSelectedScenario(created.id);
      setShowNewScenario(false);
      setCustomName("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create scenario");
    }
  };

  // Add segment handler
  const handleAddSegment = async () => {
    if (!selectedScenario) return;
    try {
      const seg = await api.scenarios.addSegment(selectedScenario, {
        segment_index: segments.length,
        duration_s: newSegDuration,
        profile_type: newSegType,
        discharge_current_a: newSegCurrent !== undefined ? newSegCurrent : undefined,
      });
      setSegments((prev) => [...prev, seg]);
      setShowAddSegment(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add segment");
    }
  };

  // Delete segment handler
  const handleDeleteSegment = async (segId: number) => {
    if (!selectedScenario) return;
    try {
      await api.scenarios.deleteSegment(selectedScenario, segId);
      setSegments((prev) => prev.filter((s) => s.id !== segId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete segment");
    }
  };

  const activeCfg = configs.find((c) => c.id === selectedCfg);
  const activeScenario = scenarios.find((s) => s.id === selectedScenario);

  return (
    <div style={{ maxWidth: 1150, margin: "0 auto" }} className="fade-in">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.75rem" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
            <Activity size={20} color="var(--arc-cyan)" />
            <h1 style={{ fontSize: "1.65rem", fontWeight: 800, letterSpacing: "-0.02em", color: "#f8fafc", margin: 0 }}>
              Simulation Launch Deck
            </h1>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", fontFamily: "monospace", margin: 0 }}>
            MULTI-PHYSICS TRANSIENT SOLVER // BATTLAB
          </p>
        </div>

        <Link href={`/projects/${projectId}/vehicle-load`} style={{ textDecoration: "none" }}>
          <button className="btn-secondary" style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.82rem" }}>
            <Car size={15} color="var(--arc-cyan)" /> Calculate Demand From Vehicle Route
          </button>
        </Link>
      </div>

      {loading ? (
        <div style={{ display: "flex", gap: "1rem", alignItems: "center", justifyContent: "center", height: "50vh", color: "var(--arc-cyan)" }}>
          <div className="spinner" style={{ width: 32, height: 32 }} />
          <span style={{ fontFamily: "monospace" }}>INITIALIZING SOLVER MATRICES…</span>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "1.5rem" }}>
          {/* Left Column: Selectors */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            
            {/* Configuration Selector */}
            <div className="card hud-bracket">
              <p className="section-title">1. Select Target Pack Blueprint</p>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {configs.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedCfg(c.id)}
                    style={{
                      textAlign: "left", padding: "0.875rem",
                      borderRadius: 8,
                      border: `1px solid ${selectedCfg === c.id ? "var(--arc-cyan)" : "var(--border-subtle)"}`,
                      background: selectedCfg === c.id ? "rgba(0, 240, 255, 0.12)" : "rgba(8, 20, 42, 0.5)",
                      cursor: "pointer", transition: "all 0.2s",
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: "0.875rem", color: selectedCfg === c.id ? "var(--arc-cyan)" : "var(--text-primary)", marginBottom: "0.25rem" }}>
                      {c.is_baseline && <span style={{ color: "var(--success)", marginRight: 4 }}>●</span>}
                      {c.label}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>
                      {c.ns}S × {c.np}P · {c.cooling_type} cooling
                      {c.calc_nominal_voltage_v && ` · ${c.calc_nominal_voltage_v.toFixed(1)} V`}
                      {c.calc_nominal_energy_wh && ` · ${c.calc_nominal_energy_wh.toFixed(0)} Wh`}
                      {c.calc_cell_mass_kg && ` · ${c.calc_cell_mass_kg.toFixed(2)} kg cells`}
                    </div>
                    {!c.cell_spec_id && (
                      <div style={{ fontSize: "0.72rem", color: "var(--warning)", marginTop: "0.35rem", display: "flex", gap: "0.3rem", alignItems: "center" }}>
                        <AlertCircle size={12} /> No cell spec chosen — simulation will fail
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Scenario Selector */}
            <div className="card hud-bracket">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <p className="section-title" style={{ margin: 0 }}>2. Select Operating Scenario &amp; Environmental Conditions</p>
                <button
                  onClick={() => setShowNewScenario(!showNewScenario)}
                  style={{
                    background: "rgba(0,240,255,0.08)", border: "1px solid rgba(0,240,255,0.3)",
                    color: "var(--arc-cyan)", borderRadius: 4, padding: "0.2rem 0.6rem", fontSize: "0.72rem",
                    cursor: "pointer", display: "flex", alignItems: "center", gap: "0.3rem",
                  }}
                >
                  <Plus size={12} /> Custom Scenario
                </button>
              </div>

              {/* Quick Custom Scenario Creator Drawer */}
              {showNewScenario && (
                <div style={{
                  background: "rgba(8, 20, 42, 0.9)", border: "1px solid var(--arc-cyan)",
                  borderRadius: 8, padding: "1rem", marginBottom: "0.85rem",
                  display: "flex", flexDirection: "column", gap: "0.75rem",
                }}>
                  <div style={{ fontWeight: 700, fontSize: "0.82rem", color: "var(--arc-cyan)" }}>
                    Configure Environmental Scenario &amp; Discharge Rate
                  </div>

                  <div>
                    <label style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "block", marginBottom: 3 }}>Scenario Name</label>
                    <input
                      className="input"
                      placeholder="e.g. Desert Highway 40°C or Freezing Commute -10°C"
                      value={customName}
                      onChange={(e) => setCustomName(e.target.value)}
                      style={{ width: "100%", fontSize: "0.8rem", padding: "0.4rem 0.6rem" }}
                    />
                  </div>

                  {/* Temperature Presets */}
                  <div>
                    <label style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "block", marginBottom: 3 }}>
                      Ambient &amp; Initial Temperature: {customAmbTemp}°C
                    </label>
                    <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                      {[
                        { label: "-10°C Sub-Zero", t: -10.0 },
                        { label: "0°C Freezing", t: 0.0 },
                        { label: "25°C Standard", t: 25.0 },
                        { label: "40°C High Temp", t: 40.0 },
                      ].map((preset) => (
                        <button
                          key={preset.label}
                          onClick={() => setCustomAmbTemp(preset.t)}
                          style={{
                            background: customAmbTemp === preset.t ? "rgba(0,240,255,0.2)" : "rgba(10,25,50,0.6)",
                            border: `1px solid ${customAmbTemp === preset.t ? "var(--arc-cyan)" : "var(--border-subtle)"}`,
                            color: customAmbTemp === preset.t ? "var(--arc-cyan)" : "var(--text-secondary)",
                            borderRadius: 4, padding: "0.25rem 0.5rem", fontSize: "0.7rem", cursor: "pointer",
                          }}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Discharge Current */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                    <div>
                      <label style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "block", marginBottom: 3 }}>Discharge Current (A)</label>
                      <input
                        type="number"
                        className="input"
                        placeholder="Leave empty for 1C"
                        value={customCurrent ?? ""}
                        onChange={(e) => setCustomCurrent(e.target.value ? Number(e.target.value) : undefined)}
                        style={{ width: "100%", fontSize: "0.8rem", padding: "0.4rem 0.6rem" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "block", marginBottom: 3 }}>Duration (seconds)</label>
                      <input
                        type="number"
                        className="input"
                        value={customDuration}
                        onChange={(e) => setCustomDuration(Number(e.target.value))}
                        style={{ width: "100%", fontSize: "0.8rem", padding: "0.4rem 0.6rem" }}
                      />
                    </div>
                  </div>

                  {/* Ageing Presets */}
                  <div>
                    <label style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "block", marginBottom: 3 }}>
                      Cell Ageing Sensitivity Preset:
                    </label>
                    <div style={{ display: "flex", gap: "0.4rem" }}>
                      {[
                        { label: "Fresh (R×1.0, C-0%)", r: 1.0, c: 0.0 },
                        { label: "Moderate (R×1.3, C-10%)", r: 1.3, c: 10.0 },
                        { label: "Aged EOL (R×1.6, C-20%)", r: 1.6, c: 20.0 },
                      ].map((ag) => (
                        <button
                          key={ag.label}
                          onClick={() => {
                            setCustomAgeingR(ag.r);
                            setCustomAgeingC(ag.c);
                          }}
                          style={{
                            background: customAgeingR === ag.r ? "rgba(0,240,255,0.2)" : "rgba(10,25,50,0.6)",
                            border: `1px solid ${customAgeingR === ag.r ? "var(--arc-cyan)" : "var(--border-subtle)"}`,
                            color: customAgeingR === ag.r ? "var(--arc-cyan)" : "var(--text-secondary)",
                            borderRadius: 4, padding: "0.25rem 0.5rem", fontSize: "0.68rem", cursor: "pointer",
                          }}
                        >
                          {ag.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.25rem" }}>
                    <button
                      onClick={() => setShowNewScenario(false)}
                      style={{ background: "transparent", border: "1px solid var(--border)", color: "var(--text-muted)", borderRadius: 4, padding: "0.3rem 0.75rem", fontSize: "0.75rem", cursor: "pointer" }}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleCreateScenario}
                      className="btn-primary"
                      style={{ padding: "0.3rem 0.85rem", fontSize: "0.75rem" }}
                    >
                      Save &amp; Select Scenario
                    </button>
                  </div>
                </div>
              )}

              {/* Scenarios List */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", maxHeight: 260, overflowY: "auto" }}>
                {scenarios.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSelectedScenario(s.id)}
                    style={{
                      textAlign: "left", padding: "0.75rem 0.875rem",
                      borderRadius: 8,
                      border: `1px solid ${selectedScenario === s.id ? "var(--arc-cyan)" : "var(--border-subtle)"}`,
                      background: selectedScenario === s.id ? "rgba(0, 240, 255, 0.12)" : "rgba(8, 20, 42, 0.5)",
                      cursor: "pointer", transition: "all 0.2s",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                      <span style={{ fontWeight: 700, fontSize: "0.875rem", color: selectedScenario === s.id ? "var(--arc-cyan)" : "var(--text-primary)" }}>
                        {s.name}
                      </span>
                      {s.discharge_current_a && (
                        <span style={{ fontSize: "0.7rem", color: "#f59e0b", fontFamily: "monospace", background: "rgba(245,158,11,0.1)", padding: "0.1rem 0.4rem", borderRadius: 3 }}>
                          {s.discharge_current_a} A
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "flex", gap: "0.75rem", flexWrap: "wrap", fontFamily: "monospace" }}>
                      <span><Thermometer size={12} style={{ display: "inline" }} /> {s.ambient_temp_c}°C AMB</span>
                      <span><Clock size={12} style={{ display: "inline" }} /> {(s.duration_s / 60).toFixed(0)} MIN</span>
                      <span><Zap size={12} style={{ display: "inline" }} /> {s.profile_type.toUpperCase()}</span>
                      {s.resistance_multiplier > 1.0 && (
                        <span style={{ color: "var(--warning)" }}>R×{s.resistance_multiplier.toFixed(1)}</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>

              {/* Duty Cycle Segments Inspection and Builder */}
              {activeScenario && (
                <div style={{ marginTop: "1rem", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.75rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                    <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--arc-cyan)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                      Duty Cycle Segments ({segments.length})
                    </span>
                    <button
                      onClick={() => setShowAddSegment(!showAddSegment)}
                      style={{
                        background: "rgba(0,240,255,0.06)", border: "1px solid rgba(0,240,255,0.2)",
                        color: "var(--arc-cyan)", borderRadius: 4, padding: "0.15rem 0.5rem", fontSize: "0.68rem",
                        cursor: "pointer", display: "flex", alignItems: "center", gap: "0.2rem",
                      }}
                    >
                      <Plus size={11} /> Add Segment
                    </button>
                  </div>

                  {/* Add Segment inline */}
                  {showAddSegment && (
                    <div style={{
                      background: "rgba(6,15,32,0.85)", border: "1px solid var(--border)",
                      borderRadius: 6, padding: "0.6rem", marginBottom: "0.5rem",
                      display: "flex", gap: "0.4rem", alignItems: "center", flexWrap: "wrap",
                    }}>
                      <select
                        value={newSegType}
                        onChange={(e) => setNewSegType(e.target.value)}
                        style={{ background: "#030814", color: "#f8fafc", border: "1px solid var(--border)", borderRadius: 4, padding: "0.25rem 0.4rem", fontSize: "0.72rem" }}
                      >
                        <option value="steady_cruise">Cruise</option>
                        <option value="rest">Rest (0A)</option>
                        <option value="high_load">High Load</option>
                        <option value="mixed">Mixed</option>
                        <option value="regen">Regen Braking</option>
                      </select>
                      <input
                        type="number"
                        placeholder="Duration (s)"
                        value={newSegDuration}
                        onChange={(e) => setNewSegDuration(Number(e.target.value))}
                        style={{ width: 85, background: "#030814", color: "#f8fafc", border: "1px solid var(--border)", borderRadius: 4, padding: "0.25rem 0.4rem", fontSize: "0.72rem" }}
                      />
                      <input
                        type="number"
                        placeholder="Current (A)"
                        value={newSegCurrent ?? ""}
                        onChange={(e) => setNewSegCurrent(e.target.value ? Number(e.target.value) : undefined)}
                        style={{ width: 85, background: "#030814", color: "#f8fafc", border: "1px solid var(--border)", borderRadius: 4, padding: "0.25rem 0.4rem", fontSize: "0.72rem" }}
                      />
                      <button
                        onClick={handleAddSegment}
                        className="btn-primary"
                        style={{ padding: "0.25rem 0.6rem", fontSize: "0.7rem" }}
                      >
                        Add
                      </button>
                    </div>
                  )}

                  {segments.length === 0 ? (
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                      Single profile: runs at {activeScenario.discharge_current_a ? `${activeScenario.discharge_current_a}A` : "1C default"} for {activeScenario.duration_s}s.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                      {segments.map((seg, i) => (
                        <div
                          key={seg.id}
                          style={{
                            display: "flex", justifyContent: "space-between", alignItems: "center",
                            background: "rgba(8, 20, 42, 0.4)", border: "1px solid var(--border-subtle)",
                            borderRadius: 4, padding: "0.3rem 0.6rem", fontSize: "0.72rem", fontFamily: "monospace",
                          }}
                        >
                          <div>
                            <span style={{ color: "var(--arc-cyan)", marginRight: 6 }}>#{i}</span>
                            <span>{seg.profile_type}</span>
                            <span style={{ color: "var(--text-muted)", marginLeft: 6 }}>{seg.duration_s}s</span>
                            {seg.discharge_current_a !== undefined && (
                              <span style={{ color: "#f59e0b", marginLeft: 6 }}>{seg.discharge_current_a}A</span>
                            )}
                          </div>
                          <button
                            onClick={() => handleDeleteSegment(seg.id)}
                            style={{ background: "transparent", border: "none", color: "var(--danger)", cursor: "pointer", padding: "0 0.2rem" }}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 3. Solver Fidelity & Aging Mode Selection */}
            <div className="card hud-bracket">
              <p className="section-title" style={{ margin: "0 0 0.75rem 0" }}>3. Thermal Network Fidelity &amp; Battery Aging Mode</p>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "0.75rem" }}>
                {/* Thermal Network Choice */}
                <div style={{ background: "rgba(8,20,42,0.6)", padding: "0.75rem", borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
                  <label style={{ fontSize: "0.72rem", color: "var(--arc-cyan)", fontWeight: 700, display: "block", marginBottom: "0.4rem" }}>
                    THERMAL MODEL FIDELITY
                  </label>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                    <label style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", color: thermalModel === "multi_node" ? "var(--arc-cyan)" : "var(--text-secondary)" }}>
                      <input
                        type="radio"
                        name="thermal_model"
                        value="multi_node"
                        checked={thermalModel === "multi_node"}
                        onChange={() => setThermalModel("multi_node")}
                      />
                      <span>3-Node Network (Core / Surface / Plate)</span>
                    </label>
                    <label style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", color: thermalModel === "lumped" ? "var(--arc-cyan)" : "var(--text-secondary)" }}>
                      <input
                        type="radio"
                        name="thermal_model"
                        value="lumped"
                        checked={thermalModel === "lumped"}
                        onChange={() => setThermalModel("lumped")}
                      />
                      <span>Lumped 1st-Order (Single Node)</span>
                    </label>
                  </div>
                </div>

                {/* Aging Operational Mode */}
                <div style={{ background: "rgba(8,20,42,0.6)", padding: "0.75rem", borderRadius: 6, border: "1px solid var(--border-subtle)" }}>
                  <label style={{ fontSize: "0.72rem", color: "var(--arc-cyan)", fontWeight: 700, display: "block", marginBottom: "0.4rem" }}>
                    OPERATIONAL AGING SEMANTICS
                  </label>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                    <label style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", color: !isCommitted ? "var(--arc-cyan)" : "var(--text-secondary)" }}>
                      <input
                        type="radio"
                        name="aging_mode"
                        checked={!isCommitted}
                        onChange={() => setIsCommitted(false)}
                      />
                      <span>Preview Mode (Read-Only / No History)</span>
                    </label>
                    <label style={{ fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer", color: isCommitted ? "var(--arc-cyan)" : "var(--text-secondary)" }}>
                      <input
                        type="radio"
                        name="aging_mode"
                        checked={isCommitted}
                        onChange={() => setIsCommitted(true)}
                      />
                      <span>Committed Record (Accumulate EFC)</span>
                    </label>
                  </div>
                </div>
              </div>

              <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                Multi-node models internal radial core-to-surface and plate gradients. Aging applies SEI parabolic kinetics to compute incremental SOH &amp; throughput.
              </div>
            </div>

            {/* Run Label & Launch Button */}
            <div className="card hud-bracket">
              <div className="field" style={{ marginBottom: "1rem" }}>
                <label className="label">Simulation Run Identifier (Optional)</label>
                <input
                  className="input"
                  value={runLabel}
                  onChange={(e) => setRunLabel(e.target.value)}
                  placeholder={`${activeCfg?.label ?? "14S8P"} // ${activeScenario?.name ?? "Full Discharge"} // Run 1`}
                />
              </div>

              <button
                className="btn-primary"
                style={{ width: "100%", justifyContent: "center", padding: "0.875rem", fontSize: "0.95rem" }}
                onClick={runSim}
                disabled={running || !selectedCfg || !selectedScenario}
              >
                {running ? (
                  <>
                    <div className="spinner" style={{ width: 18, height: 18 }} />
                    EXECUTING TRANSIENT MULTI-PHYSICS SOLVER…
                  </>
                ) : (
                  <>
                    <Play size={18} />
                    LAUNCH TRANSIENT SIMULATION
                  </>
                )}
              </button>

              {error && (
                <div style={{ marginTop: "0.875rem", display: "flex", gap: "0.5rem", alignItems: "center", color: "var(--danger)", fontSize: "0.85rem" }}>
                  <AlertCircle size={16} /> {error}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Interactive 3D Pack Preview */}
          <div className="card hud-bracket" style={{ padding: "1.25rem", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <span className="section-title" style={{ margin: 0 }}>Pack Geometry &amp; Assembly Preview</span>
              <div style={{ display: "flex", gap: "0.4rem" }}>
                <button
                  onClick={() => setExploded(!exploded)}
                  style={{
                    background: exploded ? "rgba(0,240,255,0.2)" : "rgba(8,20,42,0.6)",
                    border: `1px solid ${exploded ? "var(--arc-cyan)" : "var(--border)"}`,
                    borderRadius: 4, padding: "0.25rem 0.5rem",
                    color: exploded ? "var(--arc-cyan)" : "var(--text-secondary)", fontSize: "0.7rem", cursor: "pointer",
                  }}
                >
                  <Orbit size={11} style={{ display: "inline", marginRight: 3 }} />
                  EXPLODE
                </button>
                <button
                  onClick={() => setShowEnclosure(!showEnclosure)}
                  style={{
                    background: "rgba(8,20,42,0.6)",
                    border: "1px solid var(--border)",
                    borderRadius: 4, padding: "0.25rem 0.5rem",
                    color: showEnclosure ? "var(--arc-cyan)" : "var(--text-secondary)", fontSize: "0.7rem", cursor: "pointer",
                  }}
                >
                  <Box size={11} style={{ display: "inline", marginRight: 3 }} />
                  ENCLOSURE
                </button>
              </div>
            </div>

            <div style={{ flex: 1, minHeight: 420, borderRadius: 8, overflow: "hidden", background: "#030814", position: "relative" }}>
              <StarkBatteryVisualizer
                ns={activeCfg?.ns ?? 14}
                np={activeCfg?.np ?? 8}
                coolingType={activeCfg?.cooling_type ?? "passive"}
                showEnclosure={showEnclosure}
                exploded={exploded}
                explodeAmount={exploded ? 0.8 : 0}
              />
              <div style={{
                position: "absolute", bottom: 10, left: "50%", transform: "translateX(-50%)",
                fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "monospace",
                background: "rgba(3,8,20,0.85)", padding: "0.25rem 0.75rem", borderRadius: 100,
                border: "1px solid var(--border-subtle)", whiteSpace: "nowrap",
              }}>
                PREVIEWING: {activeCfg?.ns ?? 14}S × {activeCfg?.np ?? 8}P ({((activeCfg?.ns ?? 14) * (activeCfg?.np ?? 8))} CELLS)
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
