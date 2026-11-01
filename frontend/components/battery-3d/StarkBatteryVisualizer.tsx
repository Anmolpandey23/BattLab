"use client";
import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";

// Targeted suppression of Three.js r187+ Clock and PCFSoftShadowMap deprecation emitted inside third-party @react-three/fiber v9.8.2
// Uses Three.js official setConsoleFunction API without modifying window.console.warn or hiding application warnings.
if (typeof (THREE as unknown as { setConsoleFunction?: unknown }).setConsoleFunction === "function") {
  (THREE as unknown as { setConsoleFunction: (fn: (type: string, message: string, ...params: unknown[]) => void) => void }).setConsoleFunction(
    (type: string, message: string, ...params: unknown[]) => {
      if (
        typeof message === "string" &&
        (message.includes("Clock: This module has been deprecated") ||
         message.includes("PCFSoftShadowMap has been removed"))
      ) {
        return;
      }
      const target = (console as unknown as Record<string, (...args: unknown[]) => void>)[type] || console.warn;
      target(message, ...params);
    }
  );
}

export interface StarkBatteryVisualizerProps {
  ns?: number;
  np?: number;
  cellFormFactor?: string; // "21700" | "18650" | "prismatic"
  cellDiameterMm?: number;
  cellHeightMm?: number;
  coolingType?: string; // "passive" | "fan" | "liquid" | "phase_change"
  showEnclosure?: boolean;
  colorMode?: "default" | "thermal" | "simulation";
  thermalData?: number[];
  exploded?: boolean;
  explodeAmount?: number; // 0 to 1
  isSimulating?: boolean;
  simTimeS?: number;
  simCurrentA?: number;
  simSoc?: number;
  simTempC?: number;
  onCellSelect?: (cellInfo: { s: number; p: number; id: number; temp: number; v: number }) => void;
  showDimensions?: boolean;
  packLengthMm?: number;
  packWidthMm?: number;
  packHeightMm?: number;
}

// ── Thermodynamic False-Color Spectrum ───────────────────────────────────────
function getThermalColor(tempC: number): THREE.Color {
  const t = Math.max(20, Math.min(70, tempC));
  if (t <= 30) {
    const f = (t - 20) / 10;
    return new THREE.Color().setRGB(0, f * 0.94, 1);
  } else if (t <= 40) {
    const f = (t - 30) / 10;
    return new THREE.Color().setRGB(0, 0.94 + f * 0.06, 1 - f * 0.47);
  } else if (t <= 50) {
    const f = (t - 40) / 10;
    return new THREE.Color().setRGB(f, 1 - f * 0.27, 0.53 - f * 0.53);
  } else {
    const f = (t - 50) / 15;
    return new THREE.Color().setRGB(1, Math.max(0, 0.73 - f * 0.73), f * 0.27);
  }
}

// ── Realistic Cylindrical Cell with Cutaway Jelly-Roll Option ─────────────────
function RealisticCell({
  basePos,
  targetPos,
  cellId,
  tempC,
  colorMode,
  isSimulating,
  simPulse,
  selected,
  isCutaway = false,
  onSelect,
}: {
  basePos: [number, number, number];
  targetPos: [number, number, number];
  sIndex: number;
  pIndex: number;
  cellId: number;
  tempC: number;
  colorMode: "default" | "thermal" | "simulation";
  isSimulating?: boolean;
  simPulse?: number;
  selected?: boolean;
  isCutaway?: boolean;
  onSelect?: () => void;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const bodyMatRef = useRef<THREE.MeshStandardMaterial>(null);

  useFrame(() => {
    if (groupRef.current) {
      groupRef.current.position.x = THREE.MathUtils.lerp(groupRef.current.position.x, targetPos[0], 0.12);
      groupRef.current.position.y = THREE.MathUtils.lerp(groupRef.current.position.y, targetPos[1], 0.12);
      groupRef.current.position.z = THREE.MathUtils.lerp(groupRef.current.position.z, targetPos[2], 0.12);
    }
    if (bodyMatRef.current && isSimulating && simPulse !== undefined) {
      const pulseEmissive = Math.sin(simPulse * 8 + cellId * 0.25) * 0.25 + 0.25;
      bodyMatRef.current.emissiveIntensity = selected ? 0.8 : pulseEmissive;
    }
  });

  const cellColor = useMemo(() => {
    if (colorMode === "thermal" || colorMode === "simulation") {
      return getThermalColor(tempC);
    }
    return new THREE.Color("#0ea5e9");
  }, [colorMode, tempC]);

  return (
    <group
      ref={groupRef}
      position={basePos}
      onClick={(e) => {
        e.stopPropagation();
        onSelect?.();
      }}
    >
      {/* Selection Hologram Reticle */}
      {selected && (
        <lineSegments position={[0, 0, 0]}>
          <edgesGeometry args={[new THREE.BoxGeometry(0.24, 0.85, 0.24)]} />
          <lineBasicMaterial color="#00f0ff" linewidth={2} />
        </lineSegments>
      )}

      {/* Main Steel Casing & Dielectric Heat-Shrink Wrap */}
      {!isCutaway ? (
        <mesh castShadow receiveShadow>
          <cylinderGeometry args={[0.098, 0.098, 0.65, 24]} />
          <meshStandardMaterial
            ref={bodyMatRef}
            color={cellColor}
            metalness={0.7}
            roughness={0.25}
            emissive={selected ? new THREE.Color("#00f0ff") : cellColor}
            emissiveIntensity={selected ? 0.6 : colorMode === "thermal" ? 0.35 : 0.08}
          />
        </mesh>
      ) : (
        /* 90° Cutaway revealing the internal Swiss Jelly-Roll */
        <group>
          {/* 270° Outer Shell */}
          <mesh castShadow receiveShadow>
            <cylinderGeometry args={[0.098, 0.098, 0.65, 24, 1, false, 0, Math.PI * 1.5]} />
            <meshStandardMaterial ref={bodyMatRef} color={cellColor} metalness={0.7} roughness={0.25} />
          </mesh>

          {/* Internal Spiral Jelly Roll Core (Anode, Separator, Cathode) */}
          <mesh position={[0, 0, 0]}>
            <cylinderGeometry args={[0.088, 0.088, 0.62, 20]} />
            <meshStandardMaterial color="#b45309" metalness={0.8} roughness={0.3} />
          </mesh>
          <mesh position={[0, 0, 0]}>
            <cylinderGeometry args={[0.065, 0.065, 0.625, 18]} />
            <meshStandardMaterial color="#f1f5f9" metalness={0.2} roughness={0.6} />
          </mesh>
          <mesh position={[0, 0, 0]}>
            <cylinderGeometry args={[0.045, 0.045, 0.628, 16]} />
            <meshStandardMaterial color="#334155" metalness={0.9} roughness={0.2} />
          </mesh>

          {/* Central Steel Mandrel Pin Core */}
          <mesh position={[0, 0, 0]}>
            <cylinderGeometry args={[0.015, 0.015, 0.64, 12]} />
            <meshStandardMaterial color="#94a3b8" metalness={0.95} roughness={0.1} />
          </mesh>
        </group>
      )}

      {/* Top Crimp Shoulder Ring */}
      <mesh position={[0, 0.33, 0]}>
        <cylinderGeometry args={[0.099, 0.099, 0.02, 24]} />
        <meshStandardMaterial color="#94a3b8" metalness={0.9} roughness={0.15} />
      </mesh>

      {/* Positive Terminal Anode Button (+ Cap with Vents) */}
      <mesh position={[0, 0.355, 0]} castShadow>
        <cylinderGeometry args={[0.048, 0.048, 0.035, 16]} />
        <meshStandardMaterial color="#e2e8f0" metalness={0.95} roughness={0.1} />
      </mesh>

      {/* Negative Terminal Cathode Base (- Flat Disc) */}
      <mesh position={[0, -0.335, 0]}>
        <cylinderGeometry args={[0.095, 0.095, 0.02, 24]} />
        <meshStandardMaterial color="#64748b" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Laser Etched Polarity Indicator (+) */}
      <mesh position={[0, 0.22, 0.1]}>
        <boxGeometry args={[0.03, 0.01, 0.002]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.6} />
      </mesh>
      <mesh position={[0, 0.22, 0.1]}>
        <boxGeometry args={[0.01, 0.03, 0.002]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.6} />
      </mesh>
    </group>
  );
}

