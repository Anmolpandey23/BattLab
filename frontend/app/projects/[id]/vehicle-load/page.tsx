"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  VehicleLoadRequest,
  VehicleLoadResponse,
  Project,
  DriveCycleRequest,
  DriveCycleResponse,
} from "@/lib/api";
import {
  Car,
  Zap,
  ArrowRight,
  TrendingUp,
  Info,
  Sliders,
  CheckCircle2,
  Play,
  RotateCcw,
  Navigation,
  BatteryCharging,
  Gauge,
} from "lucide-react";

export default function VehicleLoadPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = Number(params.id);

  const [project, setProject] = useState<Project | null>(null);
  const [activeTab, setActiveTab] = useState<"steady" | "cycle">("steady");

  // Steady-state Form parameters
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VehicleLoadResponse | null>(null);
  const [appliedMsg, setAppliedMsg] = useState<string | null>(null);

  const [vehicleMassKg, setVehicleMassKg] = useState<number>(120.0);
  const [payloadMassKg, setPayloadMassKg] = useState<number>(75.0);
  const [speedKmh, setSpeedKmh] = useState<number>(35.0);
  const [gradePct, setGradePct] = useState<number>(3.0);
  const [cr, setCr] = useState<number>(0.012);
  const [cd, setCd] = useState<number>(0.6);
  const [frontalAreaM2, setFrontalAreaM2] = useState<number>(0.8);
  const [accelerationMps2, setAccelerationMps2] = useState<number>(0.0);
  const [drivetrainEff, setDrivetrainEff] = useState<number>(0.88);
  const [regenEff, setRegenEff] = useState<number>(0.65);
  const [auxPowerW, setAuxPowerW] = useState<number>(50.0);
  const [nominalBusVoltageV, setNominalBusVoltageV] = useState<number>(51.8);

  // Dynamic Drive Cycle state
  const [selectedCycle, setSelectedCycle] = useState<string>("hill_climb_route");
  const [cycleLoading, setCycleLoading] = useState(false);
  const [cycleResult, setCycleResult] = useState<DriveCycleResponse | null>(null);
  const [exportingScenario, setExportingScenario] = useState(false);

  // Monotonic request ID counter and parameter ref to eliminate asynchronous race conditions and stale closures
  const lastSteadyRequestId = useRef<number>(0);
  const paramsRef = useRef({
    vehicleMassKg,
    payloadMassKg,
    speedKmh,
    gradePct,
    cr,
    cd,
    frontalAreaM2,
    accelerationMps2,
    drivetrainEff,
    regenEff,
    auxPowerW,
    nominalBusVoltageV,
  });

  useEffect(() => {
    paramsRef.current = {
      vehicleMassKg,
      payloadMassKg,
      speedKmh,
      gradePct,
      cr,
      cd,
      frontalAreaM2,
      accelerationMps2,
      drivetrainEff,
      regenEff,
      auxPowerW,
      nominalBusVoltageV,
    };
  });

  // Load project details
  useEffect(() => {
    if (!projectId) return;
    api.projects.get(projectId).then(setProject).catch(() => {});
  }, [projectId]);

  // Recalculate steady state with strict monotonic request ID sequence
  const calculateSteady = async (overrides?: Partial<VehicleLoadRequest>) => {
    const reqId = ++lastSteadyRequestId.current;
    setLoading(true);
    setError(null);
    setAppliedMsg(null);

    const currentParams = paramsRef.current;
    const payload: VehicleLoadRequest = {
      vehicle_mass_kg: overrides?.vehicle_mass_kg ?? currentParams.vehicleMassKg,
      payload_mass_kg: overrides?.payload_mass_kg ?? currentParams.payloadMassKg,
      speed_kmh: overrides?.speed_kmh ?? currentParams.speedKmh,
      grade_pct: overrides?.grade_pct ?? currentParams.gradePct,
      cr: overrides?.cr ?? currentParams.cr,
      cd: overrides?.cd ?? currentParams.cd,
      frontal_area_m2: overrides?.frontal_area_m2 ?? currentParams.frontalAreaM2,
      acceleration_mps2: overrides?.acceleration_mps2 ?? currentParams.accelerationMps2,
      drivetrain_efficiency: overrides?.drivetrain_efficiency ?? currentParams.drivetrainEff,
      regen_efficiency: overrides?.regen_efficiency ?? currentParams.regenEff,
      auxiliary_power_w: overrides?.auxiliary_power_w ?? currentParams.auxPowerW,
      nominal_pack_voltage_v: overrides?.nominal_pack_voltage_v ?? currentParams.nominalBusVoltageV,
    };

    try {
      const res = await api.vehicleLoad.calculate(payload);
      // Discard out-of-order response if a newer request was dispatched
      if (reqId !== lastSteadyRequestId.current) return;
      setResult(res);
    } catch (e: unknown) {
      if (reqId === lastSteadyRequestId.current) {
        setError(e instanceof Error ? e.message : "Calculation failed");
      }
    } finally {
      if (reqId === lastSteadyRequestId.current) {
        setLoading(false);
      }
    }
  };

  // Auto-calculate on input change with 300ms debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      calculateSteady();
    }, 300);
    return () => clearTimeout(timer);
  }, [
    vehicleMassKg,
    payloadMassKg,
    speedKmh,
    gradePct,
    cr,
    cd,
    frontalAreaM2,
    accelerationMps2,
    drivetrainEff,
    regenEff,
    auxPowerW,
    nominalBusVoltageV,
  ]);

  // Quick preset helper with immediate dispatched calculation
  const handlePreset = (preset: {
    label: string;
    grade: number;
    speed: number;
    accel?: number;
  }) => {
    const accel = preset.accel ?? 0.0;
    setGradePct(preset.grade);
    setSpeedKmh(preset.speed);
    setAccelerationMps2(accel);
    paramsRef.current.gradePct = preset.grade;
    paramsRef.current.speedKmh = preset.speed;
    paramsRef.current.accelerationMps2 = accel;
    calculateSteady({
      grade_pct: preset.grade,
      speed_kmh: preset.speed,
      acceleration_mps2: accel,
    });
  };

  // Apply steady current to new simulation scenario
  const applyToSimulation = async () => {
    if (!result) return;
    const dischargeCurrent = Math.max(1.0, Math.abs(result.battery_current_a));
    try {
      const created = await api.scenarios.create({
        name: `Vehicle Load (${gradePct >= 0 ? "+" : ""}${gradePct}% Grade, ${speedKmh} km/h)`,
        description: `Derived from tractive load analysis: ${result.total_mass_kg}kg at ${speedKmh}km/h on ${gradePct}% slope.`,
        duration_s: 1800,
        time_step_s: 1.0,
        profile_type: "steady_cruise",
        discharge_current_a: dischargeCurrent,
        ambient_temp_c: 25.0,
      });
      setAppliedMsg(
        `Scenario created successfully with ${dischargeCurrent.toFixed(1)} A discharge current (ID #${created.id}).`
      );
      setTimeout(() => {
        router.push(`/projects/${projectId}/simulation`);
      }, 1500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create scenario");
    }
  };

  // Run dynamic drive cycle simulation
  const handleSimulateCycle = async () => {
    setCycleLoading(true);
    setError(null);
    try {
      const payload: DriveCycleRequest = {
        cycle_type: selectedCycle,
        vehicle_mass_kg: vehicleMassKg,
        payload_mass_kg: payloadMassKg,
        cr: cr,
        cd: cd,
        frontal_area_m2: frontalAreaM2,
        drivetrain_efficiency: drivetrainEff,
        regen_efficiency: regenEff,
        auxiliary_power_w: auxPowerW,
        nominal_pack_voltage_v: nominalBusVoltageV,
      };
      const res = await api.vehicleLoad.simulateDriveCycle(payload);
      setCycleResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Drive cycle simulation failed");
    } finally {
      setCycleLoading(false);
    }
  };

  // Export drive cycle directly to multi-segment scenario
  const handleExportCycleScenario = async () => {
    if (!cycleResult) return;
    setExportingScenario(true);
    setError(null);
    try {
      const res = await api.vehicleLoad.exportDriveCycleScenario({
        project_id: projectId,
        cycle_type: selectedCycle,
        vehicle_mass_kg: vehicleMassKg,
        payload_mass_kg: payloadMassKg,
        cr: cr,
        cd: cd,
        frontal_area_m2: frontalAreaM2,
        drivetrain_efficiency: drivetrainEff,
        regen_efficiency: regenEff,
        auxiliary_power_w: auxPowerW,
        nominal_pack_voltage_v: nominalBusVoltageV,
        ambient_temp_c: 25.0,
      });
      setAppliedMsg(`Created Scenario "${res.name}" (ID #${res.id}) with dynamic duty-cycle segments!`);
      setTimeout(() => {
        router.push(`/projects/${projectId}/simulation`);
      }, 1800);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to export scenario");
    } finally {
      setExportingScenario(false);
    }
  };

  const presets = [
    { label: "Flat (0%)", grade: 0.0, speed: 45.0, accel: 0.0 },
    { label: "Low Slope (+3%)", grade: 3.0, speed: 35.0, accel: 0.0 },
    { label: "Hill Climb (+8%)", grade: 8.0, speed: 25.0, accel: 0.0 },
    { label: "Steep (+15%)", grade: 15.0, speed: 18.0, accel: 0.0 },
    { label: "Braking / Regen", grade: -5.0, speed: 30.0, accel: 0.0 },
    { label: "High Accel (2 m/s²)", grade: 0.0, speed: 30.0, accel: 2.0 },
  ];

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
            <Car size={22} color="var(--arc-cyan)" />
            <h1 style={{ fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.02em", color: "#f8fafc", margin: 0 }}>
              Vehicle Tractive Load Analysis
            </h1>
          </div>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", margin: 0 }}>
            First-principles longitudinal dynamics: aerodynamic drag, rolling resistance, grade forces, and auxiliary electrical load.
            {project?.name && <span style={{ color: "var(--arc-cyan)" }}> — Project: {project.name}</span>}
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.75rem" }}>
          <Link href={`/projects/${projectId}/simulation`} style={{ textDecoration: "none" }}>
            <button className="btn-secondary" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Play size={14} /> Back to Simulation
            </button>
          </Link>
        </div>
      </div>

      {/* Mode Navigation Bar */}
      <div style={{
        display: "flex", gap: "0.5rem", borderBottom: "1px solid var(--border)", paddingBottom: "0.5rem",
      }}>
        <button
          onClick={() => setActiveTab("steady")}
          style={{
            background: activeTab === "steady" ? "rgba(0, 240, 255, 0.15)" : "transparent",
            border: `1px solid ${activeTab === "steady" ? "var(--arc-cyan)" : "transparent"}`,
            color: activeTab === "steady" ? "var(--arc-cyan)" : "var(--text-muted)",
            borderRadius: 6, padding: "0.45rem 1rem", fontSize: "0.82rem", fontWeight: 700,
            cursor: "pointer", display: "flex", alignItems: "center", gap: "0.4rem",
          }}
        >
          <Gauge size={15} /> Steady Operating Point
        </button>
        <button
          onClick={() => {
            setActiveTab("cycle");
            if (!cycleResult && !cycleLoading) handleSimulateCycle();
          }}
          style={{
            background: activeTab === "cycle" ? "rgba(0, 240, 255, 0.15)" : "transparent",
            border: `1px solid ${activeTab === "cycle" ? "var(--arc-cyan)" : "transparent"}`,
            color: activeTab === "cycle" ? "var(--arc-cyan)" : "var(--text-muted)",
            borderRadius: 6, padding: "0.45rem 1rem", fontSize: "0.82rem", fontWeight: 700,
            cursor: "pointer", display: "flex", alignItems: "center", gap: "0.4rem",
          }}
        >
          <Navigation size={15} /> Dynamic Route &amp; Drive Cycle (WLTP / Hill Climb)
        </button>
      </div>

      {/* Global Alerts */}
      {error && (
        <div style={{
          background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)",
          borderRadius: 8, padding: "0.75rem 1rem", color: "#f87171", fontSize: "0.85rem",
        }}>
          {error}
        </div>
      )}

      {appliedMsg && (
        <div style={{
          background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.4)",
          borderRadius: 8, padding: "0.75rem 1rem", color: "#34d399", fontSize: "0.85rem",
          display: "flex", alignItems: "center", gap: "0.5rem",
        }}>
          <CheckCircle2 size={16} /> {appliedMsg}
        </div>
      )}

      {/* TAB 1: STEADY OPERATING POINT */}
      {activeTab === "steady" && (
        <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1.3fr", gap: "1.5rem" }}>
          {/* Left Column: Vehicle & Route Parameters */}
          <div style={{
            background: "rgba(6, 13, 26, 0.8)", border: "1px solid var(--border)",
            borderRadius: 10, padding: "1.25rem", display: "flex", flexDirection: "column", gap: "1.25rem",
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.75rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Sliders size={18} color="var(--arc-cyan)" />
                <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "#f8fafc" }}>Dynamics &amp; Route Parameters</span>
              </div>
              <button
                onClick={() => calculateSteady()}
                disabled={loading}
                className="btn-primary"
                style={{ padding: "0.35rem 0.85rem", fontSize: "0.78rem" }}
              >
                {loading ? "Computing..." : "Update Load"}
              </button>
            </div>

            {/* Quick Presets */}
            <div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "0.5rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Route / Slope Presets:
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                {presets.map((p) => {
                  const isCurrent =
                    gradePct === p.grade && speedKmh === p.speed && accelerationMps2 === (p.accel ?? 0.0);
                  return (
                    <button
                      key={p.label}
                      onClick={() => handlePreset(p)}
                      style={{
                        background: isCurrent ? "rgba(0,240,255,0.2)" : "rgba(10,25,50,0.5)",
                        border: `1px solid ${isCurrent ? "var(--arc-cyan)" : "var(--border-subtle)"}`,
                        color: isCurrent ? "var(--arc-cyan)" : "var(--text-secondary)",
                        fontWeight: isCurrent ? 700 : 500,
                        borderRadius: 4, padding: "0.3rem 0.6rem", fontSize: "0.74rem", cursor: "pointer",
                      }}
                    >
                      {p.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Form Inputs Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.85rem", fontSize: "0.8rem" }}>
              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Vehicle Curb Mass (kg)</label>
                <input
                  type="number"
                  value={vehicleMassKg}
                  onChange={(e) => setVehicleMassKg(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Payload / Rider (kg)</label>
                <input
                  type="number"
                  value={payloadMassKg}
                  onChange={(e) => setPayloadMassKg(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Vehicle Speed (km/h)</label>
                <input
                  type="number"
                  value={speedKmh}
                  onChange={(e) => setSpeedKmh(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Road Slope / Grade (%)</label>
                <input
                  type="number"
                  value={gradePct}
                  onChange={(e) => setGradePct(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Rolling Coeff (Cr)</label>
                <input
                  type="number"
                  step="0.001"
                  value={cr}
                  onChange={(e) => setCr(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Drag Coeff (Cd)</label>
                <input
                  type="number"
                  step="0.05"
                  value={cd}
                  onChange={(e) => setCd(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Frontal Area (m²)</label>
                <input
                  type="number"
                  step="0.1"
                  value={frontalAreaM2}
                  onChange={(e) => setFrontalAreaM2(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Acceleration (m/s²)</label>
                <input
                  type="number"
                  step="0.5"
                  value={accelerationMps2}
                  onChange={(e) => setAccelerationMps2(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Drivetrain Efficiency</label>
                <input
                  type="number"
                  step="0.02"
                  min="0.1"
                  max="1.0"
                  value={drivetrainEff}
                  onChange={(e) => setDrivetrainEff(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Regen Recovery (0-1)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0.0"
                  max="1.0"
                  value={regenEff}
                  onChange={(e) => setRegenEff(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Auxiliary Power (W)</label>
                <input
                  type="number"
                  value={auxPowerW}
                  onChange={(e) => setAuxPowerW(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>
              <div>
                <label style={{ display: "block", color: "var(--text-muted)", marginBottom: 4 }}>Pack Nominal Bus (V)</label>
                <input
                  type="number"
                  step="0.1"
                  value={nominalBusVoltageV}
                  onChange={(e) => setNominalBusVoltageV(Number(e.target.value))}
                  className="input-field"
                  style={{ width: "100%", padding: "0.45rem 0.6rem" }}
                />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button
                onClick={() => {
                  setVehicleMassKg(120.0);
                  setPayloadMassKg(75.0);
                  setSpeedKmh(35.0);
                  setGradePct(3.0);
                  setCr(0.012);
                  setCd(0.6);
                  setFrontalAreaM2(0.8);
                  setAccelerationMps2(0.0);
                  setDrivetrainEff(0.88);
                  setRegenEff(0.65);
                  setAuxPowerW(50.0);
                  setNominalBusVoltageV(51.8);
                  calculateSteady({
                    vehicle_mass_kg: 120.0,
                    payload_mass_kg: 75.0,
                    speed_kmh: 35.0,
                    grade_pct: 3.0,
                    cr: 0.012,
                    cd: 0.6,
                    frontal_area_m2: 0.8,
                    acceleration_mps2: 0.0,
                    drivetrain_efficiency: 0.88,
                    regen_efficiency: 0.65,
                    auxiliary_power_w: 50.0,
                    nominal_pack_voltage_v: 51.8,
                  });
                }}
                style={{
                  background: "transparent", border: "1px solid var(--border-subtle)",
                  color: "var(--text-muted)", borderRadius: 6, padding: "0.4rem 0.75rem",
                  fontSize: "0.75rem", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.3rem",
                }}
              >
                <RotateCcw size={13} /> Reset Defaults
              </button>
            </div>
          </div>

          {/* Right Column: Output Power, Current, and Tractive Breakdown */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            
            {/* Active Solved Operating Point Status */}
            {result && (
              <div style={{
                background: "rgba(0, 240, 255, 0.05)", border: "1px solid rgba(0, 240, 255, 0.2)",
                borderRadius: 8, padding: "0.5rem 0.85rem", fontSize: "0.76rem",
                display: "flex", alignItems: "center", justifyContent: "space-between",
                fontFamily: "monospace", color: "#94a3b8",
              }}>
                <div>
                  SOLVED POINT: <span style={{ color: "var(--arc-cyan)", fontWeight: 700 }}>{result.speed_kmh} km/h</span> ({(result.speed_mps).toFixed(2)} m/s) · GRADE: <span style={{ color: "var(--arc-cyan)", fontWeight: 700 }}>{(Math.tan(result.grade_rad) * 100).toFixed(1)}%</span> ({(result.grade_rad * 180 / Math.PI).toFixed(2)}°) · TOTAL MASS: <span style={{ color: "#f8fafc" }}>{result.total_mass_kg} kg</span>
                </div>
                <div style={{ fontSize: "0.7rem", color: "#64748b" }}>
                  ρ = 1.225 kg/m³
                </div>
              </div>
            )}

            {/* Primary Metric KPI Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              {/* Battery Electrical Power */}
              <div style={{
                background: "rgba(6, 13, 26, 0.9)", border: "1px solid var(--border)",
                borderRadius: 10, padding: "1.25rem",
              }}>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                  Battery Power Demand
                </div>
                <div style={{
                  fontSize: "2rem", fontWeight: 800, fontFamily: "monospace",
                  color: result && result.p_battery_w < 0 ? "#10b981" : "var(--arc-cyan)",
                }}>
                  {result ? `${result.p_battery_w.toFixed(1)} W` : "—"}
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: 4 }}>
                  {result && result.p_battery_w < 0
                    ? "● REGENERATIVE BRAKING (Charging Pack)"
                    : "● DISCHARGING (Traction Demand)"}
                </div>
              </div>

              {/* Pack Current */}
              <div style={{
                background: "rgba(6, 13, 26, 0.9)", border: "1px solid var(--border)",
                borderRadius: 10, padding: "1.25rem",
              }}>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
                  Battery Pack Current Demand
                </div>
                <div style={{
                  fontSize: "2rem", fontWeight: 800, fontFamily: "monospace",
                  color: result && result.battery_current_a < 0 ? "#10b981" : "#f59e0b",
                }}>
                  {result ? `${result.battery_current_a.toFixed(2)} A` : "—"}
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: 4 }}>
                  {result ? `At nominal ${nominalBusVoltageV.toFixed(1)} V bus (${(result.speed_mps).toFixed(1)} m/s)` : "—"}
                </div>
              </div>
            </div>

            {/* Longitudinal Force Decomposition Table */}
            <div style={{
              background: "rgba(6, 13, 26, 0.85)", border: "1px solid var(--border)",
              borderRadius: 10, padding: "1.25rem",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
                <TrendingUp size={16} color="var(--arc-cyan)" />
                <span style={{ fontWeight: 700, fontSize: "0.9rem", color: "#f8fafc" }}>
                  Longitudinal Tractive Force Breakdown
                </span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.8rem" }}>
                {[
                  { label: "Rolling Resistance (F_rolling)", val: result?.f_rolling_n, formula: "Cr · m · g · cos(θ)" },
                  { label: "Grade Resistance (F_grade)", val: result?.f_grade_n, formula: "m · g · sin(θ)" },
                  { label: "Aerodynamic Drag (F_aero)", val: result?.f_aero_n, formula: "½ · ρ · Cd · A · v²" },
                  { label: "Inertial Force (F_accel)", val: result?.f_accel_n, formula: "m · a" },
                  { label: "Total Tractive Force (F_total)", val: result?.f_total_n, formula: "Σ F_components", highlight: true },
                  { label: "Mechanical Wheel Power (P_mech)", val: result?.p_mech_w, unit: "W", formula: "F_total · v", highlight: true },
                ].map((row) => (
                  <div
                    key={row.label}
                    style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      padding: "0.5rem 0.6rem", borderRadius: 6,
                      background: row.highlight ? "rgba(0,240,255,0.06)" : "rgba(8, 20, 42, 0.4)",
                      border: row.highlight ? "1px solid rgba(0,240,255,0.3)" : "1px solid var(--border-subtle)",
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: row.highlight ? 700 : 500, color: row.highlight ? "#f8fafc" : "var(--text-secondary)" }}>
                        {row.label}
                      </span>
                      <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginLeft: "0.5rem", fontFamily: "monospace" }}>
                        ({row.formula})
                      </span>
                    </div>
                    <div style={{
                      fontFamily: "monospace", fontWeight: 700,
                      color: row.highlight ? "var(--arc-cyan)" : "#e2e8f0",
                    }}>
                      {row.val !== undefined ? `${row.val.toFixed(1)} ${row.unit || "N"}` : "—"}
                    </div>
                  </div>
                ))}
              </div>

              {/* Action button to apply directly to scenario */}
              <div style={{ marginTop: "1.25rem", display: "flex", justifyContent: "flex-end" }}>
                <button
                  onClick={applyToSimulation}
                  disabled={!result || loading}
                  className="btn-primary"
                  style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.6rem 1.25rem" }}
                >
                  <Zap size={15} /> Apply {result?.battery_current_a ? `${Math.abs(result.battery_current_a).toFixed(1)}A` : ""} to Simulation Scenario
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>

            {/* Model Assumptions Accordion */}
            {result && (
              <div style={{
                background: "rgba(6, 13, 26, 0.6)", border: "1px solid var(--border-subtle)",
                borderRadius: 8, padding: "0.85rem 1rem", fontSize: "0.75rem", color: "var(--text-muted)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--arc-cyan)", marginBottom: "0.5rem", fontWeight: 700 }}>
                  <Info size={14} /> Model Assumptions &amp; Invariants:
                </div>
                <ul style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.6 }}>
                  {result.assumptions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: DYNAMIC DRIVE CYCLE & ROUTE SIMULATION */}
      {activeTab === "cycle" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {/* Controls Card */}
          <div style={{
            background: "rgba(6, 13, 26, 0.85)", border: "1px solid var(--border)",
            borderRadius: 10, padding: "1.25rem", display: "flex", flexDirection: "column", gap: "1rem",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Navigation size={18} color="var(--arc-cyan)" />
                <span style={{ fontWeight: 700, fontSize: "1rem", color: "#f8fafc" }}>
                  Standardized Drive Cycles &amp; Elevation Routes
                </span>
              </div>
              <button
                onClick={handleSimulateCycle}
                disabled={cycleLoading}
                className="btn-primary"
                style={{ padding: "0.45rem 1rem", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.4rem" }}
              >
                {cycleLoading ? "Simulating Dynamics..." : <><Play size={14} /> Run Dynamic Route Simulation</>}
              </button>
            </div>

            {/* Route Selection Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
              {[
                {
                  id: "hill_climb_route",
                  title: "Hill Climb Route",
                  desc: "8% sustained climb (25 km/h) followed by -5% downhill with regenerative braking recovery.",
                  meta: "1,200 s · Grade & Regen Focus",
                },
                {
                  id: "wltp_class_1",
                  title: "WLTP Class 1",
                  desc: "Worldwide Harmonized Light Vehicles Test Procedure Class 1 for low-power lightweight vehicles.",
                  meta: "1,022 s · Multi-Phase Standard",
                },
                {
                  id: "urban_delivery",
                  title: "Urban Delivery Route",
                  desc: "Frequent acceleration bursts (2.0 m/s²) and stop-and-go delivery cycles.",
                  meta: "900 s · High Acceleration Bursts",
                },
              ].map((c) => (
                <div
                  key={c.id}
                  onClick={() => setSelectedCycle(c.id)}
                  style={{
                    background: selectedCycle === c.id ? "rgba(0, 240, 255, 0.12)" : "rgba(8, 20, 42, 0.5)",
                    border: `1px solid ${selectedCycle === c.id ? "var(--arc-cyan)" : "var(--border-subtle)"}`,
                    borderRadius: 8, padding: "0.85rem", cursor: "pointer",
                    display: "flex", flexDirection: "column", gap: "0.35rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: 700, color: selectedCycle === c.id ? "var(--arc-cyan)" : "#f8fafc", fontSize: "0.85rem" }}>
                      {c.title}
                    </span>
                    {selectedCycle === c.id && <span style={{ color: "var(--arc-cyan)", fontSize: "0.75rem" }}>● Active</span>}
                  </div>
                  <div style={{ fontSize: "0.74rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                    {c.desc}
                  </div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "monospace", marginTop: "auto" }}>
                    {c.meta}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Cycle Results Display */}
          {cycleResult && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              {/* High-level KPI Cards */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "0.75rem" }}>
                {[
                  { label: "Net Energy", value: `${cycleResult.net_energy_consumed_wh.toFixed(1)} Wh`, sub: `Gross: ${cycleResult.gross_energy_discharged_wh.toFixed(1)} Wh` },
                  { label: "Specific Efficiency", value: `${cycleResult.specific_consumption_wh_per_km.toFixed(1)} Wh/km`, sub: `Over ${cycleResult.total_distance_km.toFixed(2)} km` },
                  { label: "Regen Energy Recovered", value: `${cycleResult.regen_energy_recovered_wh.toFixed(1)} Wh`, sub: `${cycleResult.regen_recovery_pct.toFixed(1)}% recovery fraction` },
                  { label: "Peak Traction Power", value: `${(cycleResult.peak_traction_power_w / 1000).toFixed(2)} kW`, sub: `Current: ${cycleResult.peak_discharge_current_a.toFixed(1)} A` },
                  { label: "Cycle Duration", value: `${(cycleResult.duration_s / 60).toFixed(1)} min`, sub: `${cycleResult.duration_s} seconds total` },
                ].map((kpi) => (
                  <div key={kpi.label} style={{
                    background: "rgba(6, 13, 26, 0.9)", border: "1px solid var(--border)",
                    borderRadius: 8, padding: "0.85rem 1rem",
                  }}>
                    <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      {kpi.label}
                    </div>
                    <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--arc-cyan)", fontFamily: "monospace", marginTop: 4 }}>
                      {kpi.value}
                    </div>
                    <div style={{ fontSize: "0.68rem", color: "var(--text-secondary)", marginTop: 2 }}>
                      {kpi.sub}
                    </div>
                  </div>
                ))}
              </div>

              {/* Action Bar: Export to Scenario */}
              <div style={{
                background: "rgba(6, 15, 32, 0.8)", border: "1px solid rgba(0, 240, 255, 0.3)",
                borderRadius: 8, padding: "1rem 1.25rem", display: "flex", justifyContent: "space-between", alignItems: "center",
              }}>
                <div>
                  <div style={{ fontWeight: 700, color: "#f8fafc", fontSize: "0.9rem" }}>
                    Export Dynamic Route to Multi-Physics Battery Simulation
                  </div>
                  <div style={{ color: "var(--text-muted)", fontSize: "0.78rem" }}>
                    Creates a persistent simulation scenario composed of chronologically staged duty-cycle segments.
                  </div>
                </div>
                <button
                  onClick={handleExportCycleScenario}
                  disabled={exportingScenario}
                  className="btn-primary"
                  style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.55rem 1.25rem", fontSize: "0.82rem" }}
                >
                  <BatteryCharging size={16} />
                  {exportingScenario ? "Generating Duty Segments..." : "Create Simulation Scenario with this Route"}
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
