"use client";
import React from "react";
import { BatteryCharging, Trash2 } from "lucide-react";

interface EnergyMeterProps {
  socPercent: number; // 0 to 100
  voltageV: number;
  currentA?: number;
  tempC?: number;
  nominalEnergyWh?: number;
  statusLabel?: string;
  isCharging?: boolean;
}

export function BatteryEnergyMeter({
  socPercent,
  voltageV,
  currentA = 0,
  tempC = 25,
  nominalEnergyWh,
  statusLabel = "ACTIVE PACK",
  isCharging = false,
}: EnergyMeterProps) {
  const clampedSoc = Math.max(0, Math.min(100, socPercent));
  const segments = 24;
  const activeSegments = Math.round((clampedSoc / 100) * segments);

  const getSegmentColor = (index: number) => {
    if (index >= activeSegments) return "rgba(0, 240, 255, 0.08)";
    const ratio = index / segments;
    if (ratio < 0.2) return "#ef4444"; // Low red
    if (ratio < 0.4) return "#f59e0b"; // Warning amber
    return "#00f0ff"; // Arc cyan
  };

  return (
    <div
      className="card hud-bracket"
      style={{
        background: "rgba(6, 13, 26, 0.9)",
        border: "1px solid rgba(0, 240, 255, 0.28)",
        borderRadius: 10,
        padding: "1.25rem",
        boxShadow: "0 8px 32px rgba(0,0,0,0.7), inset 0 0 20px rgba(0, 240, 255, 0.04)",
      }}
    >
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.85rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div
            style={{
              width: 24,
              height: 24,
              borderRadius: 6,
              background: "rgba(0, 240, 255, 0.12)",
              border: "1px solid rgba(0, 240, 255, 0.4)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <BatteryCharging size={14} color="var(--arc-cyan)" />
          </div>
          <span style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "var(--arc-cyan)", letterSpacing: "0.08em", fontWeight: 700 }}>
            {statusLabel}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: isCharging ? "#10b981" : "#00f0ff",
              boxShadow: `0 0 10px ${isCharging ? "#10b981" : "#00f0ff"}`,
            }}
          />
          <span style={{ fontSize: "0.7rem", fontFamily: "monospace", color: isCharging ? "#10b981" : "var(--text-secondary)" }}>
            {isCharging ? "REGENERATING" : "DISCHARGING"}
          </span>
        </div>
      </div>

      {/* Main Large SOC & Voltage Display */}
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: "1rem" }}>
        <div>
          <span style={{ fontSize: "2.4rem", fontWeight: 900, fontFamily: "monospace", letterSpacing: "-0.03em", color: "#f8fafc" }}>
            {clampedSoc.toFixed(1)}
          </span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--arc-cyan)", marginLeft: "0.2rem" }}>%</span>
          <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            State of Charge (SOC)
          </div>
        </div>

        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "1.35rem", fontWeight: 800, fontFamily: "monospace", color: "#38bdf8" }}>
            {voltageV.toFixed(2)} <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>V</span>
          </div>
          <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Terminal Voltage
          </div>
        </div>
      </div>

      {/* 24-Segment LED Battery Gauge */}
      <div style={{ display: "flex", gap: "3px", height: "18px", marginBottom: "1rem", padding: "2px", background: "rgba(0,0,0,0.5)", borderRadius: 4, border: "1px solid rgba(0, 240, 255, 0.15)" }}>
        {Array.from({ length: segments }).map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              background: getSegmentColor(i),
              borderRadius: 2,
              transition: "all 0.25s ease",
              boxShadow: i < activeSegments ? `0 0 6px ${getSegmentColor(i)}` : "none",
            }}
          />
        ))}
      </div>

      {/* Engineering Telemetry Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem" }}>
        <div style={{ background: "rgba(0, 240, 255, 0.04)", borderRadius: 6, padding: "0.45rem 0.6rem", border: "1px solid rgba(0, 240, 255, 0.12)" }}>
          <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>CURRENT</div>
          <div style={{ fontSize: "0.88rem", fontWeight: 700, fontFamily: "monospace", color: Math.abs(currentA) > 0 ? "var(--arc-cyan)" : "var(--text-secondary)" }}>
            {currentA.toFixed(1)} A
          </div>
        </div>

        <div style={{ background: "rgba(0, 240, 255, 0.04)", borderRadius: 6, padding: "0.45rem 0.6rem", border: "1px solid rgba(0, 240, 255, 0.12)" }}>
          <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>CORE TEMP</div>
          <div style={{ fontSize: "0.88rem", fontWeight: 700, fontFamily: "monospace", color: tempC > 45 ? "var(--warning)" : "var(--success)" }}>
            {tempC.toFixed(1)} °C
          </div>
        </div>

        <div style={{ background: "rgba(0, 240, 255, 0.04)", borderRadius: 6, padding: "0.45rem 0.6rem", border: "1px solid rgba(0, 240, 255, 0.12)" }}>
          <div style={{ fontSize: "0.62rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>PACK ENERGY</div>
          <div style={{ fontSize: "0.88rem", fontWeight: 700, fontFamily: "monospace", color: "#f8fafc" }}>
            {nominalEnergyWh ? `${(nominalEnergyWh / 1000).toFixed(2)} kWh` : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

interface CellCardProps {
  manufacturer: string;
  model: string;
  chemistry: string;
  formFactor: string;
  nominalVoltageV: number;
  capacityAh: number;
  internalResistanceOhm?: number;
  maxContinuousA?: number;
  massKg?: number;
  onClick?: () => void;
  selected?: boolean;
  isSeed?: boolean;
  onDelete?: () => void;
}

export function BatteryCellCard({
  manufacturer,
  model,
  chemistry,
  formFactor,
  nominalVoltageV,
  capacityAh,
  internalResistanceOhm,
  maxContinuousA,
  massKg,
  onClick,
  selected = false,
  isSeed = true,
  onDelete,
}: CellCardProps) {
  const energyWh = nominalVoltageV * capacityAh;
  const specificEnergyWhKg = massKg && massKg > 0 ? energyWh / massKg : null;

  return (
    <div
      onClick={onClick}
      className="card"
      style={{
        cursor: onClick ? "pointer" : "default",
        background: selected ? "rgba(0, 240, 255, 0.09)" : "rgba(6, 13, 26, 0.8)",
        border: `1px solid ${selected ? "var(--arc-cyan)" : "rgba(0, 240, 255, 0.2)"}`,
        boxShadow: selected ? "0 0 24px rgba(0, 240, 255, 0.35), inset 0 0 16px rgba(0, 240, 255, 0.08)" : "none",
        transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.6rem" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.2rem" }}>
            <span
              style={{
                fontSize: "0.65rem",
                fontFamily: "monospace",
                fontWeight: 700,
                padding: "0.15rem 0.45rem",
                borderRadius: 4,
                background: chemistry === "LFP" ? "rgba(16, 185, 129, 0.15)" : "rgba(0, 240, 255, 0.15)",
                color: chemistry === "LFP" ? "#34d399" : "var(--arc-cyan)",
                border: `1px solid ${chemistry === "LFP" ? "rgba(16, 185, 129, 0.35)" : "rgba(0, 240, 255, 0.35)"}`,
              }}
            >
              {chemistry}
            </span>
            <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontFamily: "monospace" }}>
              {formFactor}
            </span>
            {!isSeed && (
              <span
                style={{
                  fontSize: "0.62rem",
                  fontFamily: "monospace",
                  padding: "0.1rem 0.35rem",
                  borderRadius: 3,
                  background: "rgba(245, 158, 11, 0.12)",
                  color: "#f59e0b",
                  border: "1px solid rgba(245, 158, 11, 0.3)",
                }}
              >
                Custom
              </span>
            )}
          </div>
          <h4 style={{ fontWeight: 800, fontSize: "0.95rem", color: "#f8fafc", margin: 0 }}>
            {manufacturer} {model}
          </h4>
        </div>

        <div style={{ display: "flex", alignItems: "flex-start", gap: "0.6rem" }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "1.05rem", fontWeight: 800, fontFamily: "monospace", color: "var(--arc-cyan)" }}>
              {capacityAh.toFixed(1)} <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Ah</span>
            </div>
            <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontFamily: "monospace" }}>
              {nominalVoltageV.toFixed(2)} V Nom
            </div>
          </div>

          {onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="btn-danger"
              style={{
                padding: "0.3rem 0.5rem", borderRadius: 6, cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.15s ease",
              }}
              title="Delete cell specification"
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Key Specs Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.4rem", marginTop: "0.75rem", fontSize: "0.72rem", fontFamily: "monospace" }}>
        <div style={{ background: "rgba(0,0,0,0.3)", padding: "0.3rem 0.45rem", borderRadius: 4 }}>
          <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.6rem" }}>ENERGY</span>
          <span style={{ fontWeight: 700, color: "#f8fafc" }}>{energyWh.toFixed(1)} Wh</span>
        </div>
        <div style={{ background: "rgba(0,0,0,0.3)", padding: "0.3rem 0.45rem", borderRadius: 4 }}>
          <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.6rem" }}>R_INT</span>
          <span style={{ fontWeight: 700, color: "#38bdf8" }}>
            {internalResistanceOhm ? `${(internalResistanceOhm * 1000).toFixed(1)} mΩ` : "—"}
          </span>
        </div>
        <div style={{ background: "rgba(0,0,0,0.3)", padding: "0.3rem 0.45rem", borderRadius: 4 }}>
          <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.6rem" }}>MAX CONT</span>
          <span style={{ fontWeight: 700, color: maxContinuousA ? "#10b981" : "var(--text-muted)" }}>
            {maxContinuousA ? `${maxContinuousA.toFixed(0)} A` : "—"}
          </span>
        </div>
      </div>

      {specificEnergyWhKg && (
        <div style={{ marginTop: "0.6rem", fontSize: "0.68rem", color: "var(--text-secondary)", display: "flex", justifyContent: "space-between", borderTop: "1px solid rgba(0, 240, 255, 0.08)", paddingTop: "0.4rem" }}>
          <span>Specific Energy Density:</span>
          <span style={{ fontWeight: 700, color: "var(--arc-cyan)", fontFamily: "monospace" }}>
            {specificEnergyWhKg.toFixed(1)} Wh/kg
          </span>
        </div>
      )}
    </div>
  );
}