// ── Laser-Welded Busbars & High-Current Main Terminals ─────────────────────────
function Busbars({
  ns,
  np,
  spacingX,
  spacingZ,
  explodeAmount,
  isSimulating,
}: {
  ns: number;
  np: number;
  spacingX: number;
  spacingZ: number;
  explodeAmount: number;
  isSimulating?: boolean;
}) {
  const topBusbarRef = useRef<THREE.Group>(null);
  const botBusbarRef = useRef<THREE.Group>(null);

  useFrame(() => {
    if (topBusbarRef.current) {
      const targetY = 0.38 + explodeAmount * 0.95;
      topBusbarRef.current.position.y = THREE.MathUtils.lerp(topBusbarRef.current.position.y, targetY, 0.12);
    }
    if (botBusbarRef.current) {
      const targetY = -0.38 - explodeAmount * 0.95;
      botBusbarRef.current.position.y = THREE.MathUtils.lerp(botBusbarRef.current.position.y, targetY, 0.12);
    }
  });

  const totalWidth = np * spacingX;

  const busbarElements = useMemo(() => {
    const totalWidth = np * spacingX;
    const topStrips: { x: number; z: number; width: number; depth: number }[] = [];
    const botStrips: { x: number; z: number; width: number; depth: number }[] = [];

    for (let s = 0; s < ns; s++) {
      const z = (s - (ns - 1) / 2) * spacingZ;
      if (s % 2 === 0) {
        topStrips.push({ x: 0, z, width: totalWidth, depth: spacingZ * 0.65 });
      } else {
        botStrips.push({ x: 0, z, width: totalWidth, depth: spacingZ * 0.65 });
      }
    }

    return { topStrips, botStrips };
  }, [ns, np, spacingX, spacingZ]);

  return (
    <>
      {/* Top Busbars (Nickel-Plated Copper) */}
      <group ref={topBusbarRef} position={[0, 0.38, 0]}>
        {busbarElements.topStrips.map((strip, i) => (
          <group key={i} position={[strip.x, 0, strip.z]}>
            <mesh castShadow>
              <boxGeometry args={[strip.width, 0.015, strip.depth]} />
              <meshStandardMaterial
                color="#f59e0b"
                metalness={0.9}
                roughness={0.2}
                emissive={isSimulating ? new THREE.Color("#00f0ff") : new THREE.Color("#d97706")}
                emissiveIntensity={isSimulating ? 0.4 : 0.05}
              />
            </mesh>
            {/* Spot Weld Points for each parallel cell in the row */}
            {Array.from({ length: np }).map((_, p) => {
              const wx = (p - (np - 1) / 2) * spacingX;
              return (
                <mesh key={p} position={[wx, 0.01, 0]}>
                  <cylinderGeometry args={[0.035, 0.035, 0.005, 12]} />
                  <meshStandardMaterial color="#e2e8f0" metalness={0.95} roughness={0.1} />
                </mesh>
              );
            })}
          </group>
        ))}

        {/* High Current Main Positive (+) Red Terminal Post */}
        <group position={[totalWidth / 2 + 0.06, 0.04, -((ns - 1) / 2) * spacingZ]}>
          <mesh castShadow>
            <cylinderGeometry args={[0.04, 0.04, 0.08, 16]} />
            <meshStandardMaterial color="#ef4444" metalness={0.7} roughness={0.3} />
          </mesh>
          <mesh position={[0, 0.045, 0]}>
            <cylinderGeometry args={[0.02, 0.02, 0.03, 16]} />
            <meshStandardMaterial color="#e2e8f0" metalness={0.95} roughness={0.1} />
          </mesh>
        </group>
      </group>

      {/* Bottom Busbars (Solid Ground Interconnects) */}
      <group ref={botBusbarRef} position={[0, -0.38, 0]}>
        {busbarElements.botStrips.map((strip, i) => (
          <group key={i} position={[strip.x, 0, strip.z]}>
            <mesh castShadow>
              <boxGeometry args={[strip.width, 0.015, strip.depth]} />
              <meshStandardMaterial color="#d97706" metalness={0.85} roughness={0.25} />
            </mesh>
            {Array.from({ length: np }).map((_, p) => {
              const wx = (p - (np - 1) / 2) * spacingX;
              return (
                <mesh key={p} position={[wx, -0.01, 0]}>
                  <cylinderGeometry args={[0.035, 0.035, 0.005, 12]} />
                  <meshStandardMaterial color="#94a3b8" metalness={0.9} roughness={0.2} />
                </mesh>
              );
            })}
          </group>
        ))}

        {/* High Current Main Negative (-) Black Terminal Post */}
        <group position={[-totalWidth / 2 - 0.06, -0.04, ((ns - 1) / 2) * spacingZ]}>
          <mesh castShadow>
            <cylinderGeometry args={[0.04, 0.04, 0.08, 16]} />
            <meshStandardMaterial color="#0f172a" metalness={0.8} roughness={0.2} />
          </mesh>
          <mesh position={[0, -0.045, 0]}>
            <cylinderGeometry args={[0.02, 0.02, 0.03, 16]} />
            <meshStandardMaterial color="#e2e8f0" metalness={0.95} roughness={0.1} />
          </mesh>
        </group>
      </group>
    </>
  );
}

