"use client";
import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import Image from "next/image";
import {
  BatteryCharging, ChevronRight, Thermometer, Box, Orbit,
  ShieldCheck, Flame, Layers, ArrowUpRight,
  Cpu, Wind
} from "lucide-react";

const StarkBatteryVisualizer = dynamic(
  () => import("@/components/battery-3d/StarkBatteryVisualizer").then((m) => m.StarkBatteryVisualizer),
  {
    ssr: false,
    loading: () => (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", minHeight: 480, gap: "1rem", color: "var(--arc-cyan)" }}>
        <div className="spinner" style={{ width: 36, height: 36 }} />
        <span style={{ fontFamily: "monospace", fontSize: "0.8rem", letterSpacing: "0.1em" }}>INITIALIZING 3D BATTERY CAD ENGINE…</span>
      </div>
    )
  }
);

interface ChemistryPreset {
  name: string;
  fullName: string;
  tag: string;
  vNom: number;
  capAh: number;
  massKg: number;
  maxContA: number;
  energyDensityWhKg: number;
  cycleLife: number;
  runawayTempC: number;
  color: string;
  advantage: string;
}

const CHEM_PRESETS: Record<string, ChemistryPreset> = {
  NMC: {
    name: "NMC 21700",
    fullName: "Nickel Manganese Cobalt (LiNiMnCoO2)",
    tag: "High Specific Energy Density",
    vNom: 3.7,
    capAh: 5.0,
    massKg: 0.070,
    maxContA: 10.0,
    energyDensityWhKg: 264,
    cycleLife: 1500,
    runawayTempC: 210,
    color: "var(--arc-cyan)",
    advantage: "Superior gravimetric energy density for passenger EVs and long-range mobility.",
  },
  LFP: {
    name: "LFP 26650",
    fullName: "Lithium Iron Phosphate (LiFePO4)",
    tag: "Extreme Thermal Safety & Longevity",
    vNom: 3.2,
    capAh: 3.0,
    massKg: 0.090,
    maxContA: 6.0,
    energyDensityWhKg: 107,
    cycleLife: 4000,
    runawayTempC: 270,
    color: "#10b981",
    advantage: "Exceptional chemical stability, fire resistance, and 4,000+ deep discharge cycles.",
  },
  NCA: {
    name: "NCA 18650",
    fullName: "Nickel Cobalt Aluminum (LiNiCoAlO2)",
    tag: "High Discharge C-Rate",
    vNom: 3.6,
    capAh: 3.5,
    massKg: 0.048,
    maxContA: 10.0,
    energyDensityWhKg: 262,
    cycleLife: 1200,
    runawayTempC: 195,
    color: "#f59e0b",
    advantage: "High continuous power output and rapid discharge for high-performance powertrains.",
  },
  LTO: {
    name: "LTO 23680",
    fullName: "Lithium Titanate (Li4Ti5O12)",
    tag: "Ultra-Fast Charging & Sub-Zero Ops",
    vNom: 2.3,
    capAh: 10.0,
    massKg: 0.280,
    maxContA: 100.0,
    energyDensityWhKg: 82,
    cycleLife: 20000,
    runawayTempC: 340,
    color: "#a855f7",
    advantage: "Zero dendrite risk, 10C ultra-fast charging, operates down to -30°C without plating.",
  },
};

