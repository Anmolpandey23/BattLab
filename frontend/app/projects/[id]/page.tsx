"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, Project, Configuration, Requirement, SimulationMeta } from "@/lib/api";
import {
  Zap, GitCompare, FileDown, CheckCircle, XCircle, Orbit, Trash2, Sliders
} from "lucide-react";

export default function ProjectOverview({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = +id;
  const router = useRouter();

  const [project, setProject] = useState<Project | null>(null);
  const [configs, setConfigs] = useState<Configuration[]>([]);
  const [reqs, setReqs] = useState<Requirement[]>([]);
  const [runs, setRuns] = useState<SimulationMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [configToDelete, setConfigToDelete] = useState<{ id: number; label: string } | null>(null);
  const [deletingConfigId, setDeletingConfigId] = useState<number | null>(null);
  const [showDecommissionModal, setShowDecommissionModal] = useState(false);
  const [decommissioning, setDecommissioning] = useState(false);

  const [showReqModal, setShowReqModal] = useState(false);
  const [targetVoltage, setTargetVoltage] = useState("");
  const [targetEnergy, setTargetEnergy] = useState("");
  const [contCurrent, setContCurrent] = useState("");
  const [maxMass, setMaxMass] = useState("");
  const [maxCost, setMaxCost] = useState("");
  const [coolingPref, setCoolingPref] = useState("passive");
  const [savingReq, setSavingReq] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [proj, cfgData, reqData, simData] = await Promise.all([
          api.projects.get(projectId),
          api.projects.configurations.list(projectId),
          api.projects.requirements.list(projectId),
          api.projects.simulations(projectId),
        ]);
        if (active) {
          setProject(proj);
          setConfigs(cfgData);
          setReqs(reqData);
          setRuns(simData);
          setLoading(false);
        }
      } catch (e: unknown) {
        if (active) {
          setError(e instanceof Error ? e.message : "Failed to load project telemetry");
          setLoading(false);
        }
      }
    })();
    return () => { active = false; };
  }, [projectId]);

  async function confirmDeleteConfig() {
    if (!configToDelete) return;
    const { id } = configToDelete;
    setDeletingConfigId(id);
    try {
      await api.projects.configurations.delete(projectId, id);
      setConfigs((prev) => prev.filter((c) => c.id !== id));
      setConfigToDelete(null);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to delete configuration");
    } finally {
      setDeletingConfigId(null);
    }
  }

  async function confirmDecommissionProject() {
    setDecommissioning(true);
    try {
      await api.projects.delete(projectId);
      router.push("/dashboard");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to decommission project");
      setDecommissioning(false);
    }
  }

  function openReqModal() {
    if (reqs[0]) {
      const r = reqs[0];
      setTargetVoltage(r.target_voltage_v != null ? String(r.target_voltage_v) : "");
      setTargetEnergy(r.target_energy_wh != null ? String(r.target_energy_wh) : "");
      setContCurrent(r.continuous_current_a != null ? String(r.continuous_current_a) : "");
      setMaxMass(r.max_mass_kg != null ? String(r.max_mass_kg) : "");
      setMaxCost(r.max_cost_usd != null ? String(r.max_cost_usd) : "");
      setCoolingPref(r.cooling_preference || "passive");
    } else {
      const cfg = configs[0];
      setTargetVoltage(cfg?.calc_nominal_voltage_v ? String(Math.round(cfg.calc_nominal_voltage_v)) : "52");
      setTargetEnergy(cfg?.calc_nominal_energy_wh ? String(Math.round(cfg.calc_nominal_energy_wh)) : "2000");
      setContCurrent("40");
      setMaxMass("10");
      setMaxCost("600");
      setCoolingPref(cfg?.cooling_type || "passive");
    }
    setShowReqModal(true);
  }

  async function handleSaveRequirements(e: React.FormEvent) {
    e.preventDefault();
    setSavingReq(true);
    try {
      const saved = await api.projects.requirements.create(projectId, {
        target_voltage_v: targetVoltage ? parseFloat(targetVoltage) : undefined,
        target_energy_wh: targetEnergy ? parseFloat(targetEnergy) : undefined,
        continuous_current_a: contCurrent ? parseFloat(contCurrent) : undefined,
        max_mass_kg: maxMass ? parseFloat(maxMass) : undefined,
        max_cost_usd: maxCost ? parseFloat(maxCost) : undefined,
        cooling_preference: coolingPref,
      });
      setReqs([saved, ...reqs]);
      setShowReqModal(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to save requirements");
    } finally {
      setSavingReq(false);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "50vh", gap: "1rem", color: "var(--arc-cyan)" }}>
        <div className="spinner" style={{ width: 32, height: 32 }} />
        <span style={{ fontFamily: "monospace" }}>SYNCHRONIZING PROJECT TELEMETRY…</span>
      </div>
    );
  }

  if (error) {
    return <div style={{ color: "var(--danger)", padding: "2rem" }}>⚠ {error}</div>;
  }

  const req = reqs[0];
  const completedRuns = runs.filter((r) => r.status === "completed");

  const NAV_ACTIONS = [
    { href: `/projects/${projectId}/design`, label: "3D Pack Studio", icon: Orbit, color: "var(--arc-cyan)", desc: "Interact, explode & configure 3D pack" },
    { href: `/projects/${projectId}/simulation`, label: "Launch Simulation", icon: Zap, color: "#10b981", desc: "Run multi-physics electrical & thermal solver" },
    { href: `/projects/${projectId}/compare`, label: "Compare Architectures", icon: GitCompare, color: "var(--accent-gold)", desc: "Side-by-side Pareto analysis" },
    { href: `/projects/${projectId}/report`, label: "Engineering Reports", icon: FileDown, color: "#a855f7", desc: "Download PDF / CSV / JSON telemetry" },
  ];

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }} className="fade-in">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "2rem" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", marginBottom: "0.375rem" }}>
            {project?.is_demo && (
              <span className="badge-provisional">DEMO SPEC</span>
            )}
            <h1 style={{ fontSize: "1.75rem", fontWeight: 800, letterSpacing: "-0.02em" }}>{project?.name}</h1>
          </div>
          <p style={{ color: "var(--arc-cyan)", fontSize: "0.85rem", fontFamily: "monospace" }}>
            {project?.application_category.toUpperCase()} · v{project?.design_version}
            {project?.engineer_label && ` · CHIEF ENGINEER: ${project.engineer_label.toUpperCase()}`}
          </p>
          {project?.description && (
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.5rem", maxWidth: 640 }}>
              {project.description}
            </p>
          )}
        </div>
        <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
          <button
            className="btn-danger"
            onClick={() => setShowDecommissionModal(true)}
            style={{ fontSize: "0.8rem", padding: "0.45rem 0.85rem", display: "flex", alignItems: "center", gap: "0.4rem" }}
            title="Permanently decommission and delete this project"
          >
            <Trash2 size={13} /> Decommission Project
          </button>
          <Link href="/dashboard" style={{ textDecoration: "none" }}>
            <button className="btn-secondary" style={{ fontSize: "0.8rem" }}>← Return to Dashboard</button>
          </Link>
        </div>
      </div>

      {/* Quick Actions Action Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
        {NAV_ACTIONS.map((a) => (
          <Link key={a.href} href={a.href} style={{ textDecoration: "none" }}>
            <div className="card hud-bracket" style={{ padding: "1.25rem", cursor: "pointer", height: "100%" }}>
              <div style={{
                width: 42, height: 42, borderRadius: 8, marginBottom: "0.875rem",
                background: "rgba(0, 240, 255, 0.08)", border: `1px solid ${a.color}40`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <a.icon size={20} color={a.color} />
              </div>
              <div style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: "0.35rem", color: "#e6f7ff" }}>{a.label}</div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>{a.desc}</div>
            </div>
          </Link>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
        {/* Requirements */}
        <div className="card hud-bracket">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <p className="section-title" style={{ margin: 0 }}>Design Constraints & Targets</p>
            <button
              onClick={openReqModal}
              style={{
                background: "rgba(0, 240, 255, 0.1)",
                border: "1px solid var(--border)",
                borderRadius: 4,
                padding: "0.25rem 0.6rem",
                color: "var(--arc-cyan)",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              <Sliders size={12} /> {req ? "Edit Targets" : "+ Set Targets"}
            </button>
          </div>
          {req ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", fontSize: "0.85rem", fontFamily: "monospace" }}>
              {[
                { label: "Target Bus Voltage", value: req.target_voltage_v ? `${req.target_voltage_v} V` : "—" },
                { label: "Target Pack Energy", value: req.target_energy_wh ? `${req.target_energy_wh} Wh` : "—" },
                { label: "Continuous Current", value: req.continuous_current_a ? `${req.continuous_current_a} A` : "—" },
                { label: "Mass Envelope", value: req.max_mass_kg ? `${req.max_mass_kg} kg` : "—" },
                { label: "BOM Budget Cap", value: req.max_cost_usd ? `$${req.max_cost_usd}` : "—" },
                { label: "Thermal Range", value: (req.min_ambient_temp_c != null && req.max_ambient_temp_c != null) ? `${req.min_ambient_temp_c}°C to ${req.max_ambient_temp_c}°C` : "—" },
                { label: "Cooling Architecture", value: req.cooling_preference.toUpperCase() },
              ].map((row) => (
                <div key={row.label} style={{ display: "flex", justifyContent: "space-between", gap: "1rem", borderBottom: "1px solid rgba(0,240,255,0.06)", paddingBottom: 4 }}>
                  <span style={{ color: "var(--text-muted)" }}>{row.label}</span>
                  <span style={{ fontWeight: 700, color: "var(--text-primary)" }}>{row.value}</span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: "0.5rem 0" }}>
              <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", lineHeight: 1.5, marginBottom: "0.85rem" }}>
                No constraints defined yet. Add voltage, energy, current, and mass targets to enable automatic constraint verification and pass/fail audits.
              </p>
              <button
                onClick={openReqModal}
                className="btn-primary"
                style={{ fontSize: "0.78rem", padding: "0.4rem 0.85rem", display: "inline-flex", alignItems: "center", gap: "0.4rem" }}
              >
                <Sliders size={13} /> + Set Engineering Targets
              </button>
            </div>
          )}
        </div>

        {/* Configurations */}
        <div className="card hud-bracket">
          <p className="section-title">Pack Configurations ({configs.length})</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {configs.length === 0 ? (
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>No configurations yet.</p>
            ) : (
              configs.map((c) => (
                <div key={c.id} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "0.75rem", borderRadius: 6, background: "rgba(4, 10, 24, 0.7)",
                  border: `1px solid ${c.is_baseline ? "var(--border-glow)" : "var(--border-subtle)"}`,
                }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.875rem", display: "flex", alignItems: "center", gap: "0.375rem" }}>
                      {c.is_baseline && <span style={{ fontSize: "0.65rem", color: "var(--success)" }}>● BASELINE</span>}
                      {c.label}
                    </div>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontFamily: "monospace", marginTop: 2 }}>
                      {c.ns}S×{c.np}P · {c.cooling_type.toUpperCase()}
                      {c.calc_nominal_voltage_v && ` · ${c.calc_nominal_voltage_v.toFixed(1)} V`}
                      {c.calc_nominal_energy_wh && ` · ${c.calc_nominal_energy_wh.toFixed(0)} Wh`}
                      {c.calc_total_cells && ` · ${c.calc_total_cells} cells`}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "0.45rem", alignItems: "center" }}>
                    <Link href={`/projects/${projectId}/design`} style={{ textDecoration: "none" }}>
                      <button style={{
                        background: "rgba(0, 240, 255, 0.1)", border: "1px solid var(--border)", borderRadius: 4,
                        padding: "0.3rem 0.65rem", cursor: "pointer", fontSize: "0.72rem",
                        color: "var(--arc-cyan)", fontWeight: 700, whiteSpace: "nowrap",
                      }}>Open 3D →</button>
                    </Link>
                    <button
                      className="btn-danger"
                      style={{ padding: "0.3rem 0.5rem", borderRadius: 4, cursor: "pointer" }}
                      onClick={() => setConfigToDelete({ id: c.id, label: c.label })}
                      title="Delete pack configuration"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Simulation History */}
        <div className="card hud-bracket" style={{ gridColumn: "1 / -1" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.875rem" }}>
            <p className="section-title" style={{ margin: 0 }}>Simulation Run Telemetry Log ({runs.length})</p>
            {completedRuns.length >= 2 && (
              <Link href={`/projects/${projectId}/compare`} style={{ textDecoration: "none" }}>
                <button className="btn-secondary" style={{ fontSize: "0.78rem", padding: "0.35rem 0.75rem" }}>
                  <GitCompare size={13} /> Compare
                </button>
              </Link>
            )}
          </div>
          {runs.length === 0 ? (
            <div style={{ textAlign: "center", padding: "2.5rem", color: "var(--text-muted)" }}>
              <Zap size={36} style={{ margin: "0 auto 0.75rem", display: "block", color: "var(--arc-cyan)", opacity: 0.5 }} />
              <p style={{ fontSize: "0.875rem" }}>No simulation runs logged yet.</p>
              <Link href={`/projects/${projectId}/simulation`} style={{ textDecoration: "none" }}>
                <button className="btn-primary" style={{ marginTop: "1rem", fontSize: "0.85rem" }}>
                  <Zap size={14} /> Launch First Simulation
                </button>
              </Link>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run Label</th>
                  <th>Status</th>
                  <th>Voltage</th>
                  <th>Energy</th>
                  <th>Peak Temp</th>
                  <th>Gating</th>
                  <th>Timestamp</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {[...runs].sort((a, b) => b.id - a.id).map((r) => (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 600, fontFamily: "monospace" }}>{r.run_label ?? `Run #${r.id}`}</td>
                    <td>
                      {r.status === "completed" ? <span className="badge-pass"><CheckCircle size={10} /> SOLVED</span>
                        : r.status === "failed" ? <span className="badge-fail"><XCircle size={10} /> FAILED</span>
                        : r.status === "running" ? <span className="badge-warn">SOLVING</span>
                        : <span className="badge-unverified">{r.status}</span>}
                    </td>
                    <td style={{ fontFamily: "monospace" }}>{r.result_nominal_voltage_v?.toFixed(1) ?? "—"} {r.result_nominal_voltage_v ? "V" : ""}</td>
                    <td style={{ fontFamily: "monospace" }}>{r.result_nominal_energy_wh?.toFixed(0) ?? "—"} {r.result_nominal_energy_wh ? "Wh" : ""}</td>
                    <td style={{ fontFamily: "monospace" }}>{r.result_max_temp_c?.toFixed(1) ?? "—"} {r.result_max_temp_c ? "°C" : ""}</td>
                    <td>
                      <div style={{ display: "flex", gap: "0.3rem", alignItems: "center" }}>
                        {r.constraint_fail > 0 && <span className="badge-fail" style={{ fontSize: "0.68rem" }}>{r.constraint_fail} FAIL</span>}
                        {r.constraint_warning > 0 && <span className="badge-warn" style={{ fontSize: "0.68rem" }}>{r.constraint_warning} WARN</span>}
                        {r.constraint_fail === 0 && r.constraint_warning === 0 && r.status === "completed" && (
                          <span className="badge-pass" style={{ fontSize: "0.68rem" }}><CheckCircle size={9} /> PASS</span>
                        )}
                      </div>
                    </td>
                    <td style={{ color: "var(--text-muted)", fontSize: "0.78rem", fontFamily: "monospace" }}>
                      {new Date(r.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      {r.status === "completed" && (
                        <Link href={`/projects/${projectId}/results/${r.id}`} style={{ textDecoration: "none" }}>
                          <button style={{
                            background: "rgba(0, 240, 255, 0.1)", border: "1px solid var(--border)", borderRadius: 4,
                            padding: "0.25rem 0.6rem", cursor: "pointer", fontSize: "0.72rem",
                            color: "var(--arc-cyan)", fontWeight: 700, whiteSpace: "nowrap",
                          }}>View 3D Results →</button>
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
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
                  Delete Configuration
                </h3>
                <span style={{ fontSize: "0.68rem", fontFamily: "monospace", color: "var(--danger)", letterSpacing: "0.05em" }}>
                  IRREVERSIBLE ACTION
                </span>
              </div>
            </div>

            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: "1.5rem" }}>
              Are you sure you want to delete pack configuration <strong style={{ color: "#f8fafc" }}>&ldquo;{configToDelete.label}&rdquo;</strong>?
              Associated simulation runs and constraint checks for this configuration will also be removed.
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

      {/* ── Decommission Project Confirmation Modal ── */}
      {showDecommissionModal && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 100,
          background: "rgba(3, 7, 18, 0.8)", backdropFilter: "blur(8px)",
          display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem",
        }}>
          <div
            className="card hud-bracket"
            style={{
              maxWidth: 460, width: "100%", background: "rgba(6, 14, 28, 0.98)",
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
                  Decommission Project
                </h3>
                <span style={{ fontSize: "0.68rem", fontFamily: "monospace", color: "var(--danger)", letterSpacing: "0.05em" }}>
                  IRREVERSIBLE ACTION
                </span>
              </div>
            </div>

            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: "1.5rem" }}>
              Are you sure you want to decommission <strong style={{ color: "#f8fafc" }}>&ldquo;{project?.name}&rdquo;</strong>?
              All associated cell topologies, multi-physics simulations, and engineering validation reports will be permanently purged.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
              <button
                className="btn-secondary"
                onClick={() => setShowDecommissionModal(false)}
                disabled={decommissioning}
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
                disabled={decommissioning}
                onClick={confirmDecommissionProject}
              >
                <Trash2 size={14} />
                {decommissioning ? "Decommissioning…" : "Confirm Decommission"}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* ── Engineering Requirements & Constraints Modal ── */}
      {showReqModal && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 100,
          background: "rgba(3, 7, 18, 0.8)", backdropFilter: "blur(8px)",
          display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem",
        }}>
          <div
            className="card hud-bracket"
            style={{
              maxWidth: 520, width: "100%", background: "rgba(6, 14, 28, 0.98)",
              border: "1px solid var(--border-glow)",
              boxShadow: "0 24px 64px rgba(0, 0, 0, 0.9), 0 0 32px rgba(0, 240, 255, 0.15)",
              padding: "1.75rem", borderRadius: 10,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.85rem", marginBottom: "1.25rem" }}>
              <div style={{
                width: 40, height: 40, borderRadius: 8,
                background: "rgba(0, 240, 255, 0.12)", border: "1px solid var(--border)",
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}>
                <Sliders size={20} color="var(--arc-cyan)" />
              </div>
              <div>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, color: "#f8fafc" }}>
                  Design Constraints & Engineering Targets
                </h3>
                <span style={{ fontSize: "0.68rem", fontFamily: "monospace", color: "var(--arc-cyan)", letterSpacing: "0.05em" }}>
                  AUTOMATIC PASS / FAIL VERIFICATION GATES
                </span>
              </div>
            </div>

            <form onSubmit={handleSaveRequirements}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.85rem", marginBottom: "1.25rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 4 }}>
                    Target Bus Voltage (V)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="e.g. 52.0"
                    value={targetVoltage}
                    onChange={(e) => setTargetVoltage(e.target.value)}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--border)", color: "#fff", fontSize: "0.85rem", fontFamily: "monospace" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 4 }}>
                    Target Energy (Wh)
                  </label>
                  <input
                    type="number"
                    step="1"
                    placeholder="e.g. 2000"
                    value={targetEnergy}
                    onChange={(e) => setTargetEnergy(e.target.value)}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--border)", color: "#fff", fontSize: "0.85rem", fontFamily: "monospace" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 4 }}>
                    Continuous Current (A)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    placeholder="e.g. 40.0"
                    value={contCurrent}
                    onChange={(e) => setContCurrent(e.target.value)}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--border)", color: "#fff", fontSize: "0.85rem", fontFamily: "monospace" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 4 }}>
                    Max Mass Limit (kg)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="e.g. 10.0"
                    value={maxMass}
                    onChange={(e) => setMaxMass(e.target.value)}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--border)", color: "#fff", fontSize: "0.85rem", fontFamily: "monospace" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 4 }}>
                    BOM Budget Cap ($ USD)
                  </label>
                  <input
                    type="number"
                    step="1"
                    placeholder="e.g. 600"
                    value={maxCost}
                    onChange={(e) => setMaxCost(e.target.value)}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--border)", color: "#fff", fontSize: "0.85rem", fontFamily: "monospace" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: 4 }}>
                    Cooling Architecture
                  </label>
                  <select
                    value={coolingPref}
                    onChange={(e) => setCoolingPref(e.target.value)}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 4, background: "rgba(0,0,0,0.5)", border: "1px solid var(--border)", color: "#fff", fontSize: "0.85rem" }}
                  >
                    <option value="passive">Passive Air</option>
                    <option value="fan">Forced Air / Fan</option>
                    <option value="liquid">Liquid Cold Plate</option>
                    <option value="phase_change">Phase Change (PCM)</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowReqModal(false)}
                  disabled={savingReq}
                  style={{ padding: "0.55rem 1.1rem" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  style={{ padding: "0.55rem 1.25rem", fontSize: "0.825rem", fontWeight: 700 }}
                  disabled={savingReq}
                >
                  {savingReq ? "Saving…" : "Save Requirements"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