// ── Honeycomb Cell Spacer Holders ─────────────────────────────────────────────
function CellHolders({
  width,
  depth,
  ns,
  np,
  spacingX,
  spacingZ,
  explodeAmount,
}: {
  width: number;
  depth: number;
  ns: number;
  np: number;
  spacingX: number;
  spacingZ: number;
  explodeAmount: number;
}) {
  const topHolderRef = useRef<THREE.Group>(null);
  const botHolderRef = useRef<THREE.Group>(null);

  useFrame(() => {
    if (topHolderRef.current) {
      topHolderRef.current.position.y = THREE.MathUtils.lerp(topHolderRef.current.position.y, 0.28 + explodeAmount * 0.45, 0.12);
    }
    if (botHolderRef.current) {
      botHolderRef.current.position.y = THREE.MathUtils.lerp(botHolderRef.current.position.y, -0.28 - explodeAmount * 0.45, 0.12);
    }
  });

  return (
    <>
      {/* Upper Matrix Plate with Cell Sockets */}
      <group ref={topHolderRef} position={[0, 0.28, 0]}>
        <mesh receiveShadow>
          <boxGeometry args={[width + 0.1, 0.03, depth + 0.1]} />
          <meshStandardMaterial color="#0f172a" metalness={0.4} roughness={0.6} transparent opacity={0.88} />
        </mesh>
        <lineSegments>
          <edgesGeometry args={[new THREE.BoxGeometry(width + 0.1, 0.03, depth + 0.1)]} />
          <lineBasicMaterial color="#00f0ff" transparent opacity={0.4} />
        </lineSegments>

        {/* Circular Cell Socket Collars */}
        {Array.from({ length: Math.min(ns, 16) }).map((_, s) => {
          const z = (s - (Math.min(ns, 16) - 1) / 2) * spacingZ;
          return Array.from({ length: Math.min(np, 18) }).map((__, p) => {
            const x = (p - (Math.min(np, 18) - 1) / 2) * spacingX;
            return (
              <mesh key={`${s}-${p}`} position={[x, 0.016, z]}>
                <ringGeometry args={[0.096, 0.108, 16]} />
                <meshBasicMaterial color="#00f0ff" transparent opacity={0.35} side={THREE.DoubleSide} />
              </mesh>
            );
          });
        })}
      </group>

      {/* Lower Matrix Plate */}
      <group ref={botHolderRef} position={[0, -0.28, 0]}>
        <mesh receiveShadow>
          <boxGeometry args={[width + 0.1, 0.03, depth + 0.1]} />
          <meshStandardMaterial color="#0f172a" metalness={0.4} roughness={0.6} transparent opacity={0.88} />
        </mesh>
        <lineSegments>
          <edgesGeometry args={[new THREE.BoxGeometry(width + 0.1, 0.03, depth + 0.1)]} />
          <lineBasicMaterial color="#00f0ff" transparent opacity={0.4} />
        </lineSegments>
      </group>
    </>
  );
}