export default function LandingPage() {
  const [exploded, setExploded] = useState(false);
  const [colorMode, setColorMode] = useState<"default" | "thermal">("default");
  const [showEnclosure, setShowEnclosure] = useState(true);

  // Interactive Live Architecture Synthesizer
  const [chemKey, setChemKey] = useState<"NMC" | "LFP" | "NCA" | "LTO">("NMC");
  const [ns, setNs] = useState(14);
  const [np, setNp] = useState(8);

  // Thermal demonstration state
  const [dischargeRate, setDischargeRate] = useState(1.5); // C-rate

  const selectedChem = CHEM_PRESETS[chemKey];

  // Dynamic Pack Metrics
  const packStats = useMemo(() => {
    const totalCells = ns * np;
    const vNom = ns * selectedChem.vNom;
    const capAh = np * selectedChem.capAh;
    const energyWh = vNom * capAh;
    const cellMassKg = totalCells * selectedChem.massKg;
    const estPackMassKg = cellMassKg * 1.25; // 25% overhead for busbars, BMS, cooling & enclosure
    const specificEnergyWhKg = energyWh / estPackMassKg;
    const contCurrentA = np * selectedChem.maxContA;
    const peakPowerKw = (vNom * contCurrentA * 1.5) / 1000;
    const internalResistanceMo = (25.0 * ns) / np; // approximate pack IR

    return {
      totalCells,
      vNom,
      capAh,
      energyWh,
      cellMassKg,
      estPackMassKg,
      specificEnergyWhKg,
      contCurrentA,
      peakPowerKw,
      internalResistanceMo,
    };
  }, [ns, np, selectedChem]);

  // Dynamic Multi-Node Thermal Estimates for Demonstrator
  const thermalSim = useMemo(() => {
    const currentA = dischargeRate * packStats.capAh;
    const ohmicLossW = Math.pow(currentA, 2) * (packStats.internalResistanceMo / 1000);
    const ambientT = 25.0;
    // Core (70% mass, higher thermal resistance)
    const deltaCore = (ohmicLossW * 0.70) / (packStats.estPackMassKg * 0.45);
    const coreTempC = ambientT + Math.min(deltaCore * 0.22, 52.0);
    // Surface (30% mass, closer to cooling boundary)
    const surfaceTempC = ambientT + Math.min(deltaCore * 0.14, 38.0);
    // Cold plate
    const plateTempC = ambientT + Math.min(deltaCore * 0.05, 12.0);

    return {
      currentA,
      ohmicLossW,
      coreTempC,
      surfaceTempC,
      plateTempC,
    };
  }, [dischargeRate, packStats]);

  return (
    <div style={{ backgroundColor: "#030712", minHeight: "100vh", color: "#f8fafc", overflowX: "hidden" }}>
      {/* ── Top Navigation Bar ── */}
      <nav style={{
        position: "sticky", top: 0, zIndex: 50,
        backgroundColor: "rgba(3, 7, 18, 0.94)",
        backdropFilter: "blur(20px)",
        borderBottom: "1px solid rgba(0, 240, 255, 0.15)",
        padding: "0 clamp(1rem, 3vw, 2.5rem)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: "64px",
      }}>
        {/* Brand Logo */}
        <Link href="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "0.85rem" }}>
          <div style={{
            width: 44, height: 44, borderRadius: 10,
            background: "rgba(0, 240, 255, 0.06)",
            border: "1px solid rgba(0, 240, 255, 0.35)",
            boxShadow: "0 0 20px rgba(0, 240, 255, 0.25)",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            padding: "2px",
          }}>
            <Image src="/logo-mark.png" alt="BattLab" width={38} height={38} style={{ objectFit: "contain" }} priority />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: "1.2rem", letterSpacing: "0.06em", color: "#f8fafc", lineHeight: 1.1 }}>
              <span style={{ color: "var(--arc-cyan)" }}>BATT</span>LAB
            </div>
            <div style={{ fontSize: "0.62rem", color: "var(--text-secondary)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
              Battery Design Software
            </div>
          </div>
        </Link>

        {/* Desktop Quick Nav */}
        <div className="hidden lg:flex" style={{ alignItems: "center", gap: "2rem" }}>
          {[
            { label: "3D CAD STUDIO", href: "#studio" },
            { label: "TOPOLOGY SYNTHESIZER", href: "#synthesizer" },
            { label: "MULTI-NODE THERMAL", href: "#thermal" },
            { label: "CHEMISTRY MATRIX", href: "#chemistry" },
            { label: "SAFETY PROTOCOLS", href: "#safety" },
          ].map((l) => (
            <a key={l.label} href={l.href} style={{
              color: "var(--text-secondary)", fontSize: "0.76rem", fontFamily: "monospace",
              letterSpacing: "0.06em", textDecoration: "none", transition: "color 0.2s",
            }}
              onMouseOver={(e) => ((e.target as HTMLElement).style.color = "var(--arc-cyan)")}
              onMouseOut={(e) => ((e.target as HTMLElement).style.color = "var(--text-secondary)")}
            >{l.label}</a>
          ))}
        </div>

        {/* Clean Enter Studio Actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <Link href="/library" className="hidden sm:inline-block" style={{ textDecoration: "none" }}>
            <button className="btn-secondary" style={{ padding: "0.45rem 0.9rem", fontSize: "0.78rem" }}>
              <Layers size={13} /> Cell Library
            </button>
          </Link>

          <Link href="/dashboard" style={{ textDecoration: "none" }}>
            <button className="btn-primary" style={{ padding: "0.5rem 1.15rem", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.45rem" }}>
              ENTER STUDIO <ChevronRight size={14} />
            </button>
          </Link>
        </div>
      </nav>

      {/* ── Main Hero Section (Balanced Side-by-Side 5fr / 7fr on Desktop) ── */}
      <section id="studio" style={{
        padding: "clamp(2rem, 3.5vw, 3rem) clamp(1rem, 3vw, 2.5rem)",
        maxWidth: 1440, margin: "0 auto", position: "relative",
      }}>
        {/* Subtle background glow aura */}
        <div className="hero-glow-aura" />

        <div className="hero-layout-grid" style={{ position: "relative", zIndex: 1 }}>
          
          {/* ── Left Column: Headlines, Metrics & Actions ── */}
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
            
            {/* Status Pill */}
            <div style={{
              display: "inline-flex", alignItems: "center", gap: "0.5rem",
              background: "rgba(0, 240, 255, 0.06)", border: "1px solid rgba(0, 240, 255, 0.22)",
              padding: "0.3rem 0.75rem", borderRadius: 100, marginBottom: "1.25rem", width: "fit-content",
            }}>
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981" }} />
              <span style={{ color: "var(--arc-cyan)", fontSize: "0.72rem", fontWeight: 700, fontFamily: "monospace", letterSpacing: "0.06em" }}>
                TRANSIENT SOLVER ONLINE // 0.1ms TIME STEP
              </span>
            </div>

            {/* Main Headline */}
            <h1 style={{
              fontSize: "clamp(2.1rem, 3.6vw, 3.2rem)", fontWeight: 900,
              lineHeight: 1.14, letterSpacing: "-0.03em", marginBottom: "1.1rem",
              color: "#ffffff",
            }}>
              Next-Gen Battery CAD &amp; Multi-Physics
              <span style={{
                display: "block",
                background: "linear-gradient(135deg, #00f0ff 0%, #38bdf8 50%, #10b981 100%)",
                WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
              }}>
                Simulation Platform.
              </span>
            </h1>

            {/* Subtitle */}
            <p style={{
              fontSize: "0.95rem", color: "var(--text-secondary)", lineHeight: 1.6,
              marginBottom: "1.75rem", maxWidth: 540,
            }}>
              Synthesize series-parallel pack architectures, inspect micro-welded busbars in interactive exploded 3D CAD,
              evaluate multi-node transient heat rejection, and screen vehicle tractive loads before committing hardware.
            </p>

            {/* Primary Action Buttons */}
            <div style={{ display: "flex", gap: "0.85rem", flexWrap: "wrap", marginBottom: "1.75rem" }}>
              <Link href="/dashboard" style={{ textDecoration: "none" }}>
                <button className="btn-primary" style={{ padding: "0.8rem 1.65rem", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "0.55rem" }}>
                  <BatteryCharging size={17} /> Launch 3D Pack Studio
                </button>
              </Link>
              <Link href="/projects/new" style={{ textDecoration: "none" }}>
                <button className="btn-secondary" style={{ padding: "0.8rem 1.45rem", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "0.55rem" }}>
                  <Cpu size={17} /> + New Battery Project
                </button>
              </Link>
            </div>

            {/* Quick Architecture Preset Switcher */}
            <div className="card hud-bracket" style={{ padding: "1.1rem", background: "rgba(6, 13, 26, 0.85)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                <span style={{ fontSize: "0.72rem", fontFamily: "monospace", color: "var(--arc-cyan)", fontWeight: 700 }}>
                  QUICK ARCHITECTURE PRESETS
                </span>
                <span style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontFamily: "monospace" }}>
                  DYNAMIC 3D COUPLING
                </span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem" }}>
                {[
                  { label: "14S8P 51.8V", nsVal: 14, npVal: 8, chem: "NMC" as const, desc: "LEV / E-Scooter" },
                  { label: "16S12P 59.2V", nsVal: 16, npVal: 12, chem: "NMC" as const, desc: "Urban EV Compact" },
                  { label: "16S8P 51.2V", nsVal: 16, npVal: 8, chem: "LFP" as const, desc: "Commercial ESS" },
                ].map((item) => {
                  const active = ns === item.nsVal && np === item.npVal && chemKey === item.chem;
                  return (
                    <button
                      key={item.label}
                      onClick={() => {
                        setNs(item.nsVal);
                        setNp(item.npVal);
                        setChemKey(item.chem);
                      }}
                      style={{
                        padding: "0.55rem 0.5rem", borderRadius: 6,
                        background: active ? "rgba(0, 240, 255, 0.16)" : "rgba(0, 240, 255, 0.04)",
                        border: `1px solid ${active ? "var(--arc-cyan)" : "rgba(0, 240, 255, 0.15)"}`,
                        color: active ? "#ffffff" : "var(--text-secondary)",
                        cursor: "pointer", textAlign: "left", transition: "all 0.18s",
                      }}
                    >
                      <div style={{ fontSize: "0.76rem", fontWeight: 700, fontFamily: "monospace", color: active ? "var(--arc-cyan)" : "#f8fafc" }}>
                        {item.label}
                      </div>
                      <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", marginTop: "2px" }}>
                        {item.desc}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

          </div>

          {/* ── Right Column: Interactive 3D Pack Studio Holotable ── */}
          <div style={{
            position: "relative", minHeight: 520, height: "100%", borderRadius: 12, overflow: "hidden",
            border: "1px solid rgba(0, 240, 255, 0.28)", backgroundColor: "#040914",
            boxShadow: "0 16px 64px rgba(0, 0, 0, 0.85), 0 0 32px rgba(0, 240, 255, 0.06)",
            display: "flex", flexDirection: "column",
          }}>
            {/* Top 3D In-Canvas Toolbar */}
            <div style={{
              position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)",
              display: "flex", gap: "0.45rem", zIndex: 10, flexWrap: "wrap", justifyContent: "center",
              backgroundColor: "rgba(5, 12, 26, 0.92)", backdropFilter: "blur(14px)",
              border: "1px solid rgba(0, 240, 255, 0.25)", borderRadius: 8, padding: "0.35rem 0.65rem",
              boxShadow: "0 8px 24px rgba(0, 0, 0, 0.7)",
            }}>
              <button
                onClick={() => setExploded(!exploded)}
                style={{
                  background: exploded ? "rgba(0, 240, 255, 0.22)" : "transparent",
                  border: `1px solid ${exploded ? "var(--arc-cyan)" : "transparent"}`,
                  borderRadius: 4, padding: "0.3rem 0.6rem",
                  color: exploded ? "var(--arc-cyan)" : "var(--text-secondary)", fontSize: "0.72rem", fontWeight: 700,
                  cursor: "pointer", display: "flex", alignItems: "center", gap: "0.35rem",
                  transition: "all 0.2s",
                }}
              >
                <Orbit size={13} />
                <span>{exploded ? "COLLAPSE PACK" : "EXPLODE 3D CAD"}</span>
              </button>

              <button
                onClick={() => setColorMode((m) => m === "thermal" ? "default" : "thermal")}
                style={{
                  background: colorMode === "thermal" ? "rgba(239, 68, 68, 0.2)" : "transparent",
                  border: `1px solid ${colorMode === "thermal" ? "var(--danger)" : "transparent"}`,
                  borderRadius: 4, padding: "0.3rem 0.6rem",
                  color: colorMode === "thermal" ? "var(--danger)" : "var(--text-secondary)", fontSize: "0.72rem", fontWeight: 700,
                  cursor: "pointer", display: "flex", alignItems: "center", gap: "0.35rem",
                  transition: "all 0.2s",
                }}
              >
                <Thermometer size={13} />
                <span>THERMAL FLUX</span>
              </button>

              <button
                onClick={() => setShowEnclosure(!showEnclosure)}
                style={{
                  background: "transparent",
                  border: "1px solid transparent",
                  borderRadius: 4, padding: "0.3rem 0.6rem",
                  color: showEnclosure ? "var(--arc-cyan)" : "var(--text-secondary)", fontSize: "0.72rem",
                  cursor: "pointer", display: "flex", alignItems: "center", gap: "0.35rem",
                  transition: "all 0.2s",
                }}
              >
                <Box size={13} />
                <span>ENCLOSURE</span>
              </button>
            </div>

            {/* Top Left Live Architecture Tag */}
            <div style={{
              position: "absolute", top: 12, left: 12, zIndex: 10,
              background: "rgba(3, 7, 18, 0.85)", backdropFilter: "blur(10px)",
              border: "1px solid rgba(0, 240, 255, 0.2)", borderRadius: 6,
              padding: "0.3rem 0.6rem", fontFamily: "monospace", fontSize: "0.7rem",
            }}>
              <span style={{ color: "var(--arc-cyan)", fontWeight: 700 }}>{ns}S{np}P</span>
              <span style={{ color: "var(--text-muted)", marginLeft: "0.4rem" }}>{selectedChem.name}</span>
            </div>

            {/* The 3D Canvas */}
            <div style={{ flex: 1, position: "relative", minHeight: 460 }}>
              <StarkBatteryVisualizer
                ns={Math.min(ns, 16)}
                np={Math.min(np, 12)}
                coolingType="liquid"
                showEnclosure={showEnclosure}
                colorMode={colorMode}
                exploded={exploded}
                explodeAmount={exploded ? 0.85 : 0}
              />
            </div>

            {/* Bottom Telemetry HUD Bar */}
            <div style={{
              position: "absolute", bottom: 12, left: 12, right: 12,
              display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.5rem",
              background: "rgba(3, 7, 18, 0.88)", backdropFilter: "blur(12px)",
              border: "1px solid rgba(0, 240, 255, 0.2)", borderRadius: 8, padding: "0.55rem 0.8rem",
              fontFamily: "monospace",
            }}>
              <div>
                <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", textTransform: "uppercase" }}>VOLTAGE</div>
                <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "var(--arc-cyan)" }}>
                  {packStats.vNom.toFixed(1)} <span style={{ fontSize: "0.68rem", color: "var(--text-secondary)" }}>V</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", textTransform: "uppercase" }}>ENERGY</div>
                <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "#f8fafc" }}>
                  {(packStats.energyWh / 1000).toFixed(2)} <span style={{ fontSize: "0.68rem", color: "var(--text-secondary)" }}>kWh</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", textTransform: "uppercase" }}>CELL COUNT</div>
                <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "#38bdf8" }}>
                  {packStats.totalCells} <span style={{ fontSize: "0.68rem", color: "var(--text-secondary)" }}>cells</span>
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", textTransform: "uppercase" }}>PACK MASS</div>
                <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "#10b981" }}>
                  {packStats.estPackMassKg.toFixed(1)} <span style={{ fontSize: "0.68rem", color: "var(--text-secondary)" }}>kg</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ── Interactive Architecture Synthesizer Section ── */}
      <section id="synthesizer" style={{
        padding: "4.5rem clamp(1rem, 3vw, 2.5rem)",
        background: "rgba(5, 11, 24, 0.95)",
        borderTop: "1px solid rgba(0, 240, 255, 0.15)",
        borderBottom: "1px solid rgba(0, 240, 255, 0.15)",
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: "2.75rem" }}>
            <p className="section-title">PARAMETRIC BATTERY SYNTHESIS</p>
            <h2 style={{ fontSize: "clamp(1.75rem, 2.8vw, 2.4rem)", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em" }}>
              Configure &amp; Evaluate Topologies in Real Time
            </h2>
            <p style={{ color: "var(--text-secondary)", maxWidth: 600, margin: "0.5rem auto 0", fontSize: "0.92rem" }}>
              Adjust series/parallel groupings and chemistry specifications to inspect instantaneous physical pack metrics.
            </p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "2rem" }}>
            {/* Left Controls Card */}
            <div className="card hud-bracket" style={{ padding: "1.75rem", background: "rgba(6, 13, 26, 0.9)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
                <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "#f8fafc" }}>Pack Grouping Controls</span>
                <span style={{ fontSize: "0.72rem", color: "var(--arc-cyan)", fontFamily: "monospace" }}>SYNTHESIS ENGINE</span>
              </div>

              {/* Chemistry Selector */}
              <div style={{ marginBottom: "1.25rem" }}>
                <label style={{ display: "block", fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "0.45rem", fontFamily: "monospace" }}>
                  CELL CHEMISTRY SPECIFICATION
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.45rem" }}>
                  {(["NMC", "LFP", "NCA", "LTO"] as const).map((key) => {
                    const preset = CHEM_PRESETS[key];
                    const active = chemKey === key;
                    return (
                      <button
                        key={key}
                        onClick={() => setChemKey(key)}
                        style={{
                          padding: "0.55rem 0.35rem", borderRadius: 6,
                          background: active ? "rgba(0, 240, 255, 0.18)" : "rgba(0, 240, 255, 0.04)",
                          border: `1px solid ${active ? "var(--arc-cyan)" : "rgba(0, 240, 255, 0.15)"}`,
                          color: active ? "#ffffff" : "var(--text-secondary)",
                          cursor: "pointer", transition: "all 0.15s",
                        }}
                      >
                        <div style={{ fontWeight: 800, fontSize: "0.825rem", color: active ? "var(--arc-cyan)" : "#f8fafc" }}>{key}</div>
                        <div style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>{preset.vNom}V</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Series (Ns) Slider */}
              <div style={{ marginBottom: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                  <label style={{ fontSize: "0.76rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>
                    SERIES CELLS (Ns) — VOLTAGE SCALING
                  </label>
                  <span style={{ fontWeight: 800, color: "var(--arc-cyan)", fontFamily: "monospace" }}>{ns}S ({packStats.vNom.toFixed(1)} V)</span>
                </div>
                <input
                  type="range" min={4} max={96} step={1} value={ns}
                  onChange={(e) => setNs(+e.target.value)}
                  style={{ width: "100%", accentColor: "var(--arc-cyan)", cursor: "pointer" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "2px" }}>
                  <span>4S (14.8V)</span>
                  <span>14S (51.8V)</span>
                  <span>24S (88.8V)</span>
                  <span>96S (355V)</span>
                </div>
              </div>

              {/* Parallel (Np) Slider */}
              <div style={{ marginBottom: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                  <label style={{ fontSize: "0.76rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>
                    PARALLEL CELLS (Np) — CAPACITY &amp; CURRENT
                  </label>
                  <span style={{ fontWeight: 800, color: "var(--arc-cyan)", fontFamily: "monospace" }}>{np}P ({packStats.capAh.toFixed(1)} Ah)</span>
                </div>
                <input
                  type="range" min={1} max={32} step={1} value={np}
                  onChange={(e) => setNp(+e.target.value)}
                  style={{ width: "100%", accentColor: "var(--arc-cyan)", cursor: "pointer" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "2px" }}>
                  <span>1P</span>
                  <span>8P</span>
                  <span>16P</span>
                  <span>32P</span>
                </div>
              </div>
            </div>

            {/* Right Telemetry Matrix Card */}
            <div className="card hud-bracket" style={{ padding: "1.75rem", background: "rgba(6, 13, 26, 0.9)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
                  <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "#f8fafc" }}>Synthesized Physical Pack Specs</span>
                  <span style={{
                    fontSize: "0.65rem", padding: "0.2rem 0.5rem", borderRadius: 4,
                    background: "rgba(16, 185, 129, 0.12)", color: "#10b981", border: "1px solid rgba(16, 185, 129, 0.3)",
                    fontFamily: "monospace",
                  }}>
                    CALCULATED
                  </span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.85rem" }}>
                  <div style={{ background: "rgba(0, 240, 255, 0.04)", border: "1px solid rgba(0, 240, 255, 0.12)", borderRadius: 6, padding: "0.75rem" }}>
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase" }}>NOMINAL ENERGY</div>
                    <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "#f8fafc", fontFamily: "monospace" }}>
                      {(packStats.energyWh / 1000).toFixed(2)} <span style={{ fontSize: "0.75rem", color: "var(--arc-cyan)" }}>kWh</span>
                    </div>
                  </div>

                  <div style={{ background: "rgba(0, 240, 255, 0.04)", border: "1px solid rgba(0, 240, 255, 0.12)", borderRadius: 6, padding: "0.75rem" }}>
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase" }}>SPECIFIC ENERGY</div>
                    <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "#38bdf8", fontFamily: "monospace" }}>
                      {packStats.specificEnergyWhKg.toFixed(1)} <span style={{ fontSize: "0.75rem", color: "var(--arc-cyan)" }}>Wh/kg</span>
                    </div>
                  </div>

                  <div style={{ background: "rgba(0, 240, 255, 0.04)", border: "1px solid rgba(0, 240, 255, 0.12)", borderRadius: 6, padding: "0.75rem" }}>
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase" }}>CONT. DISCHARGE CURRENT</div>
                    <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "#10b981", fontFamily: "monospace" }}>
                      {packStats.contCurrentA.toFixed(0)} <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>A</span>
                    </div>
                  </div>

                  <div style={{ background: "rgba(0, 240, 255, 0.04)", border: "1px solid rgba(0, 240, 255, 0.12)", borderRadius: 6, padding: "0.75rem" }}>
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase" }}>ESTIMATED PEAK POWER</div>
                    <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "#f59e0b", fontFamily: "monospace" }}>
                      {packStats.peakPowerKw.toFixed(1)} <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>kW</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Direct Link into Studio with this Configuration */}
              <div style={{ marginTop: "1.5rem" }}>
                <Link href="/projects/new" style={{ textDecoration: "none" }}>
                  <button className="btn-primary" style={{ width: "100%", justifyContent: "center", padding: "0.75rem" }}>
                    INITIALIZE PROJECT WITH {ns}S{np}P CONFIGURATION <ChevronRight size={16} />
                  </button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Multi-Node Thermal Rejection Simulator Showcase ── */}
      <section id="thermal" style={{
        padding: "4.5rem clamp(1rem, 3vw, 2.5rem)",
        background: "rgba(3, 7, 18, 0.98)",
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: "2.75rem" }}>
            <p className="section-title">COUPLED ELECTRO-THERMAL SOLVER</p>
            <h2 style={{ fontSize: "clamp(1.75rem, 2.8vw, 2.4rem)", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em" }}>
              Multi-Node Heat Rejection &amp; Internal Temperature Gradient
            </h2>
            <p style={{ color: "var(--text-secondary)", maxWidth: 640, margin: "0.5rem auto 0", fontSize: "0.92rem" }}>
              BattLab solves a coupled 3-node thermal network distinguishing cell jelly-roll core (70% mass), surface casing (30% mass), and bottom cold plate buffer (15% mass).
            </p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "2rem" }}>
            {/* Interactive C-Rate Driver */}
            <div className="card hud-bracket" style={{ padding: "1.75rem", background: "rgba(6, 13, 26, 0.9)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
                <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Discharge Load Scenario</span>
                <span style={{ fontSize: "0.72rem", color: "var(--danger)", fontFamily: "monospace" }}>HEAT FLUX</span>
              </div>

              <p style={{ fontSize: "0.825rem", color: "var(--text-secondary)", marginBottom: "1.5rem", lineHeight: 1.5 }}>
                Vary the discharge rate to observe ohmic heating and internal core-to-surface temperature gradients.
              </p>

              <div style={{ marginBottom: "1.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                  <label style={{ fontSize: "0.76rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>
                    DISCHARGE C-RATE
                  </label>
                  <span style={{ fontWeight: 800, color: "var(--danger)", fontFamily: "monospace" }}>{dischargeRate.toFixed(1)} C ({thermalSim.currentA.toFixed(0)} A)</span>
                </div>
                <input
                  type="range" min={0.2} max={3.5} step={0.1} value={dischargeRate}
                  onChange={(e) => setDischargeRate(+e.target.value)}
                  style={{ width: "100%", accentColor: "var(--danger)", cursor: "pointer" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "2px" }}>
                  <span>0.5 C (Gentle)</span>
                  <span>1.0 C (Nominal)</span>
                  <span>2.0 C (Highway)</span>
                  <span>3.5 C (Peak)</span>
                </div>
              </div>

              <div style={{ background: "rgba(0,0,0,0.4)", borderRadius: 6, padding: "0.85rem", border: "1px solid rgba(239, 68, 68, 0.2)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "0.3rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Total Modeled Ohmic Heat:</span>
                  <span style={{ fontWeight: 700, fontFamily: "monospace", color: "#f8fafc" }}>{thermalSim.ohmicLossW.toFixed(0)} W</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "0.3rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Core Allocation (70%):</span>
                  <span style={{ fontWeight: 700, fontFamily: "monospace", color: "var(--danger)" }}>{(thermalSim.ohmicLossW * 0.7).toFixed(0)} W</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem" }}>
                  <span style={{ color: "var(--text-muted)" }}>Surface Allocation (30%):</span>
                  <span style={{ fontWeight: 700, fontFamily: "monospace", color: "var(--warning)" }}>{(thermalSim.ohmicLossW * 0.3).toFixed(0)} W</span>
                </div>
              </div>
            </div>

            {/* 3-Node Thermal Nodes Display */}
            <div className="card hud-bracket" style={{ padding: "1.75rem", background: "rgba(6, 13, 26, 0.9)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
                  <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>Simulated Multi-Node Heat Balance</span>
                  <span style={{ fontSize: "0.72rem", color: "#10b981", fontFamily: "monospace" }}>IMPLICIT EULER SOLVER</span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {/* Node 1: Core */}
                  <div style={{
                    padding: "0.85rem 1.15rem", borderRadius: 8,
                    background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.3)",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                  }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <Flame size={15} color="var(--danger)" />
                        <span style={{ fontWeight: 800, fontSize: "0.88rem", color: "#f8fafc" }}>Node 1: Cell Jelly-Roll Core</span>
                      </div>
                      <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>
                        Thermal mass: 70% · Internal conduction resistance R_cs = 1.8 K/W
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "1.3rem", fontWeight: 900, fontFamily: "monospace", color: "var(--danger)" }}>
                        {thermalSim.coreTempC.toFixed(1)} °C
                      </div>
                      <div style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>CORE TEMP</div>
                    </div>
                  </div>

                  {/* Heat Flux Arrow */}
                  <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.4rem", color: "var(--text-muted)", fontSize: "0.68rem", fontFamily: "monospace" }}>
                    <span>↓ Core-to-surface heat conduction flux</span>
                  </div>

                  {/* Node 2: Surface */}
                  <div style={{
                    padding: "0.85rem 1.15rem", borderRadius: 8,
                    background: "rgba(245, 158, 11, 0.08)", border: "1px solid rgba(245, 158, 11, 0.3)",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                  }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <Thermometer size={15} color="var(--warning)" />
                        <span style={{ fontWeight: 800, fontSize: "0.88rem", color: "#f8fafc" }}>Node 2: Cylindrical Casing Surface</span>
                      </div>
                      <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>
                        Thermal mass: 30% · Interface gap resistance R_sp = 0.5 K/W
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "1.3rem", fontWeight: 900, fontFamily: "monospace", color: "var(--warning)" }}>
                        {thermalSim.surfaceTempC.toFixed(1)} °C
                      </div>
                      <div style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>SURFACE TEMP</div>
                    </div>
                  </div>

                  {/* Heat Flux Arrow */}
                  <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.4rem", color: "var(--text-muted)", fontSize: "0.68rem", fontFamily: "monospace" }}>
                    <span>↓ Surface-to-plate convective heat dissipation</span>
                  </div>

                  {/* Node 3: Cold Plate */}
                  <div style={{
                    padding: "0.85rem 1.15rem", borderRadius: 8,
                    background: "rgba(0, 240, 255, 0.08)", border: "1px solid rgba(0, 240, 255, 0.3)",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                  }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <Wind size={15} color="var(--arc-cyan)" />
                        <span style={{ fontWeight: 800, fontSize: "0.88rem", color: "#f8fafc" }}>Node 3: Bottom Cooling Cold Plate</span>
                      </div>
                      <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "2px" }}>
                        Thermal mass: 15% · Liquid coolant flow convection hA = 22 W/K
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "1.3rem", fontWeight: 900, fontFamily: "monospace", color: "var(--arc-cyan)" }}>
                        {thermalSim.plateTempC.toFixed(1)} °C
                      </div>
                      <div style={{ fontSize: "0.62rem", color: "var(--text-muted)" }}>PLATE TEMP</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Electrochemical Chemistry Matrix Section ── */}
      <section id="chemistry" style={{
        padding: "4.5rem clamp(1rem, 3vw, 2.5rem)",
        background: "rgba(5, 11, 24, 0.95)",
        borderTop: "1px solid rgba(0, 240, 255, 0.15)",
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: "2.75rem" }}>
            <p className="section-title">ELECTROCHEMICAL COMPARISON</p>
            <h2 style={{ fontSize: "clamp(1.75rem, 2.8vw, 2.4rem)", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em" }}>
              Commercial Chemistry Trade-Off Matrix
            </h2>
            <p style={{ color: "var(--text-secondary)", maxWidth: 640, margin: "0.5rem auto 0", fontSize: "0.92rem" }}>
              Compare energy density, cycle life, thermal runaway thresholds, and fast-charging capabilities across major battery chemistries.
            </p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1.25rem" }}>
            {Object.entries(CHEM_PRESETS).map(([key, c]) => (
              <div
                key={key}
                className="card hud-bracket"
                style={{
                  padding: "1.5rem",
                  background: chemKey === key ? "rgba(0, 240, 255, 0.08)" : "rgba(6, 13, 26, 0.8)",
                  border: `1px solid ${chemKey === key ? "var(--arc-cyan)" : "rgba(0, 240, 255, 0.18)"}`,
                  boxShadow: chemKey === key ? "0 0 24px rgba(0, 240, 255, 0.2)" : "none",
                  cursor: "pointer",
                  transition: "all 0.25s ease",
                }}
                onClick={() => setChemKey(key as "NMC" | "LFP" | "NCA" | "LTO")}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.75rem" }}>
                  <div>
                    <span style={{
                      fontSize: "0.68rem", fontWeight: 700, fontFamily: "monospace",
                      padding: "0.2rem 0.5rem", borderRadius: 4,
                      background: "rgba(0, 240, 255, 0.1)", color: c.color,
                      border: `1px solid ${c.color}`,
                    }}>
                      {key}
                    </span>
                    <h3 style={{ fontSize: "1.05rem", fontWeight: 800, color: "#f8fafc", marginTop: "0.5rem", marginBottom: "2px" }}>
                      {c.name}
                    </h3>
                  </div>
                  {chemKey === key && (
                    <span style={{ fontSize: "0.65rem", color: "var(--arc-cyan)", fontFamily: "monospace", border: "1px solid var(--arc-cyan)", padding: "1px 6px", borderRadius: 3 }}>
                      ACTIVE
                    </span>
                  )}
                </div>

                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "1rem", lineHeight: 1.4 }}>
                  {c.fullName}
                </p>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", fontSize: "0.72rem", fontFamily: "monospace", marginBottom: "1rem" }}>
                  <div style={{ background: "rgba(0,0,0,0.3)", padding: "0.4rem", borderRadius: 4 }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.6rem" }}>NOMINAL VOLT</div>
                    <div style={{ fontWeight: 800, color: "#f8fafc" }}>{c.vNom} V</div>
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.3)", padding: "0.4rem", borderRadius: 4 }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.6rem" }}>ENERGY DENSITY</div>
                    <div style={{ fontWeight: 800, color: "var(--arc-cyan)" }}>{c.energyDensityWhKg} Wh/kg</div>
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.3)", padding: "0.4rem", borderRadius: 4 }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.6rem" }}>CYCLE LIFE</div>
                    <div style={{ fontWeight: 800, color: "#10b981" }}>{c.cycleLife.toLocaleString()} cycles</div>
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.3)", padding: "0.4rem", borderRadius: 4 }}>
                    <div style={{ color: "var(--text-muted)", fontSize: "0.6rem" }}>RUNAWAY ONSET</div>
                    <div style={{ fontWeight: 800, color: "var(--danger)" }}>{c.runawayTempC} °C</div>
                  </div>
                </div>

                <p style={{ fontSize: "0.76rem", color: "var(--text-secondary)", lineHeight: 1.5, borderTop: "1px solid rgba(0, 240, 255, 0.08)", paddingTop: "0.75rem" }}>
                  {c.advantage}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Engineering Safety Protocol & Constraint Screening Section ── */}
      <section id="safety" style={{
        padding: "4.5rem clamp(1rem, 3vw, 2.5rem)",
        backgroundColor: "rgba(3, 7, 18, 0.98)",
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: "2.75rem" }}>
            <p className="section-title">VERIFICATION &amp; SAFETY INTEGRITY</p>
            <h2 style={{ fontSize: "clamp(1.75rem, 2.8vw, 2.4rem)", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em" }}>
              Automated Multi-Constraint Safety Screening
            </h2>
            <p style={{ color: "var(--text-secondary)", maxWidth: 640, margin: "0.5rem auto 0", fontSize: "0.92rem" }}>
              BattLab screens packs against stringent multi-domain constraints with complete scientific transparency.
            </p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.25rem" }}>
            {[
              {
                id: "VOLT_NOMINAL",
                name: "Nominal Pack Voltage",
                desc: "Evaluates Ns * V_nom against the target powertrain bus voltage.",
                honesty: "Verified from series cell count and chemistry OCV.",
              },
              {
                id: "CURR_CONTINUOUS",
                name: "Continuous Discharge Current",
                desc: "Verifies whether per-cell continuous current (I_pack / Np) exceeds manufacturer limits.",
                honesty: "Marked UNVERIFIED if target continuous current is omitted in requirements.",
              },
              {
                id: "TEMP_CELL_MAX",
                name: "Peak Transient Temperature",
                desc: "Screens simulated peak core and surface temperatures against maximum allowable threshold (typically 60°C).",
                honesty: "Calculated via coupled electro-thermal multi-node ODE solver.",
              },
              {
                id: "SOC_FLOOR",
                name: "State of Charge Floor",
                desc: "Ensures the pack does not exceed deep discharge limits to protect against copper dissolution.",
                honesty: "Tracked at 100 Hz simulation time-step resolution.",
              },
              {
                id: "MASS_LIMIT",
                name: "Total System Mass",
                desc: "Aggregates total cell mass plus structural and thermal management allowances.",
                honesty: "Calculated with configurable pack packaging efficiency factors.",
              },
              {
                id: "COST_BOM",
                name: "Cell BOM Budget Ceiling",
                desc: "Calculates total cell bill-of-materials cost against target budget limit.",
                honesty: "Marked UNVERIFIED if cost ceiling or cell unit price is omitted.",
              },
            ].map((rule) => (
              <div key={rule.id} className="card hud-bracket" style={{ padding: "1.5rem", background: "rgba(6, 13, 26, 0.85)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                  <span style={{ fontSize: "0.72rem", fontFamily: "monospace", color: "var(--arc-cyan)", fontWeight: 700 }}>
                    {rule.id}
                  </span>
                  <ShieldCheck size={16} color="var(--arc-cyan)" />
                </div>
                <h3 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#f8fafc", marginBottom: "0.5rem" }}>
                  {rule.name}
                </h3>
                <p style={{ fontSize: "0.825rem", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "0.75rem" }}>
                  {rule.desc}
                </p>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontStyle: "italic", borderTop: "1px solid rgba(0, 240, 255, 0.08)", paddingTop: "0.5rem" }}>
                  💡 {rule.honesty}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Call to Action Section ── */}
      <section style={{ padding: "5rem clamp(1rem, 3vw, 2.5rem)", maxWidth: 1000, margin: "0 auto", textAlign: "center" }}>
        <div style={{
          backgroundColor: "rgba(6, 13, 26, 0.9)",
          border: "1px solid rgba(0, 240, 255, 0.3)",
          borderRadius: 16, padding: "3.5rem 2rem",
          boxShadow: "0 16px 64px rgba(0, 0, 0, 0.8), 0 0 32px rgba(0, 240, 255, 0.08)",
        }}>
          <h2 style={{ fontSize: "clamp(1.75rem, 2.8vw, 2.3rem)", fontWeight: 800, color: "#ffffff", marginBottom: "0.85rem" }}>
            Ready to Engineer Your Virtual Battery System?
          </h2>
          <p style={{ color: "var(--text-secondary)", maxWidth: 540, margin: "0 auto 1.75rem", fontSize: "0.92rem" }}>
            Explore verified cell chemistries, configure module topologies, and simulate coupled electro-thermal transients in minutes.
          </p>
          <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/projects/new" style={{ textDecoration: "none" }}>
              <button className="btn-primary" style={{ padding: "0.8rem 1.85rem", fontSize: "0.92rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                + START NEW BATTERY PROJECT <ArrowUpRight size={15} />
              </button>
            </Link>
            <Link href="/dashboard" style={{ textDecoration: "none" }}>
              <button className="btn-secondary" style={{ padding: "0.8rem 1.75rem", fontSize: "0.92rem" }}>
                VIEW ACTIVE DESIGNS
              </button>
            </Link>
          </div>
        </div>
      </section>

      {/* ── High-Tech Footer ── */}
      <footer style={{
        borderTop: "1px solid rgba(0, 240, 255, 0.12)",
        backgroundColor: "#02050c",
        padding: "2.25rem 1.5rem", textAlign: "center",
        fontSize: "0.76rem", color: "var(--text-muted)",
      }}>
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.6rem", marginBottom: "0.4rem" }}>
          <Image src="/logo-mark.png" alt="BattLab" width={22} height={22} style={{ objectFit: "contain" }} />
          <span style={{ fontWeight: 800, color: "#f8fafc", letterSpacing: "0.04em" }}><span style={{ color: "var(--arc-cyan)" }}>BATT</span>LAB</span>
          <span>·</span>
          <span>Battery Design Software &amp; Multi-Physics Platform</span>
        </div>
        <div style={{ maxWidth: 640, margin: "0 auto", lineHeight: 1.5 }}>
          First-principles numerical simulation software. Model predictions are engineering estimates subject to experimental cycler validation.
        </div>
      </footer>
    </div>
  );
}
