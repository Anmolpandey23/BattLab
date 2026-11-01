"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ProjectSummary } from "@/lib/api";
import {
  Plus, Search, FolderOpen, Clock, Zap, AlertTriangle,
  CheckCircle, Trash2, ExternalLink, Activity, Orbit, Layers
} from "lucide-react";

function StatusBadge({ status }: { status?: string }) {
  if (!status) return <span className="badge-unverified">NOT INITIALIZED</span>;
  if (status === "completed") return <span className="badge-pass"><CheckCircle size={10} /> SOLVED</span>;
  if (status === "failed") return <span className="badge-fail">FAILED</span>;
  if (status === "running") return <span className="badge-warn">SOLVING</span>;
  return <span className="badge-unverified">{status.toUpperCase()}</span>;
}

export default function Dashboard() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [projectToDelete, setProjectToDelete] = useState<{ id: number; name: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await api.projects.list();
        if (active) {
          setProjects(data);
          setLoading(false);
        }
      } catch (e: unknown) {
        if (active) {
          setError(e instanceof Error ? e.message : "Failed to load projects. Is the backend running?");
          setLoading(false);
        }
      }
    })();
    return () => { active = false; };
  }, []);

  async function confirmDecommission() {
    if (!projectToDelete) return;
    const { id } = projectToDelete;
    setDeleting(id);
    try {
      await api.projects.delete(id);
      setProjects((p) => p.filter((x) => x.id !== id));
      setProjectToDelete(null);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(null);
    }
  }

  const filtered = projects.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.application_category.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fade-in" style={{ maxWidth: 1200, margin: "0 auto" }}>
      {/* ── Top Header ── */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "2rem" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
            <Activity size={20} color="var(--arc-cyan)" />
            <h1 style={{ fontSize: "1.65rem", fontWeight: 800, letterSpacing: "-0.02em" }}>
              Battery Pack Engineering Projects
            </h1>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", fontFamily: "monospace" }}>
            ACTIVE PACK ARCHITECTURES // BATTLAB SUITE
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <Link href="/projects/new" style={{ textDecoration: "none" }}>
            <button className="btn-primary">
              <Plus size={16} /> + New Battery Architecture
            </button>
          </Link>
        </div>
      </div>

      {/* ── Battery Architecture Telemetry Overview Bar ── */}
      <div
        className="battery-gradient-border"
        style={{
          borderRadius: 10,
          padding: "1rem 1.5rem",
          marginBottom: "1.75rem",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "1.25rem",
          background: "rgba(6, 14, 28, 0.75)",
          backdropFilter: "blur(16px)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: "rgba(0, 240, 255, 0.12)", border: "1px solid rgba(0, 240, 255, 0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Layers size={18} color="var(--arc-cyan)" />
          </div>
          <div>
            <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "monospace" }}>ARCHITECTURES</div>
            <div style={{ fontSize: "1.15rem", fontWeight: 800, fontFamily: "monospace", color: "#f8fafc" }}>
              {projects.length} ACTIVE PACKS
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: "rgba(16, 185, 129, 0.12)", border: "1px solid rgba(16, 185, 129, 0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Zap size={18} color="#10b981" />
          </div>
          <div>
            <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "monospace" }}>CHEMISTRY SCOPE</div>
            <div style={{ fontSize: "0.85rem", fontWeight: 700, fontFamily: "monospace", color: "#34d399" }}>
              NMC · LFP · NCA · LTO
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: "rgba(245, 158, 11, 0.12)", border: "1px solid rgba(245, 158, 11, 0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Orbit size={18} color="#f59e0b" />
          </div>
          <div>
            <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "monospace" }}>3D CAD &amp; SOLVER</div>
            <div style={{ fontSize: "0.85rem", fontWeight: 700, fontFamily: "monospace", color: "#fbbf24" }}>
              ELECTRO-THERMAL
            </div>
          </div>
        </div>
      </div>

      {/* ── Search Bar ── */}
      <div style={{ position: "relative", marginBottom: "1.75rem", maxWidth: 400 }}>
        <Search size={16} style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--arc-cyan)" }} />
        <input
          className="input"
          style={{ paddingLeft: 40, fontFamily: "monospace", fontSize: "0.85rem" }}
          placeholder="SEARCH BLUEPRINTS OR VEHICLE CLASS…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Error state */}
      {error && (
        <div style={{
          background: "rgba(255,42,95,0.08)", border: "1px solid rgba(255,42,95,0.4)",
          borderRadius: 8, padding: "1rem 1.25rem", marginBottom: "1.5rem",
          color: "var(--danger)", fontSize: "0.875rem",
        }}>
          ⚠ {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "40vh", gap: "1rem", color: "var(--arc-cyan)" }}>
          <div className="spinner" style={{ width: 32, height: 32 }} />
          <span style={{ fontFamily: "monospace" }}>SCANNING RIG MATRICES…</span>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && filtered.length === 0 && (
        <div style={{
          textAlign: "center", padding: "4rem 2rem",
          border: "2px dashed var(--border)", borderRadius: 12,
          background: "rgba(5, 12, 26, 0.4)",
        }}>
          <FolderOpen size={48} color="var(--arc-cyan)" style={{ margin: "0 auto 1rem", opacity: 0.7 }} />
          <h3 style={{ fontWeight: 700, marginBottom: "0.5rem", color: "#e6f7ff" }}>
            {search ? "No projects match query" : "No battery systems in database"}
          </h3>
          <p style={{ color: "var(--text-secondary)", marginBottom: "1.5rem", fontSize: "0.875rem" }}>
            {search ? "Modify search filters." : "Create your first battery pack project to begin modeling."}
          </p>
          {!search && (
            <Link href="/projects/new" style={{ textDecoration: "none" }}>
              <button className="btn-primary"><Plus size={16} /> + Create Battery Project</button>
            </Link>
          )}
        </div>
      )}

      {/* Project grid */}
      {!loading && filtered.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: "1.25rem" }}>
          {filtered.map((p) => (
            <div key={p.id} className="card hud-bracket">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.875rem" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                    {p.is_demo && (
                      <span className="badge-provisional">DEMO SPEC</span>
                    )}
                    <h3 style={{ fontWeight: 700, fontSize: "1.05rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#e6f7ff" }}>
                      {p.name}
                    </h3>
                  </div>
                  <p style={{ fontSize: "0.75rem", color: "var(--arc-cyan)", fontFamily: "monospace" }}>
                    {p.application_category.toUpperCase()} · v{p.design_version}
                  </p>
                </div>
                <button
                  className="btn-danger"
                  style={{ padding: "0.35rem 0.55rem", fontSize: "0.75rem", marginLeft: "0.5rem", borderRadius: 6, cursor: "pointer" }}
                  disabled={deleting === p.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    setProjectToDelete({ id: p.id, name: p.name });
                  }}
                  title="Decommission project"
                >
                  <Trash2 size={13} />
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.625rem", marginBottom: "1rem" }}>
                <MetricChip
                  label="CONFIGS"
                  value={p.configuration_count}
                  icon={<Zap size={11} color="var(--arc-cyan)" />}
                />
                <MetricChip
                  label="STATUS"
                  value={<StatusBadge status={p.latest_sim_status} />}
                />
                <MetricChip
                  label="CHECKS"
                  value={p.warning_count > 0 ? `${p.warning_count} WARN` : "PASS"}
                  color={p.warning_count > 0 ? "var(--warning)" : "var(--success)"}
                  icon={p.warning_count > 0 ? <AlertTriangle size={11} /> : <CheckCircle size={11} />}
                />
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "1rem", fontFamily: "monospace" }}>
                <Clock size={12} />
                TELEMETRY SYNC: {new Date(p.updated_at).toLocaleDateString()}
              </div>

              <div style={{ display: "flex", gap: "0.625rem" }}>
                <Link href={`/projects/${p.id}`} style={{ textDecoration: "none", flex: 1 }}>
                  <button className="btn-secondary" style={{ width: "100%", justifyContent: "center", fontSize: "0.78rem" }}>
                    <ExternalLink size={13} /> Overview
                  </button>
                </Link>
                <Link href={`/projects/${p.id}/design`} style={{ textDecoration: "none", flex: 1 }}>
                  <button className="btn-primary" style={{ width: "100%", justifyContent: "center", fontSize: "0.78rem" }}>
                    <Orbit size={13} /> 3D Holotable
                  </button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Decommission Confirmation Modal ── */}
      {projectToDelete && (
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
              Are you sure you want to decommission <strong style={{ color: "#f8fafc" }}>&ldquo;{projectToDelete.name}&rdquo;</strong>?
              All associated cell topologies, multi-physics simulations, and engineering validation reports will be permanently purged.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
              <button
                className="btn-secondary"
                onClick={() => setProjectToDelete(null)}
                disabled={deleting !== null}
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
                disabled={deleting !== null}
                onClick={confirmDecommission}
              >
                <Trash2 size={14} />
                {deleting === projectToDelete.id ? "Decommissioning…" : "Confirm Decommission"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricChip({ label, value, icon, color }: { label: string; value: React.ReactNode; icon?: React.ReactNode; color?: string }) {
  return (
    <div style={{
      background: "rgba(4, 10, 24, 0.7)", borderRadius: 6, padding: "0.5rem 0.65rem",
      border: "1px solid var(--border-subtle)", fontFamily: "monospace",
    }}>
      <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginBottom: "0.2rem" }}>{label}</div>
      <div style={{
        fontSize: "0.8rem", fontWeight: 700,
        color: color ?? "var(--text-primary)",
        display: "flex", alignItems: "center", gap: "0.25rem",
      }}>
        {icon}{value}
      </div>
    </div>
  );
}