// ── Multi-Physics Thermal Management System (Liquid / Fan / PCM / Passive) ────
function ThermalManagementSystem({
  width,
  depth,
  ns,
  np,
  spacingX,
  spacingZ,
  explodeAmount,
  coolingType,
  isSimulating,
}: {
  width: number;
  depth: number;
  ns: number;
  np: number;
  spacingX: number;
  spacingZ: number;
  explodeAmount: number;
  coolingType: string;
  isSimulating?: boolean;
}) {
  const thermalGroupRef = useRef<THREE.Group>(null);
  const fanBlades1Ref = useRef<THREE.Group>(null);
  const fanBlades2Ref = useRef<THREE.Group>(null);
  const fluidPulseRef = useRef<THREE.MeshStandardMaterial>(null);

  useFrame((_, delta) => {
    // Separation interpolation
    if (thermalGroupRef.current) {
      const targetY = -0.46 - explodeAmount * 1.5;
      thermalGroupRef.current.position.y = THREE.MathUtils.lerp(thermalGroupRef.current.position.y, targetY, 0.12);
    }

    // Active cooling fan rotation animation
    if (coolingType === "fan") {
      const speed = isSimulating ? 18 : 6;
      if (fanBlades1Ref.current) fanBlades1Ref.current.rotation.z += delta * speed;
      if (fanBlades2Ref.current) fanBlades2Ref.current.rotation.z += delta * speed;
    }

    // Coolant fluid pulse animation
    if (coolingType === "liquid" && fluidPulseRef.current && isSimulating) {
      fluidPulseRef.current.emissiveIntensity = 0.4 + Math.sin(Date.now() * 0.006) * 0.3;
    }
  });

  // 1. LIQUID COOLING COLD PLATE WITH INTERNAL CHANNELS
  if (coolingType === "liquid") {
    return (
      <group ref={thermalGroupRef} position={[0, -0.46, 0]}>
        {/* Aluminum Cold Plate Bottom Base */}
        <mesh castShadow receiveShadow>
          <boxGeometry args={[width + 0.14, 0.025, depth + 0.14]} />
          <meshStandardMaterial color="#0284c7" metalness={0.85} roughness={0.2} />
        </mesh>

        {/* Internal Serpentine Fluid Micro-Channels (Visible in Exploded/Inspection View) */}
        <group position={[0, 0.016, 0]}>
          {Array.from({ length: Math.min(ns, 12) }).map((_, i) => {
            const z = (i - (Math.min(ns, 12) - 1) / 2) * spacingZ;
            return (
              <group key={i} position={[0, 0, z]}>
                {/* Milled Channel Groove */}
                <mesh>
                  <boxGeometry args={[width * 0.92, 0.01, 0.035]} />
                  <meshStandardMaterial color="#082f49" metalness={0.9} roughness={0.3} />
                </mesh>
                {/* Flowing Coolant Stream Ribbon */}
                <mesh position={[0, 0.003, 0]}>
                  <boxGeometry args={[width * 0.9, 0.008, 0.024]} />
                  <meshStandardMaterial
                    ref={i === 0 ? fluidPulseRef : undefined}
                    color="#00f0ff"
                    metalness={0.4}
                    roughness={0.1}
                    emissive={new THREE.Color("#00c8ff")}
                    emissiveIntensity={isSimulating ? 0.6 : 0.25}
                    transparent
                    opacity={0.85}
                  />
                </mesh>
              </group>
            );
          })}
        </group>

        {/* Top Channel Cover Plate (Lifts slightly in exploded view so you see INSIDE) */}
        <mesh position={[0, 0.03 + explodeAmount * 0.08, 0]}>
          <boxGeometry args={[width + 0.14, 0.01, depth + 0.14]} />
          <meshStandardMaterial
            color="#38bdf8"
            metalness={0.8}
            roughness={0.2}
            transparent
            opacity={explodeAmount > 0.3 ? 0.4 : 0.9}
          />
        </mesh>

        {/* Dual High-Pressure Anodized Fluid Ports (Blue Cold In, Red Hot Out) */}
        <group position={[width / 2 + 0.12, 0.01, -depth / 4]}>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.025, 0.025, 0.14, 16]} />
            <meshStandardMaterial color="#00e5ff" metalness={0.9} roughness={0.1} />
          </mesh>
          <mesh position={[0.08, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
            <torusGeometry args={[0.028, 0.008, 8, 16]} />
            <meshStandardMaterial color="#1e293b" metalness={0.9} />
          </mesh>
        </group>
        <group position={[width / 2 + 0.12, 0.01, depth / 4]}>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.025, 0.025, 0.14, 16]} />
            <meshStandardMaterial color="#ef4444" metalness={0.9} roughness={0.1} />
          </mesh>
          <mesh position={[0.08, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
            <torusGeometry args={[0.028, 0.008, 8, 16]} />
            <meshStandardMaterial color="#1e293b" metalness={0.9} />
          </mesh>
        </group>
      </group>
    );
  }

  // 2. FORCED AIR / ACTIVE FAN-COOLED SYSTEM (Heatsink Fins + Dual Spinning Fans)
  if (coolingType === "fan") {
    return (
      <group ref={thermalGroupRef} position={[0, -0.46, 0]}>
        {/* Aluminum Heatsink Base Plate */}
        <mesh castShadow receiveShadow>
          <boxGeometry args={[width + 0.12, 0.03, depth + 0.12]} />
          <meshStandardMaterial color="#334155" metalness={0.8} roughness={0.3} />
        </mesh>

        {/* Longitudinal Air Cooling Fins */}
        <group position={[0, -0.04, 0]}>
          {Array.from({ length: 14 }).map((_, f) => {
            const z = (f - 6.5) * (depth / 14);
            return (
              <mesh key={f} position={[0, 0, z]}>
                <boxGeometry args={[width + 0.1, 0.05, 0.008]} />
                <meshStandardMaterial color="#475569" metalness={0.9} roughness={0.2} />
              </mesh>
            );
          })}
        </group>

        {/* Dual High-Flow Brushless Axial Cooling Fans */}
        {[-depth / 3, depth / 3].map((fz, fi) => (
          <group key={fi} position={[width / 2 + 0.14, 0, fz]}>
            {/* Square Fan Shroud Housing */}
            <mesh rotation={[0, 0, Math.PI / 2]}>
              <boxGeometry args={[0.18, 0.04, 0.18]} />
              <meshStandardMaterial color="#0f172a" metalness={0.5} roughness={0.4} />
            </mesh>
            {/* Cylindrical Venturi Bore */}
            <mesh rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.08, 0.08, 0.042, 20]} />
              <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.2} />
            </mesh>

            {/* Spinning Fan Impeller Blades */}
            <group ref={fi === 0 ? fanBlades1Ref : fanBlades2Ref} rotation={[0, 0, Math.PI / 2]}>
              {/* Center Motor Hub */}
              <mesh>
                <cylinderGeometry args={[0.032, 0.032, 0.03, 16]} />
                <meshStandardMaterial color="#00f0ff" metalness={0.9} roughness={0.1} />
              </mesh>
              {/* 7 Curved Aerodynamic Blades */}
              {Array.from({ length: 7 }).map((_, b) => (
                <mesh key={b} rotation={[0, (b * Math.PI * 2) / 7, 0.35]}>
                  <boxGeometry args={[0.075, 0.004, 0.022]} />
                  <meshStandardMaterial color="#0284c7" metalness={0.6} roughness={0.3} />
                </mesh>
              ))}
            </group>

            {/* Protective Wire Finger Guard */}
            <mesh position={[0.025, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
              <ringGeometry args={[0.03, 0.078, 16]} />
              <meshBasicMaterial color="#94a3b8" wireframe />
            </mesh>
          </group>
        ))}
      </group>
    );
  }

  // 3. PHASE CHANGE MATERIAL (PCM) MATRIX SLEEVES
  if (coolingType === "phase_change") {
    return (
      <group ref={thermalGroupRef} position={[0, -0.46, 0]}>
        {/* Composite Graphite-Wax PCM Thermal Block */}
        <mesh castShadow receiveShadow>
          <boxGeometry args={[width + 0.12, 0.06, depth + 0.12]} />
          <meshStandardMaterial
            color="#78350f"
            metalness={0.3}
            roughness={0.7}
            emissive={isSimulating ? new THREE.Color("#d97706") : new THREE.Color("#451a03")}
            emissiveIntensity={isSimulating ? 0.35 : 0.05}
            transparent
            opacity={0.85}
          />
        </mesh>
        <lineSegments>
          <edgesGeometry args={[new THREE.BoxGeometry(width + 0.12, 0.06, depth + 0.12)]} />
          <lineBasicMaterial color="#f59e0b" />
        </lineSegments>

        {/* PCM Hexagonal Cell Pocket Liners */}
        {Array.from({ length: Math.min(ns, 8) }).map((_, s) => {
          const z = (s - (Math.min(ns, 8) - 1) / 2) * spacingZ;
          return Array.from({ length: Math.min(np, 10) }).map((__, p) => {
            const x = (p - (Math.min(np, 10) - 1) / 2) * spacingX;
            return (
              <mesh key={`${s}-${p}`} position={[x, 0.035, z]}>
                <cylinderGeometry args={[0.102, 0.102, 0.08, 16]} />
                <meshStandardMaterial color="#92400e" metalness={0.4} roughness={0.5} wireframe />
              </mesh>
            );
          });
        })}
      </group>
    );
  }

  // 4. PASSIVE CONVECTION (Extruded Finned Tray)
  return (
    <group ref={thermalGroupRef} position={[0, -0.46, 0]}>
      {/* Aluminum Thermal Tray */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width + 0.1, 0.02, depth + 0.1]} />
        <meshStandardMaterial color="#1e293b" metalness={0.8} roughness={0.3} />
      </mesh>
      {/* Convection Heat Dissipation Ribs */}
      {[-depth / 4, 0, depth / 4].map((z, i) => (
        <mesh key={i} position={[0, -0.015, z]}>
          <boxGeometry args={[width + 0.08, 0.015, 0.01]} />
          <meshStandardMaterial color="#334155" metalness={0.9} roughness={0.2} />
        </mesh>
      ))}
    </group>
  );
}

