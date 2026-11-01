"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, CellSpec, RequirementCreate } from "@/lib/api";
import { ChevronRight, ChevronLeft, Check, Zap, AlertCircle } from "lucide-react";

const STEPS = ["Project Info", "Requirements", "Design Mode", "Starting Config"];
const CATEGORIES = ["Custom", "EV Scooter", "EV Bicycle", "EV Car", "Stationary Storage", "Marine", "Aerospace"];
const COOLING_OPTIONS = ["passive", "fan", "liquid", "phase_change"];

export default function NewProjectWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1
  const [name, setName] = useState("");
  const [category, setCategory] = useState("EV Scooter");
  const [description, setDescription] = useState("");
  const [engineer, setEngineer] = useState("");
  const [version, setVersion] = useState("0.1");

  // Step 2 — requirements
  const [targetV, setTargetV] = useState("");
  const [targetE, setTargetE] = useState("");
  const [energyUsable, setEnergyUsable] = useState(false);
  const [contCurrent, setContCurrent] = useState("");
  const [peakCurrent, setPeakCurrent] = useState("");
  const [maxMass, setMaxMass] = useState("");
  const [maxCost, setMaxCost] = useState("");
  const [minTemp, setMinTemp] = useState("-10");
  const [maxTemp, setMaxTemp] = useState("40");
  const [cooling, setCooling] = useState("passive");
  const [designNotes, setDesignNotes] = useState("");

  // Step 3
  const [designMode, setDesignMode] = useState<"requirements_first" | "manual">("requirements_first");

  // Step 4
  const [cells, setCells] = useState<CellSpec[]>([]);
  const [cellsLoading, setCellsLoading] = useState(false);
  const [selectedCell, setSelectedCell] = useState<number | null>(null);
  const [ns, setNs] = useState("14");
  const [np, setNp] = useState("8");

  async function loadCells() {
    setCellsLoading(true);
    try {
      const data = await api.library.cells();
      setCells(data);
      if (data.length > 0) setSelectedCell(data[0].id);
    } catch { /* ignore */ }
    setCellsLoading(false);
  }

  function validateStep(s: number): string | null {
    if (s === 0 && !name.trim()) return "Project name is required.";
    if (s === 1) {
      if (!targetV || isNaN(+targetV) || +targetV <= 0) return "Target voltage must be a positive number.";
      if (!targetE || isNaN(+targetE) || +targetE <= 0) return "Target energy must be a positive number.";
    }
    if (s === 3 && !selectedCell) return "Please select a cell.";
    return null;
  }

  function next() {
    const err = validateStep(step);
    if (err) { setError(err); return; }
    setError(null);
    if (step === 2) loadCells();
    setStep((s) => s + 1);
  }

  function back() { setError(null); setStep((s) => s - 1); }

  async function finish() {
    const err = validateStep(step);
    if (err) { setError(err); return; }
    setSaving(true);
    setError(null);
    try {
      // Create project
      const project = await api.projects.create({
        name, description, application_category: category,
        engineer_label: engineer, design_version: version,
      });

      // Create requirement
      const reqBody: RequirementCreate = {
        target_voltage_v: +targetV,
        target_energy_wh: +targetE,
        energy_is_usable: energyUsable,
        continuous_current_a: contCurrent ? +contCurrent : undefined,
        peak_current_a: peakCurrent ? +peakCurrent : undefined,
        max_mass_kg: maxMass ? +maxMass : undefined,
        max_cost_usd: maxCost ? +maxCost : undefined,
        min_ambient_temp_c: minTemp ? +minTemp : undefined,
        max_ambient_temp_c: maxTemp ? +maxTemp : undefined,
        cooling_preference: cooling,
        design_notes: designNotes,
        hard_constraints: ["target_voltage_v", "target_energy_wh"],
      };
      await api.projects.requirements.create(project.id, reqBody);

      // Create initial configuration
      if (selectedCell) {
        await api.projects.configurations.create(project.id, {
          label: "Initial Configuration",
          design_mode: designMode,
          cell_spec_id: selectedCell,
          ns: +ns,
          np: +np,
          cooling_type: cooling,
          is_baseline: true,
        });
      }

      router.push(`/projects/${project.id}/design`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create project");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      {/* Progress */}
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "1.25rem" }}>New Battery Project</h1>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          {STEPS.map((s, i) => (
            <div key={s} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <div style={{
                width: 28, height: 28, borderRadius: "50%",
                background: i < step ? "var(--success)" : i === step ? "var(--accent)" : "var(--bg-surface)",
                border: `2px solid ${i <= step ? (i < step ? "var(--success)" : "var(--accent)") : "var(--border)"}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "0.75rem", fontWeight: 700,
                color: i <= step ? (i < step ? "#fff" : "#000") : "var(--text-muted)",
                transition: "all 0.3s",
              }}>
                {i < step ? <Check size={14} /> : i + 1}
              </div>
              <span style={{
                fontSize: "0.8rem",
                color: i === step ? "var(--text-primary)" : "var(--text-muted)",
                fontWeight: i === step ? 600 : 400,
              }}>{s}</span>
              {i < STEPS.length - 1 && (
                <div style={{ width: 40, height: 2, background: i < step ? "var(--success)" : "var(--border-subtle)" }} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step content */}
      <div className="card fade-in" style={{ marginBottom: "1rem" }}>
        {step === 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.125rem" }}>
            <h2 style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Project Information</h2>
            <Field label="Project Name *" required>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. 48V EV Scooter Battery Rev2" />
            </Field>
            <Field label="Application Category">
              <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Description">
              <textarea className="input" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Brief description of the design exercise…" style={{ resize: "vertical" }} />
            </Field>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <Field label="Engineer / Team (optional)">
                <input className="input" value={engineer} onChange={(e) => setEngineer(e.target.value)} placeholder="e.g. EV Engineering Team" />
              </Field>
              <Field label="Design Version">
                <input className="input" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="0.1" />
              </Field>
            </div>
          </div>
        )}

        {step === 1 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.125rem" }}>
            <h2 style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Engineering Requirements</h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <Field label="Target Nominal Voltage (V) *">
                <input className="input" type="number" value={targetV} onChange={(e) => setTargetV(e.target.value)} placeholder="51.8" />
              </Field>
              <Field label="Target Energy (Wh) *">
                <input className="input" type="number" value={targetE} onChange={(e) => setTargetE(e.target.value)} placeholder="4000" />
              </Field>
            </div>
            <Field label="Energy target type">
              <div style={{ display: "flex", gap: "1rem" }}>
                {[false, true].map((u) => (
                  <label key={String(u)} style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontSize: "0.875rem" }}>
                    <input type="radio" checked={energyUsable === u} onChange={() => setEnergyUsable(u)} />
                    {u ? "Usable energy" : "Nominal energy"}
                  </label>
                ))}
              </div>
            </Field>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <Field label="Continuous Pack Current (A)">
                <input className="input" type="number" value={contCurrent} onChange={(e) => setContCurrent(e.target.value)} placeholder="40" />
              </Field>
              <Field label="Peak Pack Current (A)">
                <input className="input" type="number" value={peakCurrent} onChange={(e) => setPeakCurrent(e.target.value)} placeholder="80" />
              </Field>
              <Field label="Max Pack Mass (kg)">
                <input className="input" type="number" value={maxMass} onChange={(e) => setMaxMass(e.target.value)} placeholder="25" />
              </Field>
              <Field label="Max BOM Cost (USD)">
                <input className="input" type="number" value={maxCost} onChange={(e) => setMaxCost(e.target.value)} placeholder="optional" />
              </Field>
              <Field label="Min Ambient Temp (°C)">
                <input className="input" type="number" value={minTemp} onChange={(e) => setMinTemp(e.target.value)} placeholder="-10" />
              </Field>
              <Field label="Max Ambient Temp (°C)">
                <input className="input" type="number" value={maxTemp} onChange={(e) => setMaxTemp(e.target.value)} placeholder="40" />
              </Field>
            </div>
            <Field label="Cooling Preference">
              <select className="select" value={cooling} onChange={(e) => setCooling(e.target.value)}>
                {COOLING_OPTIONS.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Design Notes">
              <textarea className="input" rows={2} value={designNotes} onChange={(e) => setDesignNotes(e.target.value)} placeholder="Any additional constraints or notes…" style={{ resize: "vertical" }} />
            </Field>
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 style={{ fontWeight: 600, marginBottom: "1rem" }}>Choose Design Mode</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
              {[
                {
                  key: "requirements_first" as const,
                  title: "Requirements-First (Recommended)",
                  desc: "Automatically generate candidate configurations from your requirements and selected cell. BattLab evaluates feasibility and ranks results.",
                },
                {
                  key: "manual" as const,
                  title: "Manual Configuration",
                  desc: "Manually specify series count, parallel count, module grouping and supporting components. Full control over the topology.",
                },
              ].map((opt) => (
                <button
                  key={opt.key}
                  onClick={() => setDesignMode(opt.key)}
                  style={{
                    background: designMode === opt.key ? "rgba(0,212,255,0.08)" : "var(--bg-surface)",
                    border: `2px solid ${designMode === opt.key ? "var(--accent)" : "var(--border-subtle)"}`,
                    borderRadius: 10, padding: "1rem 1.25rem", cursor: "pointer",
                    textAlign: "left", transition: "all 0.2s",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.375rem" }}>
                    <div style={{
                      width: 18, height: 18, borderRadius: "50%",
                      border: `2px solid ${designMode === opt.key ? "var(--accent)" : "var(--border)"}`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      {designMode === opt.key && <div style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--accent)" }} />}
                    </div>
                    <span style={{ fontWeight: 600 }}>{opt.title}</span>
                  </div>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", paddingLeft: "1.625rem" }}>{opt.desc}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <h2 style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Starting Configuration</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginBottom: "1.25rem" }}>
              Select a cell from the library and set the initial topology.
            </p>
            {cellsLoading ? (
              <div className="spinner" />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <Field label="Select Cell">
                  <select className="select" value={selectedCell ?? ""} onChange={(e) => setSelectedCell(+e.target.value)}>
                    {cells.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.manufacturer} {c.model} — {c.nominal_voltage_v}V / {c.nominal_capacity_ah}Ah [{c.data_status}]
                      </option>
                    ))}
                  </select>
                </Field>
                {selectedCell && cells.find((c) => c.id === selectedCell)?.data_status === "provisional" && (
                  <div style={{
                    display: "flex", gap: "0.625rem", alignItems: "flex-start",
                    background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)",
                    borderRadius: 8, padding: "0.75rem",
                  }}>
                    <AlertCircle size={15} color="var(--warning)" style={{ flexShrink: 0, marginTop: 1 }} />
                    <p style={{ fontSize: "0.8rem", color: "#d97706" }}>
                      This is a provisional/illustrative cell. All specifications are assumed demo values.
                      Replace with verified manufacturer data for engineering decisions.
                    </p>
                  </div>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <Field label="Series Count (Ns)">
                    <input className="input" type="number" min={1} value={ns} onChange={(e) => setNs(e.target.value)} />
                  </Field>
                  <Field label="Parallel Count (Np)">
                    <input className="input" type="number" min={1} value={np} onChange={(e) => setNp(e.target.value)} />
                  </Field>
                </div>
                {selectedCell && ns && np && (
                  <div className="card-surface">
                    <p className="section-title">Calculated Preview</p>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "0.75rem" }}>
                      {(() => {
                        const cell = cells.find((c) => c.id === selectedCell);
                        if (!cell) return null;
                        const v = +ns * cell.nominal_voltage_v;
                        const ah = +np * cell.nominal_capacity_ah;
                        const wh = v * ah;
                        return <>
                          <CalcPreview label="Nominal Voltage" value={`${v.toFixed(1)} V`} />
                          <CalcPreview label="Pack Capacity" value={`${ah.toFixed(0)} Ah`} />
                          <CalcPreview label="Nominal Energy" value={`${wh.toFixed(0)} Wh`} />
                          <CalcPreview label="Total Cells" value={`${+ns * +np}`} />
                        </>;
                      })()}
                    </div>
                    <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "0.625rem" }}>
                      Provisional calculated preview. Confirmed values will be computed by the backend.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div style={{
          display: "flex", gap: "0.5rem", alignItems: "center",
          background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)",
          borderRadius: 8, padding: "0.75rem 1rem", marginBottom: "1rem",
          fontSize: "0.875rem", color: "var(--danger)",
        }}>
          <AlertCircle size={15} /> {error}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem" }}>
        {step > 0 ? (
          <button className="btn-secondary" onClick={back}><ChevronLeft size={16} /> Back</button>
        ) : <div />}
        {step < STEPS.length - 1 ? (
          <button className="btn-primary" onClick={next}>Next <ChevronRight size={16} /></button>
        ) : (
          <button className="btn-primary" onClick={finish} disabled={saving}>
            {saving ? <><div className="spinner" style={{ width: 16, height: 16 }} /> Creating…</> : <><Zap size={16} /> Create Project</>}
          </button>
        )}
      </div>
    </div>
  );
}

function Field({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div className="field">
      <label className="label">{label}{required && " *"}</label>
      {children}
    </div>
  );
}

function CalcPreview({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{value}</div>
    </div>
  );
}
