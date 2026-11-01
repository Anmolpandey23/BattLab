"use client";
import { useEffect, useState, Fragment } from "react";
import { api, CellSpec } from "@/lib/api";
import { Plus, Trash2, Search, ChevronDown, ChevronUp, AlertCircle, LayoutGrid, Table as TableIcon } from "lucide-react";
import AppLayout from "@/components/layout/AppLayout";
import { BatteryCellCard } from "@/components/battery-ui/BatteryWidgets";

const CHEMISTRIES = ["NMC", "LFP", "NCA", "LTO", "NiMH", "Lead-Acid", "Other"];
const FORM_FACTORS = ["21700", "18650", "26650", "pouch", "prismatic", "custom"];

export default function LibraryPage() {
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");
  const [selectedChemistry, setSelectedChemistry] = useState<string>("ALL");
  const [cells, setCells] = useState<CellSpec[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [cellToDelete, setCellToDelete] = useState<{ id: number; name: string } | null>(null);
  const [selectedReplacementId, setSelectedReplacementId] = useState<number | null>(null);
  const [deletingCellId, setDeletingCellId] = useState<number | null>(null);

  // Form state
  const [form, setForm] = useState({
    manufacturer: "", model: "", chemistry: "NMC", form_factor: "21700",
    nominal_voltage_v: "3.7", nominal_capacity_ah: "5.0",
    min_voltage_v: "2.5", max_voltage_v: "4.2",
    internal_resistance_ohm: "", max_continuous_discharge_a: "",
    mass_kg: "", unit_cost_usd: "",
    datasheet_url: "", source_notes: "",
  });

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await api.library.cells();
        if (active) {
          setCells(data);
          setLoading(false);
        }
      } catch (e: unknown) {
        if (active) {
          setError(e instanceof Error ? e.message : "Failed to load cells");
          setLoading(false);
        }
      }
    })();
    return () => { active = false; };
  }, []);

  function f(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      setForm((prev) => ({ ...prev, [key]: e.target.value }));
    };
  }

  async function saveCell() {
    setSaving(true);
    setError(null);
    try {
      await api.library.createCell({
        manufacturer: form.manufacturer,
        model: form.model,
        chemistry: form.chemistry,
        form_factor: form.form_factor,
        nominal_voltage_v: +form.nominal_voltage_v,
        nominal_capacity_ah: +form.nominal_capacity_ah,
        min_voltage_v: form.min_voltage_v ? +form.min_voltage_v : undefined,
        max_voltage_v: form.max_voltage_v ? +form.max_voltage_v : undefined,
        internal_resistance_ohm: form.internal_resistance_ohm ? +form.internal_resistance_ohm : undefined,
        max_continuous_discharge_a: form.max_continuous_discharge_a ? +form.max_continuous_discharge_a : undefined,
        mass_kg: form.mass_kg ? +form.mass_kg : undefined,
        unit_cost_usd: form.unit_cost_usd ? +form.unit_cost_usd : undefined,
        datasheet_url: form.datasheet_url || undefined,
        source_notes: form.source_notes || undefined,
      });
      setShowForm(false);
      const fresh = await api.library.cells();
      setCells(fresh);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function confirmDeleteCell() {
    if (!cellToDelete) return;
    const { id } = cellToDelete;
    setDeletingCellId(id);
    try {
      await api.library.deleteCell(id, selectedReplacementId ?? undefined);
      setCells((prev) => prev.filter((c) => c.id !== id));
      setCellToDelete(null);
      setSelectedReplacementId(null);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeletingCellId(null);
    }
  }

  function promptDeleteCell(id: number, name: string) {
    setCellToDelete({ id, name });
    const alternatives = cells.filter((c) => c.id !== id);
    setSelectedReplacementId(alternatives.length > 0 ? alternatives[0].id : null);
  }

  const filtered = cells.filter((c) => {
    const matchesSearch = `${c.manufacturer} ${c.model} ${c.chemistry}`.toLowerCase().includes(search.toLowerCase());
    const matchesChem = selectedChemistry === "ALL" || c.chemistry.toUpperCase() === selectedChemistry.toUpperCase();
    return matchesSearch && matchesChem;
  });

  return (
    <AppLayout>
      <div style={{ maxWidth: 1100 }} className="fade-in">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.75rem" }}>
          <div>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.25rem" }}>Component Library</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
              Cell specifications used in design configurations. Provisional seed data is labelled.
            </p>
          </div>
          <button className="btn-primary" onClick={() => setShowForm((v) => !v)}>
            <Plus size={15} /> Add Cell
          </button>
        </div>

        {/* Disclaimer */}
        <div style={{
          display: "flex", gap: "0.625rem", alignItems: "flex-start",
          background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)",
          borderRadius: 8, padding: "0.75rem 1rem", marginBottom: "1.25rem", fontSize: "0.78rem", color: "#d97706",
        }}>
          <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          Seed cells are illustrative demo data only. Values are not verified against manufacturer datasheets.
          Add your own cells with verified specifications before making engineering decisions.
        </div>

        {/* Add form */}
        {showForm && (
          <div className="card" style={{ marginBottom: "1.25rem" }}>
            <h3 style={{ fontWeight: 600, marginBottom: "1rem" }}>Add New Cell Specification</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.875rem" }}>
              {[
                { label: "Manufacturer *", key: "manufacturer" as const, placeholder: "e.g. Panasonic" },
                { label: "Model *", key: "model" as const, placeholder: "e.g. NCR21700T" },
                { label: "Nominal Voltage (V) *", key: "nominal_voltage_v" as const, placeholder: "3.7", type: "number" },
                { label: "Nominal Capacity (Ah) *", key: "nominal_capacity_ah" as const, placeholder: "5.0", type: "number" },
                { label: "Min Voltage (V)", key: "min_voltage_v" as const, placeholder: "2.5", type: "number" },
                { label: "Max Voltage (V)", key: "max_voltage_v" as const, placeholder: "4.2", type: "number" },
                { label: "Internal Resistance (Ω)", key: "internal_resistance_ohm" as const, placeholder: "0.025", type: "number" },
                { label: "Max Cont. Discharge (A)", key: "max_continuous_discharge_a" as const, placeholder: "15", type: "number" },
                { label: "Mass (kg)", key: "mass_kg" as const, placeholder: "0.070", type: "number" },
                { label: "Unit Cost (USD)", key: "unit_cost_usd" as const, placeholder: "6.50", type: "number" },
                { label: "Datasheet URL", key: "datasheet_url" as const, placeholder: "https://…" },
              ].map((f_) => (
                <div key={f_.key} className="field">
                  <label className="label">{f_.label}</label>
                  <input className="input" style={{ fontSize: "0.85rem" }} type={f_.type ?? "text"} placeholder={f_.placeholder} value={form[f_.key]} onChange={f(f_.key)} />
                </div>
              ))}
              <div className="field">
                <label className="label">Chemistry</label>
                <select className="select" style={{ fontSize: "0.85rem" }} value={form.chemistry} onChange={f("chemistry")}>
                  {CHEMISTRIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div className="field">
                <label className="label">Form Factor</label>
                <select className="select" style={{ fontSize: "0.85rem" }} value={form.form_factor} onChange={f("form_factor")}>
                  {FORM_FACTORS.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div className="field" style={{ marginTop: "0.875rem" }}>
              <label className="label">Source Notes</label>
              <textarea className="input" rows={2} style={{ resize: "vertical", fontSize: "0.85rem" }} placeholder="Datasheet version, assumptions, verification status…" value={form.source_notes} onChange={f("source_notes")} />
            </div>
            {error && <div style={{ marginTop: "0.625rem", color: "var(--danger)", fontSize: "0.8rem" }}>{error}</div>}
            <div style={{ marginTop: "1rem", display: "flex", gap: "0.625rem" }}>
              <button className="btn-primary" onClick={saveCell} disabled={saving}>
                {saving ? "Saving…" : "Save Cell"}
              </button>
              <button className="btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </div>
        )}

        {/* Controls: Search, Chemistry Filter Pills & View Mode Switch */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
          {/* Search */}
          <div style={{ position: "relative", minWidth: 260, maxWidth: 360, flex: 1 }}>
            <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }} />
            <input className="input" style={{ paddingLeft: 32, fontSize: "0.85rem", fontFamily: "monospace" }} placeholder="SEARCH CELLS, CHEMISTRIES…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>

          {/* Chemistry filter pills */}
          <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", alignItems: "center" }}>
            {["ALL", "NMC", "LFP", "NCA", "LTO"].map((chem) => (
              <button
                key={chem}
                onClick={() => setSelectedChemistry(chem)}
                style={{
                  padding: "0.3rem 0.65rem",
                  borderRadius: 6,
                  fontSize: "0.72rem",
                  fontFamily: "monospace",
                  fontWeight: 700,
                  cursor: "pointer",
                  border: `1px solid ${selectedChemistry === chem ? "var(--arc-cyan)" : "rgba(0, 240, 255, 0.18)"}`,
                  background: selectedChemistry === chem ? "rgba(0, 240, 255, 0.16)" : "rgba(6, 13, 26, 0.6)",
                  color: selectedChemistry === chem ? "var(--arc-cyan)" : "var(--text-secondary)",
                  transition: "all 0.18s ease",
                  boxShadow: selectedChemistry === chem ? "0 0 10px rgba(0, 240, 255, 0.25)" : "none",
                }}
              >
                {chem}
              </button>
            ))}
          </div>

          {/* View mode toggle */}
          <div style={{ display: "flex", background: "rgba(6, 13, 26, 0.8)", border: "1px solid rgba(0, 240, 255, 0.2)", borderRadius: 6, padding: "2px" }}>
            <button
              onClick={() => setViewMode("grid")}
              style={{
                display: "flex", alignItems: "center", gap: "0.3rem",
                padding: "0.3rem 0.6rem", borderRadius: 4, border: "none", cursor: "pointer",
                background: viewMode === "grid" ? "rgba(0, 240, 255, 0.2)" : "transparent",
                color: viewMode === "grid" ? "var(--arc-cyan)" : "var(--text-muted)",
                fontSize: "0.75rem", fontWeight: 700, fontFamily: "monospace",
              }}
              title="Grid Card View"
            >
              <LayoutGrid size={13} /> CARDS
            </button>
            <button
              onClick={() => setViewMode("table")}
              style={{
                display: "flex", alignItems: "center", gap: "0.3rem",
                padding: "0.3rem 0.6rem", borderRadius: 4, border: "none", cursor: "pointer",
                background: viewMode === "table" ? "rgba(0, 240, 255, 0.2)" : "transparent",
                color: viewMode === "table" ? "var(--arc-cyan)" : "var(--text-muted)",
                fontSize: "0.75rem", fontWeight: 700, fontFamily: "monospace",
              }}
              title="Engineering Data Table View"
            >
              <TableIcon size={13} /> TABLE
            </button>
          </div>
        </div>

        {/* Content View: Grid or Table */}
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "30vh", color: "var(--arc-cyan)" }}>
            <div className="spinner" style={{ width: 32, height: 32 }} />
          </div>
        ) : viewMode === "grid" ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1rem" }}>
            {filtered.map((c) => (
              <BatteryCellCard
                key={c.id}
                manufacturer={c.manufacturer}
                model={c.model}
                chemistry={c.chemistry}
                formFactor={c.form_factor}
                nominalVoltageV={c.nominal_voltage_v}
                capacityAh={c.nominal_capacity_ah}
                internalResistanceOhm={c.internal_resistance_ohm}
                maxContinuousA={c.max_continuous_discharge_a}
                massKg={c.mass_kg}
                isSeed={c.is_seed}
                onDelete={() => promptDeleteCell(c.id, `${c.manufacturer} ${c.model}`)}
              />
            ))}
          </div>
        ) : (
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cell</th>
                  <th>Chemistry / Format</th>
                  <th>Voltage</th>
                  <th>Capacity</th>
                  <th>Int. Res.</th>
                  <th>Mass</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <Fragment key={c.id}>
                    <tr>
                      <td>
                        <div style={{ fontWeight: 600 }}>{c.model}</div>
                        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{c.manufacturer}</div>
                      </td>
                      <td>{c.chemistry} · {c.form_factor}</td>
                      <td>{c.nominal_voltage_v} V {c.min_voltage_v && c.max_voltage_v ? <span style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>({c.min_voltage_v}–{c.max_voltage_v})</span> : ""}</td>
                      <td>{c.nominal_capacity_ah} Ah</td>
                      <td>{c.internal_resistance_ohm ? `${(c.internal_resistance_ohm * 1000).toFixed(0)} mΩ` : "—"}</td>
                      <td>{c.mass_kg ? `${(c.mass_kg * 1000).toFixed(0)} g` : "—"}</td>
                      <td>
                        {c.data_status === "provisional"
                          ? <span className="badge-provisional">Provisional</span>
                          : c.data_status === "verified"
                          ? <span className="badge-pass" style={{ fontSize: "0.7rem" }}>Verified</span>
                          : <span className="badge-unverified" style={{ fontSize: "0.7rem" }}>Unknown</span>}
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: "0.375rem" }}>
                          <button
                            onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: "0.25rem" }}
                            title="Show details">
                            {expanded === c.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>
                          <button
                            className="btn-danger"
                            style={{ padding: "0.2rem 0.4rem", borderRadius: 4, cursor: "pointer" }}
                            onClick={() => promptDeleteCell(c.id, `${c.manufacturer} ${c.model}`)}
                            title="Delete cell specification"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expanded === c.id && (
                      <tr key={`${c.id}-detail`}>
                        <td colSpan={8} style={{ background: "var(--bg-surface)", padding: "0.875rem 1rem" }}>
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "0.625rem", fontSize: "0.8rem" }}>
                            {[
                              { label: "Max Cont. Discharge", value: c.max_continuous_discharge_a ? `${c.max_continuous_discharge_a} A` : "—" },
                              { label: "Max Operating Temp", value: c.max_operating_temp_c ? `${c.max_operating_temp_c} °C` : "—" },
                              { label: "Unit Cost", value: c.unit_cost_usd ? `$${c.unit_cost_usd.toFixed(2)}` : "—" },
                              { label: "Seed Cell", value: c.is_seed ? "Yes" : "No" },
                            ].map((item) => (
                              <div key={item.label}>
                                <div style={{ color: "var(--text-muted)", marginBottom: "0.125rem" }}>{item.label}</div>
                                <div style={{ fontWeight: 600 }}>{item.value}</div>
                              </div>
                            ))}
                          </div>
                          {c.source_notes && (
                            <p style={{ marginTop: "0.625rem", fontSize: "0.75rem", color: "#d97706", fontStyle: "italic" }}>
                              Note: {c.source_notes}
                            </p>
                          )}
                          {c.datasheet_url && (
                            <a href={c.datasheet_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: "0.75rem", color: "var(--accent)", marginTop: "0.375rem", display: "block" }}>
                              Datasheet ↗
                            </a>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Cell Deletion Confirmation Modal ── */}
        {cellToDelete && (
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
                    Delete Cell Specification
                  </h3>
                  <span style={{ fontSize: "0.68rem", fontFamily: "monospace", color: "var(--danger)", letterSpacing: "0.05em" }}>
                    LIBRARY REMOVAL
                  </span>
                </div>
              </div>

              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: "1.25rem" }}>
                Are you sure you want to delete <strong style={{ color: "#f8fafc" }}>&ldquo;{cellToDelete.name}&rdquo;</strong> from the cell library?
              </p>

              {cells.filter((c) => c.id !== cellToDelete.id).length > 0 && (
                <div style={{
                  marginBottom: "1.25rem",
                  background: "rgba(0, 240, 255, 0.04)",
                  border: "1px solid rgba(0, 240, 255, 0.18)",
                  borderRadius: 6,
                  padding: "0.85rem",
                }}>
                  <label style={{ display: "block", fontSize: "0.72rem", fontFamily: "monospace", color: "var(--arc-cyan)", marginBottom: "0.4rem", fontWeight: 700 }}>
                    MIGRATE REFERENCED PACK CONFIGURATIONS TO:
                  </label>
                  <select
                    className="select"
                    style={{ fontSize: "0.8rem", width: "100%", marginBottom: "0.4rem" }}
                    value={selectedReplacementId ?? ""}
                    onChange={(e) => setSelectedReplacementId(e.target.value ? +e.target.value : null)}
                  >
                    <option value="">— Refuse deletion if actively referenced —</option>
                    {cells.filter((c) => c.id !== cellToDelete.id).map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.manufacturer} {r.model} ({r.chemistry} · {r.nominal_voltage_v}V · {r.nominal_capacity_ah}Ah)
                      </option>
                    ))}
                  </select>
                  <p style={{ fontSize: "0.68rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.4 }}>
                    Silent reassignment is prevented. If referenced, pack configurations will be explicitly updated to your chosen replacement cell. Historical simulation runs retain their execution snapshot.
                  </p>
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                <button
                  className="btn-secondary"
                  onClick={() => setCellToDelete(null)}
                  disabled={deletingCellId !== null}
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
                  disabled={deletingCellId !== null}
                  onClick={confirmDeleteCell}
                >
                  <Trash2 size={14} />
                  {deletingCellId === cellToDelete.id ? "Deleting…" : "Confirm Delete"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