// ── Realistic BMS Board with Multi-Color Balance Wire Harness ─────────────────
function BMSBoard({
  width,
  depth,
  ns,
  spacingZ,
  explodeAmount,
  isSimulating,
}: {
  width: number;
  depth: number;
  ns: number;
  spacingZ: number;
  explodeAmount: number;
  isSimulating?: boolean;
}) {
  const bmsRef = useRef<THREE.Group>(null);
  const [ledBlink, setLedBlink] = useState(false);

  useEffect(() => {
    const iv = setInterval(() => setLedBlink((b) => !b), 350);
    return () => clearInterval(iv);
  }, []);

  useFrame(() => {
    if (bmsRef.current) {
      const targetY = 0.45 + explodeAmount * 1.5;
      const targetRotX = explodeAmount * 0.12;
      bmsRef.current.position.y = THREE.MathUtils.lerp(bmsRef.current.position.y, targetY, 0.12);
      bmsRef.current.rotation.x = THREE.MathUtils.lerp(bmsRef.current.rotation.x, targetRotX, 0.12);
    }
  });

  const bmsW = Math.max(0.7, width * 0.8);
  const bmsD = Math.max(0.45, depth * 0.45);

  const wireColors = ["#ef4444", "#f97316", "#eab308", "#10b981", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899", "#f1f5f9"];

  return (
    <group ref={bmsRef} position={[0, 0.45, 0]}>
      {/* Matte Black High-Density FR4 PCB Substrate */}
      <mesh castShadow>
        <boxGeometry args={[bmsW, 0.016, bmsD]} />
        <meshStandardMaterial color="#091422" metalness={0.4} roughness={0.5} />
      </mesh>
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(bmsW, 0.016, bmsD)]} />
        <lineBasicMaterial color="#00f0ff" transparent opacity={0.6} />
      </lineSegments>

      {/* Main High-Performance Battery Monitor Microcontroller (QFP Package) */}
      <mesh position={[0, 0.014, 0]}>
        <boxGeometry args={[0.09, 0.012, 0.09]} />
        <meshStandardMaterial color="#020617" metalness={0.9} roughness={0.1} />
      </mesh>
      {/* MCU Pins */}
      <lineSegments position={[0, 0.01, 0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(0.105, 0.005, 0.105)]} />
        <lineBasicMaterial color="#cbd5e1" />
      </lineSegments>

      {/* Power MOSFET Balancing Array with Aluminum Heatsink Clamp */}
      <mesh position={[0, 0.018, bmsD / 4]}>
        <boxGeometry args={[bmsW * 0.75, 0.015, 0.05]} />
        <meshStandardMaterial color="#334155" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Precision Current Sense Shunt Resistor */}
      <mesh position={[bmsW / 3, 0.014, -bmsD / 4]}>
        <boxGeometry args={[0.05, 0.01, 0.03]} />
        <meshStandardMaterial color="#b45309" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Multi-Pin JST Balance Harness Header */}
      <mesh position={[-bmsW / 3, 0.018, 0]}>
        <boxGeometry args={[0.04, 0.02, 0.18]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.4} />
      </mesh>

      {/* Individual Colored Voltage Sense Balance Wires Routing to Series Groups */}
      <group position={[-bmsW / 3, 0.018, 0]}>
        {Array.from({ length: Math.min(ns, 8) }).map((_, w) => {
          const targetZ = (w - (Math.min(ns, 8) - 1) / 2) * spacingZ * 0.9;
          const wireColor = wireColors[w % wireColors.length];
          return (
            <mesh key={w} position={[0.02, 0.005, targetZ * 0.4]}>
              <cylinderGeometry args={[0.003, 0.003, 0.08, 6]} />
              <meshStandardMaterial color={wireColor} roughness={0.6} />
            </mesh>
          );
        })}
      </group>

      {/* Telemetry Status Diagnostic LEDs */}
      <mesh position={[-bmsW / 2 + 0.06, 0.018, -bmsD / 2 + 0.06]}>
        <sphereGeometry args={[0.014, 8, 8]} />
        <meshBasicMaterial color={ledBlink ? "#10b981" : "#064e3b"} />
      </mesh>
      <mesh position={[-bmsW / 2 + 0.11, 0.018, -bmsD / 2 + 0.06]}>
        <sphereGeometry args={[0.014, 8, 8]} />
        <meshBasicMaterial color={isSimulating ? "#00f0ff" : "#0369a1"} />
      </mesh>
    </group>
  );
}

// ── Outer Protective Enclosure Shell ──────────────────────────────────────────
function EnclosureShell({
  width,
  depth,
  explodeAmount,
  showLid = true,
}: {
  width: number;
  depth: number;
  explodeAmount: number;
  showLid?: boolean;
}) {
  const topLidRef = useRef<THREE.Group>(null);
  const baseChassisRef = useRef<THREE.Group>(null);

  useFrame(() => {
    if (topLidRef.current) {
      topLidRef.current.position.y = THREE.MathUtils.lerp(topLidRef.current.position.y, 0.55 + explodeAmount * 2.2, 0.12);
    }
    if (baseChassisRef.current) {
      baseChassisRef.current.position.y = THREE.MathUtils.lerp(baseChassisRef.current.position.y, -0.58 - explodeAmount * 2.2, 0.12);
    }
  });

  const encW = width + 0.24;
  const encD = depth + 0.24;

  return (
    <>
      {/* Top Enclosure Lid (Transparent Polycarbonate with Anodized Bezel) */}
      {showLid && (
        <group ref={topLidRef} position={[0, 0.55, 0]}>
          <mesh castShadow>
            <boxGeometry args={[encW, 0.02, encD]} />
            <meshStandardMaterial
              color="#00f0ff"
              transparent
              opacity={0.22}
              roughness={0.1}
              metalness={0.9}
            />
          </mesh>
          <lineSegments>
            <edgesGeometry args={[new THREE.BoxGeometry(encW, 0.02, encD)]} />
            <lineBasicMaterial color="#00f0ff" linewidth={2} />
          </lineSegments>

          {/* Corner Structural Fastener Bolts */}
          {[
            [-encW / 2 + 0.04, -encD / 2 + 0.04],
            [encW / 2 - 0.04, -encD / 2 + 0.04],
            [-encW / 2 + 0.04, encD / 2 - 0.04],
            [encW / 2 - 0.04, encD / 2 - 0.04],
          ].map(([bx, bz], i) => (
            <mesh key={i} position={[bx, 0.015, bz]}>
              <cylinderGeometry args={[0.015, 0.015, 0.01, 8]} />
              <meshStandardMaterial color="#cbd5e1" metalness={0.95} />
            </mesh>
          ))}
        </group>
      )}

      {/* Heavy-Duty Aluminum Pack Chassis Bottom Tray */}
      <group ref={baseChassisRef} position={[0, -0.58, 0]}>
        <mesh receiveShadow>
          <boxGeometry args={[encW, 0.08, encD]} />
          <meshStandardMaterial color="#091322" metalness={0.8} roughness={0.3} />
        </mesh>
        <lineSegments>
          <edgesGeometry args={[new THREE.BoxGeometry(encW, 0.08, encD)]} />
          <lineBasicMaterial color="#0284c7" transparent opacity={0.6} />
        </lineSegments>
      </group>
    </>
  );
}

// ── Native WebGL 3D Dimension Badge (Zero React DOM roots, 100% immune to React 19 unmount issues) ──
function DimensionBadgeSprite({
  position,
  title,
  value,
  subtitle,
  badgeColor = "#00f0ff",
  scale = [0.65, 0.20, 1],
}: {
  position: [number, number, number];
  title: string;
  value: string;
  subtitle?: string;
  badgeColor?: string;
  scale?: [number, number, number];
}) {
  const texture = useMemo(() => {
    if (typeof document === "undefined") return null;
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 160;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    ctx.clearRect(0, 0, 512, 160);

    // High-tech rounded HUD container
    ctx.fillStyle = "rgba(4, 12, 28, 0.94)";
    ctx.strokeStyle = badgeColor;
    ctx.lineWidth = 4;
    ctx.beginPath();
    if (typeof ctx.roundRect === "function") {
      ctx.roundRect(12, 12, 488, 136, 20);
    } else {
      ctx.rect(12, 12, 488, 136);
    }
    ctx.fill();
    ctx.stroke();

    // Subtle inner accent line
    ctx.strokeStyle = "rgba(255, 255, 255, 0.22)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    if (typeof ctx.roundRect === "function") {
      ctx.roundRect(18, 18, 476, 124, 16);
    } else {
      ctx.rect(18, 18, 476, 124);
    }
    ctx.stroke();

    // Title / Type
    ctx.fillStyle = badgeColor;
    ctx.font = "bold 26px 'Courier New', monospace, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(title.toUpperCase(), 256, 44);

    // Main Metric Value
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 38px 'Courier New', monospace, sans-serif";
    ctx.fillText(value, 256, subtitle ? 88 : 98);

    // Subtitle note
    if (subtitle) {
      ctx.fillStyle = "rgba(148, 163, 184, 0.95)";
      ctx.font = "600 20px 'Courier New', monospace, sans-serif";
      ctx.fillText(subtitle, 256, 124);
    }

    const tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    tex.magFilter = THREE.LinearFilter;
    tex.needsUpdate = true;
    return tex;
  }, [title, value, subtitle, badgeColor]);

  useEffect(() => {
    return () => {
      if (texture) texture.dispose();
    };
  }, [texture]);

  if (!texture) return null;

  return (
    <sprite position={position} scale={scale}>
      <spriteMaterial map={texture} transparent depthTest={false} depthWrite={false} />
    </sprite>
  );
}

// ── 3D Dimension Line with Witness Extensions & Native WebGL Billboard Badge ──
function DimensionArrowLine({
  start,
  end,
  title,
  value,
  subtitle,
  badgeColor = "#00f0ff",
  extensionStart1,
  extensionEnd1,
  extensionStart2,
  extensionEnd2,
  badgeOffset = [0, 0, 0],
  badgeScale = [0.65, 0.20, 1],
}: {
  start: [number, number, number];
  end: [number, number, number];
  title: string;
  value: string;
  subtitle?: string;
  badgeColor?: string;
  extensionStart1?: [number, number, number];
  extensionEnd1?: [number, number, number];
  extensionStart2?: [number, number, number];
  extensionEnd2?: [number, number, number];
  badgeOffset?: [number, number, number];
  badgeScale?: [number, number, number];
}) {
  const linePoints = useMemo(() => [new THREE.Vector3(...start), new THREE.Vector3(...end)], [start, end]);
  const lineGeo = useMemo(() => new THREE.BufferGeometry().setFromPoints(linePoints), [linePoints]);

  const midPos: [number, number, number] = [
    (start[0] + end[0]) / 2 + badgeOffset[0],
    (start[1] + end[1]) / 2 + badgeOffset[1],
    (start[2] + end[2]) / 2 + badgeOffset[2],
  ];

  const extGeo1 = useMemo(() => {
    if (!extensionStart1 || !extensionEnd1) return null;
    return new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(...extensionStart1),
      new THREE.Vector3(...extensionEnd1),
    ]);
  }, [extensionStart1, extensionEnd1]);

  const extGeo2 = useMemo(() => {
    if (!extensionStart2 || !extensionEnd2) return null;
    return new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(...extensionStart2),
      new THREE.Vector3(...extensionEnd2),
    ]);
  }, [extensionStart2, extensionEnd2]);

  const mainLine = useMemo(() => {
    const mat = new THREE.LineBasicMaterial({ color: badgeColor, linewidth: 2 });
    return new THREE.Line(lineGeo, mat);
  }, [lineGeo, badgeColor]);

  const extLine1 = useMemo(() => {
    if (!extGeo1) return null;
    const mat = new THREE.LineBasicMaterial({ color: "#38bdf8", transparent: true, opacity: 0.35 });
    return new THREE.Line(extGeo1, mat);
  }, [extGeo1]);

  const extLine2 = useMemo(() => {
    if (!extGeo2) return null;
    const mat = new THREE.LineBasicMaterial({ color: "#38bdf8", transparent: true, opacity: 0.35 });
    return new THREE.Line(extGeo2, mat);
  }, [extGeo2]);

  return (
    <group>
      {/* Witness Extension Lines */}
      {extLine1 && <primitive object={extLine1} />}
      {extLine2 && <primitive object={extLine2} />}

      {/* Main Dimension Line */}
      <primitive object={mainLine} />

      {/* Glowing End Spheres */}
      <mesh position={start}>
        <sphereGeometry args={[0.022, 12, 12]} />
        <meshBasicMaterial color={badgeColor} />
      </mesh>
      <mesh position={end}>
        <sphereGeometry args={[0.022, 12, 12]} />
        <meshBasicMaterial color={badgeColor} />
      </mesh>

      {/* Native WebGL Billboard Badge */}
      <DimensionBadgeSprite
        position={midPos}
        title={title}
        value={value}
        subtitle={subtitle}
        badgeColor={badgeColor}
        scale={badgeScale}
      />
    </group>
  );
}

// ── 3D Physical Assembly & Cell Dimensions Display ──
function PackDimensions3D({
  width,
  depth,
  cellDiameterMm = 21.4,
  cellHeightMm = 70.0,
  packLengthMm,
  packWidthMm,
  packHeightMm,
  ns = 14,
  np = 8,
  explodeAmount = 0,
}: {
  width: number;
  depth: number;
  cellDiameterMm?: number;
  cellHeightMm?: number;
  packLengthMm?: number;
  packWidthMm?: number;
  packHeightMm?: number;
  ns?: number;
  np?: number;
  explodeAmount?: number;
}) {
  const encW = width + 0.24;
  const encD = depth + 0.24;
  const halfW = encW / 2;
  const halfD = encD / 2;

  const bottomY = -0.42 - explodeAmount * 0.45;
  const topY = 0.42 + explodeAmount * 0.45;
  const offset = 0.38;

  const lengthMm = packLengthMm ?? 235.2;
  const widthMm = packWidthMm ?? 80.6;
  const heightMm = packHeightMm ?? 70.0;

  // Front-left reference cell location in Three.js coordinates
  const cellSpacing = 0.24;
  const cornerCellX = -((np - 1) / 2) * cellSpacing;
  const cornerCellZ = ((ns - 1) / 2) * cellSpacing;

  return (
    <group>
      {/* 1. INDIVIDUAL CELL DIMENSIONS CALLOUT (Cell Height & Diameter) */}
      <DimensionArrowLine
        start={[cornerCellX - 0.20, -0.35, cornerCellZ]}
        end={[cornerCellX - 0.20, 0.35, cornerCellZ]}
        title="CELL DIMENSIONS"
        value={`Ø${cellDiameterMm.toFixed(1)} × ${cellHeightMm.toFixed(0)} mm`}
        subtitle={`Cell Height: ${cellHeightMm.toFixed(0)}mm · Diam: ${cellDiameterMm.toFixed(1)}mm`}
        badgeColor="#10b981"
        extensionStart1={[cornerCellX, -0.35, cornerCellZ]}
        extensionEnd1={[cornerCellX - 0.22, -0.35, cornerCellZ]}
        extensionStart2={[cornerCellX, 0.35, cornerCellZ]}
        extensionEnd2={[cornerCellX - 0.22, 0.35, cornerCellZ]}
        badgeOffset={[-0.20, 0, 0]}
        badgeScale={[0.72, 0.22, 1]}
      />

      {/* 2. PACK LENGTH Callout (along Z axis / Series rows) */}
      <DimensionArrowLine
        start={[-halfW - offset, bottomY, -halfD]}
        end={[-halfW - offset, bottomY, halfD]}
        title="PACK LENGTH"
        value={`${lengthMm.toFixed(1)} mm`}
        subtitle={`${ns}S Series Length`}
        badgeColor="#38bdf8"
        extensionStart1={[-halfW, bottomY, -halfD]}
        extensionEnd1={[-halfW - offset - 0.05, bottomY, -halfD]}
        extensionStart2={[-halfW, bottomY, halfD]}
        extensionEnd2={[-halfW - offset - 0.05, bottomY, halfD]}
        badgeOffset={[0, 0.16, 0]}
        badgeScale={[0.65, 0.20, 1]}
      />

      {/* 3. PACK WIDTH Callout (along X axis / Parallel columns) */}
      <DimensionArrowLine
        start={[-halfW, bottomY, halfD + offset]}
        end={[halfW, bottomY, halfD + offset]}
        title="PACK WIDTH"
        value={`${widthMm.toFixed(1)} mm`}
        subtitle={`${np}P Parallel Width`}
        badgeColor="#38bdf8"
        extensionStart1={[-halfW, bottomY, halfD]}
        extensionEnd1={[-halfW, bottomY, halfD + offset + 0.05]}
        extensionStart2={[halfW, bottomY, halfD]}
        extensionEnd2={[halfW, bottomY, halfD + offset + 0.05]}
        badgeOffset={[0, 0.16, 0]}
        badgeScale={[0.65, 0.20, 1]}
      />

      {/* 4. PACK HEIGHT Callout (Vertical along Y axis) */}
      <DimensionArrowLine
        start={[halfW + offset, bottomY, halfD]}
        end={[halfW + offset, topY, halfD]}
        title="PACK HEIGHT"
        value={`${heightMm.toFixed(1)} mm`}
        subtitle="Pack Height (Z-Axis)"
        badgeColor="#38bdf8"
        extensionStart1={[halfW, bottomY, halfD]}
        extensionEnd1={[halfW + offset + 0.05, bottomY, halfD]}
        extensionStart2={[halfW, topY, halfD]}
        extensionEnd2={[halfW + offset + 0.05, topY, halfD]}
        badgeOffset={[0.22, 0, 0]}
        badgeScale={[0.65, 0.20, 1]}
      />
    </group>
  );
}

// ── Main Scene Internals ──────────────────────────────────────────────────────
function BatterySceneContent({
  ns = 14,
  np = 8,
  coolingType = "passive",
  showEnclosure = true,
  colorMode = "default",
  thermalData,
  exploded = false,
  explodeAmount = 0,
  isSimulating = false,
  simTimeS = 0,
  simCurrentA = 30,
  simSoc = 0.95,
  simTempC = 25,
  onCellSelect,
  showDimensions = true,
  cellDiameterMm = 21.4,
  cellHeightMm = 70.0,
  packLengthMm,
  packWidthMm,
  packHeightMm,
}: StarkBatteryVisualizerProps) {
  const [selectedCell, setSelectedCell] = useState<{ s: number; p: number; id: number } | null>(null);
  const [pulse, setPulse] = useState(0);

  // Dynamic grid setup (bounded to prevent GPU overload)
  const ROWS = Math.max(1, Math.min(ns, 24));
  const COLS = Math.max(1, Math.min(np, 24));

  // Reset selected cell telemetry popup during render when topology changes (prevents stale coordinate bug)
  const [prevTopology, setPrevTopology] = useState({ ns, np });
  if (prevTopology.ns !== ns || prevTopology.np !== np) {
    setPrevTopology({ ns, np });
    setSelectedCell(null);
  }
  const spacingX = 0.24;
  const spacingZ = 0.24;
  const totalWidth = COLS * spacingX;
  const totalDepth = ROWS * spacingZ;

  const currentExplode = exploded ? Math.max(0.65, explodeAmount || 0.8) : explodeAmount;

  useFrame((_, delta) => {
    if (isSimulating) {
      setPulse((p) => (p + delta * 3) % (Math.PI * 2));
    }
  });

  // Generate cells with dynamic positions and thermal physics
  const cells = useMemo(() => {
    const list: {
      id: number;
      s: number;
      p: number;
      basePos: [number, number, number];
      targetPos: [number, number, number];
      temp: number;
      isCutaway: boolean;
    }[] = [];

    let id = 0;
    for (let s = 0; s < ROWS; s++) {
      for (let p = 0; p < COLS; p++) {
        const baseX = (p - (COLS - 1) / 2) * spacingX;
        const baseZ = (s - (ROWS - 1) / 2) * spacingZ;

        // Controlled radial expansion during exploded view (+12% max)
        const explodeFactor = 1 + currentExplode * 0.12;
        const targetX = baseX * explodeFactor;
        const targetZ = baseZ * explodeFactor;
        const tierY = currentExplode * Math.sin(p * 0.6 + s * 0.6) * 0.08;

        // Radial thermal gradient: core runs hotter than perimeter
        const distFromCenter = Math.sqrt(
          Math.pow((p - (COLS - 1) / 2) / (COLS / 2 || 1), 2) +
          Math.pow((s - (ROWS - 1) / 2) / (ROWS / 2 || 1), 2)
        );
        const coreHeatOffset = (1 - Math.min(1, distFromCenter)) * 14;
        const cellTemp = (simTempC || 25) + coreHeatOffset;

        // Designated front-corner cell cutaway so user can see inside the cell architecture
        const isCutaway = s === 0 && p === 0;

        list.push({
          id,
          s,
          p,
          basePos: [baseX, 0, baseZ],
          targetPos: [targetX, tierY, targetZ],
          temp: thermalData ? (thermalData[id] ?? cellTemp) : cellTemp,
          isCutaway,
        });
        id++;
      }
    }
    return list;
  }, [ROWS, COLS, spacingX, spacingZ, currentExplode, simTempC, thermalData]);

  return (
    <>
      {/* ── Studio Lighting ── */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[14, 18, 14]} intensity={1.6} castShadow />
      <directionalLight position={[-14, -8, -14]} intensity={0.6} color="#0284c7" />
      <pointLight position={[0, 6, 0]} color="#00f0ff" intensity={2.0} distance={22} />
      <pointLight position={[totalWidth / 2, -2, totalDepth / 2]} color="#f59e0b" intensity={0.8} />

      {/* ── Battery Cells with Internal Cutaway Inspection ── */}
      <group>
        {cells.map((cell) => (
          <RealisticCell
            key={cell.id}
            cellId={cell.id}
            sIndex={cell.s}
            pIndex={cell.p}
            basePos={cell.basePos}
            targetPos={cell.targetPos}
            tempC={cell.temp}
            colorMode={colorMode}
            isSimulating={isSimulating}
            simPulse={pulse}
            isCutaway={cell.isCutaway || selectedCell?.id === cell.id}
            selected={selectedCell?.id === cell.id}
            onSelect={() => {
              setSelectedCell(cell);
              onCellSelect?.({
                s: cell.s,
                p: cell.p,
                id: cell.id,
                temp: cell.temp,
                v: 3.7,
              });
            }}
          />
        ))}
      </group>

      {/* ── Laser-Welded Busbars & High-Current Main Terminals ── */}
      <Busbars
        ns={ROWS}
        np={COLS}
        spacingX={spacingX}
        spacingZ={spacingZ}
        explodeAmount={currentExplode}
        isSimulating={isSimulating}
      />

      {/* ── Honeycomb Matrix Cell Holders ── */}
      <CellHolders
        width={totalWidth}
        depth={totalDepth}
        ns={ROWS}
        np={COLS}
        spacingX={spacingX}
        spacingZ={spacingZ}
        explodeAmount={currentExplode}
      />

      {/* ── Responsive Multi-Physics Thermal Management System ── */}
      {/* key={coolingType} forces a full React remount when the cooling mode changes */}
      <ThermalManagementSystem
        key={coolingType}
        width={totalWidth}
        depth={totalDepth}
        ns={ROWS}
        np={COLS}
        spacingX={spacingX}
        spacingZ={spacingZ}
        explodeAmount={currentExplode}
        coolingType={coolingType}
        isSimulating={isSimulating}
      />

      {/* ── Battery Management System (BMS) PCB & Balance Wire Harness ── */}
      <BMSBoard
        width={totalWidth}
        depth={totalDepth}
        ns={ROWS}
        spacingZ={spacingZ}
        explodeAmount={currentExplode}
        isSimulating={isSimulating}
      />

      {/* ── Protective Outer Enclosure Shell ── */}
      {showEnclosure && (
        <EnclosureShell
          width={totalWidth}
          depth={totalDepth}
          explodeAmount={currentExplode}
          showLid={true}
        />
      )}

      {/* ── 3D Physical CAD & Cell Dimension Lines & Measurement Callouts ── */}
      {showDimensions && (
        <PackDimensions3D
          width={totalWidth}
          depth={totalDepth}
          cellDiameterMm={cellDiameterMm}
          cellHeightMm={cellHeightMm}
          packLengthMm={packLengthMm}
          packWidthMm={packWidthMm}
          packHeightMm={packHeightMm}
          ns={ROWS}
          np={COLS}
          explodeAmount={currentExplode}
        />
      )}

      {/* ── Engineering CAD Floor Grid ── */}
      <gridHelper args={[24, 48, "#00f0ff", "#002440"]} position={[0, -0.95 - currentExplode * 2.2, 0]} />

      {/* Selected Cell Floating Telemetry HUD (Pure WebGL Native Sprite - Zero ReactDOM roots) */}
      {selectedCell && selectedCell.s < ROWS && selectedCell.p < COLS && (
        <DimensionBadgeSprite
          position={[0, 1.45, 0]}
          title={`CELL #${selectedCell.id} (S${selectedCell.s + 1} × P${selectedCell.p + 1})`}
          value={`3.70V · ${((simTempC || 25) + 6).toFixed(1)}°C · ${(simCurrentA / (np || 1)).toFixed(1)}A`}
          subtitle={`Cell: Ø${cellDiameterMm.toFixed(1)}×${cellHeightMm.toFixed(0)}mm · ${((simSoc || 0.95) * 100).toFixed(0)}% SOC${simTimeS > 0 ? ` · ${(simTimeS / 60).toFixed(1)}m` : ""}`}
          badgeColor="#00f0ff"
          scale={[1.15, 0.35, 1]}
        />
      )}

      {/* 3D Camera Controls */}
      <OrbitControls
        enablePan
        minDistance={2}
        maxDistance={35}
        autoRotate={!selectedCell && !exploded}
        autoRotateSpeed={0.35}
      />
    </>
  );
}

// ── Exported Full Interactive Visualizer Canvas ──────────────────────────────
export function StarkBatteryVisualizer(props: StarkBatteryVisualizerProps) {
  const cols = Math.max(1, Math.min(props.np || 8, 24));
  const rows = Math.max(1, Math.min(props.ns || 14, 24));
  const maxDim = Math.max(cols * 0.24, rows * 0.24);
  const camDist = Math.max(6, maxDim * 1.8);

  return (
    <Canvas
      camera={{ position: [camDist * 0.75, camDist * 0.65, camDist * 0.95], fov: 46 }}
      style={{ width: "100%", height: "100%", background: "transparent" }}
      gl={{ antialias: true, alpha: true }}
      onCreated={({ gl }) => {
        gl.shadowMap.enabled = true;
        gl.shadowMap.type = THREE.PCFShadowMap;
      }}
    >
      <BatterySceneContent {...props} />
    </Canvas>
  );
}

// Legacy Aliases for backwards compatibility
export const BatteryScene3D = StarkBatteryVisualizer;
export const LandingBatteryScene = (props: StarkBatteryVisualizerProps) => (
  <StarkBatteryVisualizer ns={7} np={8} showEnclosure={true} {...props} />
);
export default StarkBatteryVisualizer;
