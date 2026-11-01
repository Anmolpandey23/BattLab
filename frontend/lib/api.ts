// BattLab — API Client
// All communication with the FastAPI backend goes through this module.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

async function req<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${options.method ?? "GET"} ${path} → ${res.status}: ${text.slice(0, 200)}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Health ────────────────────────────────────────────────────────────────────
export const api = {
  health: () => req<{ status: string; version: string }>("/health"),

  // ── Projects ───────────────────────────────────────────────────────────────
  projects: {
    list: () => req<ProjectSummary[]>("/projects"),
    get: (id: number) => req<Project>(`/projects/${id}`),
    create: (body: ProjectCreate) =>
      req<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
    update: (id: number, body: Partial<ProjectCreate>) =>
      req<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (id: number) => req<void>(`/projects/${id}`, { method: "DELETE" }),

    requirements: {
      list: (pid: number) => req<Requirement[]>(`/projects/${pid}/requirements`),
      create: (pid: number, body: RequirementCreate) =>
        req<Requirement>(`/projects/${pid}/requirements`, {
          method: "POST",
          body: JSON.stringify(body),
        }),
    },

    configurations: {
      list: (pid: number) => req<Configuration[]>(`/projects/${pid}/configurations`),
      create: (pid: number, body: ConfigurationCreate) =>
        req<Configuration>(`/projects/${pid}/configurations`, {
          method: "POST",
          body: JSON.stringify(body),
        }),
      update: async (cfgId: number, body: Partial<ConfigurationCreate>) => {
        try {
          return await req<Configuration>(`/configurations/${cfgId}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
        } catch {
          return await req<Configuration>(`/projects/configurations/${cfgId}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          });
        }
      },
      massBreakdown: async (cfgId: number) => {
        try {
          return await req<PackMassBreakdown>(`/projects/configurations/${cfgId}/mass-breakdown`);
        } catch {
          return await req<PackMassBreakdown>(`/configurations/${cfgId}/mass-breakdown`);
        }
      },
      delete: (pid: number, cfgId: number) =>
        req<void>(`/projects/${pid}/configurations/${cfgId}`, { method: "DELETE" }),
    },

    candidates: (pid: number, body: CandidateRequest) =>
      req<CandidateSummary[]>(`/projects/${pid}/candidates`, {
        method: "POST",
        body: JSON.stringify(body),
      }),

    simulations: (pid: number) =>
      req<SimulationMeta[]>(`/projects/${pid}/simulations`),

    compare: (pid: number, body: CompareRequest) =>
      req<CompareResult>(`/projects/${pid}/compare`, {
        method: "POST",
        body: JSON.stringify(body),
      }),

    report: (pid: number, body: { format: string; simulation_run_id: number }) =>
      req<{ report_id: number; filename: string }>(`/projects/${pid}/reports`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  // ── Library ────────────────────────────────────────────────────────────────
  library: {
    cells: () => req<CellSpec[]>("/library/cells"),
    getCell: (id: number) => req<CellSpec>(`/library/cells/${id}`),
    createCell: (body: Partial<CellSpec>) =>
      req<CellSpec>("/library/cells", { method: "POST", body: JSON.stringify(body) }),
    updateCell: (id: number, body: Partial<CellSpec>) =>
      req<CellSpec>(`/library/cells/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    deleteCell: (id: number, replacementCellId?: number) =>
      req<void>(`/library/cells/${id}${replacementCellId != null ? `?replacement_cell_id=${replacementCellId}` : ""}`, { method: "DELETE" }),

    components: () => req<ComponentSpec[]>("/library/components"),
    createComponent: (body: Partial<ComponentSpec>) =>
      req<ComponentSpec>("/library/components", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  // ── Scenarios ──────────────────────────────────────────────────────────────
  scenarios: {
    list: () => req<ScenarioRead[]>("/scenarios"),
    get: (id: number) => req<ScenarioRead>(`/scenarios/${id}`),
    create: (body: ScenarioCreate) =>
      req<ScenarioRead>("/scenarios", { method: "POST", body: JSON.stringify(body) }),
    listSegments: (scenarioId: number) =>
      req<DutyCycleSegment[]>(`/scenarios/${scenarioId}/segments`),
    addSegment: (scenarioId: number, body: DutyCycleSegmentCreate) =>
      req<DutyCycleSegment>(`/scenarios/${scenarioId}/segments`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    deleteSegment: (scenarioId: number, segmentId: number) =>
      req<void>(`/scenarios/${scenarioId}/segments/${segmentId}`, { method: "DELETE" }),
  },

  // ── Vehicle Load ───────────────────────────────────────────────────────────
  vehicleLoad: {
    calculate: (body: VehicleLoadRequest) =>
      req<VehicleLoadResponse>("/vehicle-load/calculate", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    simulateDriveCycle: (body: DriveCycleRequest) =>
      req<DriveCycleResponse>("/vehicle-load/drive-cycle/simulate", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    exportDriveCycleScenario: (body: DriveCycleExportScenarioRequest) =>
      req<ScenarioRead>("/vehicle-load/drive-cycle/export-scenario", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  // ── Simulations ────────────────────────────────────────────────────────────
  simulations: {
    run: (cfgId: number, body: { configuration_id: number; scenario_id: number; run_label?: string; enable_multi_node_thermal?: boolean; is_committed?: boolean }) =>
      req<{ simulation_id: number; status: string }>(`/configurations/${cfgId}/simulate`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    get: (id: number) => req<SimulationMeta>(`/simulations/${id}`),
    results: (id: number) => req<SimulationResults>(`/simulations/${id}/results`),
    provenance: (id: number) => req<ProvenanceCatalog>(`/simulations/${id}/provenance`),
    validation: (id: number, target_metric: string = "voltage_v") =>
      req<ValidationReport>(`/simulations/${id}/validation?target_metric=${target_metric}`),
    uncertainty: (id: number, body?: { n_iterations?: number; random_seed?: number }) =>
      req<UncertaintyReport>(`/simulations/${id}/uncertainty`, {
        method: "POST",
        body: JSON.stringify(body || {}),
      }),
    validateDataset: (
      id: number,
      body: {
        csv_content: string;
        custom_mapping?: Record<string, string>;
        is_physical_laboratory_data?: boolean;
        dataset_name?: string;
        split_ratio_calibration?: number;
        split_mode?: string;
      }
    ) =>
      req<{
        dataset_report: DatasetValidationReport;
        validation_result: ExperimentalValidationResult;
      }>(`/simulations/${id}/validate-dataset`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  validation: {
    ingestCheck: (body: {
      csv_content: string;
      custom_mapping?: Record<string, string>;
      is_physical_laboratory_data?: boolean;
      dataset_name?: string;
    }) =>
      req<{
        report: DatasetValidationReport;
        record_count: number;
        sample_records: unknown[];
      }>("/validation/ingest-check", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    getPublicDatasetEvaluation: () =>
      req<{
        benchmark_id: string;
        calibrated_parameters: Record<string, number>;
        evaluations: Record<string, unknown>;
        verdicts: Record<string, string>;
        figures: string[];
        timestamp: string;
      }>("/validation/public-dataset-evaluation"),

    getDatasetManifest: () =>
      req<{
        dataset_name: string;
        authors: string;
        year: number;
        source_url: string;
        license: string;
        test_cell_specification: Record<string, unknown>;
        raw_archives: Array<{ path: string; size_bytes: number; sha256: string }>;
        canonical_csv_exports: Array<{ path: string; size_bytes: number; sha256: string }>;
        generated_at: string;
      }>("/validation/dataset-manifest"),
  },

  // ── Reports ────────────────────────────────────────────────────────────────
  reports: {
    downloadUrl: (reportId: number) => `${BASE}/reports/${reportId}/download`,
  },
};

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Project {
  id: number;
  created_at: string;
  updated_at: string;
  name: string;
  description?: string;
  application_category: string;
  engineer_label?: string;
  design_version: string;
  units: string;
  is_demo: boolean;
}

export interface ProjectSummary extends Project {
  latest_sim_status?: string;
  warning_count: number;
  configuration_count: number;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  application_category?: string;
  engineer_label?: string;
  design_version?: string;
  units?: string;
}

export interface Requirement {
  id: number;
  project_id: number;
  target_voltage_v?: number;
  target_energy_wh?: number;
  energy_is_usable: boolean;
  continuous_current_a?: number;
  peak_current_a?: number;
  peak_duration_s?: number;
  max_mass_kg?: number;
  max_cost_usd?: number;
  charge_time_h?: number;
  min_ambient_temp_c?: number;
  max_ambient_temp_c?: number;
  cooling_preference: string;
  design_notes?: string;
  hard_constraints?: string[];
}

export interface RequirementCreate {
  target_voltage_v?: number;
  target_energy_wh?: number;
  energy_is_usable?: boolean;
  continuous_current_a?: number;
  peak_current_a?: number;
  peak_duration_s?: number;
  max_mass_kg?: number;
  max_cost_usd?: number;
  charge_time_h?: number;
  min_ambient_temp_c?: number;
  max_ambient_temp_c?: number;
  cooling_preference?: string;
  design_notes?: string;
  hard_constraints?: string[];
}

export interface CellSpec {
  id: number;
  manufacturer: string;
  model: string;
  chemistry: string;
  form_factor: string;
  nominal_voltage_v: number;
  min_voltage_v?: number;
  max_voltage_v?: number;
  nominal_capacity_ah: number;
  internal_resistance_ohm?: number;
  max_continuous_discharge_a?: number;
  max_peak_discharge_a?: number;
  mass_kg?: number;
  diameter_mm?: number;
  length_mm?: number;
  specific_heat_j_per_kg_k?: number;
  thermal_conductance_w_per_k?: number;
  min_operating_temp_c?: number;
  max_operating_temp_c?: number;
  unit_cost_usd?: number;
  datasheet_url?: string;
  source_notes?: string;
  data_status: "verified" | "provisional" | "unknown";
  is_seed: boolean;
}

export interface ComponentSpec {
  id: number;
  name: string;
  component_type: string;
  manufacturer?: string;
  model?: string;
  max_voltage_v?: number;
  max_current_a?: number;
  mass_kg?: number;
  unit_cost_usd?: number;
  thermal_conductance_w_per_k?: number;
  aux_power_w?: number;
  source_notes?: string;
  data_status: string;
  is_seed: boolean;
}

export interface Configuration {
  id: number;
  project_id: number;
  label: string;
  design_mode: string;
  cell_spec_id?: number;
  ns: number;
  np: number;
  cells_per_module?: number;
  modules_in_series?: number;
  modules_in_parallel?: number;
  cooling_type: string;
  usable_soc_window: number;
  interconnect_resistance_ohm: number;
  notes?: string;
  is_baseline: boolean;
  calc_nominal_voltage_v?: number;
  calc_nominal_energy_wh?: number;
  calc_total_cells?: number;
  calc_cell_mass_kg?: number;
  calc_bom_cost_usd?: number;
  cell_spec?: CellSpec;
}

export interface ConfigurationCreate {
  label?: string;
  design_mode?: string;
  cell_spec_id?: number;
  ns: number;
  np: number;
  cells_per_module?: number;
  modules_in_series?: number;
  modules_in_parallel?: number;
  cooling_type?: string;
  usable_soc_window?: number;
  interconnect_resistance_ohm?: number;
  notes?: string;
  is_baseline?: boolean;
}

export interface CandidateRequest {
  cell_spec_id: number;
  target_voltage_v: number;
  target_energy_wh: number;
  energy_is_usable?: boolean;
  max_mass_kg?: number;
  max_cost_usd?: number;
  continuous_current_a?: number;
  max_candidates?: number;
}

export interface CandidateSummary {
  ns: number;
  np: number;
  total_cells: number;
  nominal_voltage_v: number;
  nominal_energy_wh: number;
  estimated_usable_energy_wh?: number;
  estimated_cell_mass_kg?: number;
  estimated_bom_cost_usd?: number;
  voltage_error_pct: number;
  energy_error_pct: number;
  status: "feasible" | "unverified" | "infeasible";
  pass_notes: string[];
  fail_notes: string[];
  warning_notes: string[];
}

export interface ScenarioRead {
  id: number;
  name: string;
  description?: string;
  ambient_temp_c: number;
  initial_cell_temp_c: number;
  initial_soc: number;
  duration_s: number;
  time_step_s: number;
  profile_type: string;
  capacity_variation_pct: number;
  resistance_variation_pct: number;
  resistance_multiplier: number;
  discharge_current_a?: number;
  is_seed: boolean;
}

export interface ScenarioCreate {
  name: string;
  description?: string;
  ambient_temp_c?: number;
  initial_cell_temp_c?: number;
  initial_soc?: number;
  duration_s?: number;
  time_step_s?: number;
  profile_type?: string;
  capacity_variation_pct?: number;
  resistance_variation_pct?: number;
  resistance_multiplier?: number;
  discharge_current_a?: number;
}

export interface DutyCycleSegment {
  id: number;
  scenario_id: number;
  segment_index: number;
  duration_s: number;
  profile_type: string;
  discharge_current_a?: number;
  ambient_temp_c?: number;
  notes?: string;
}

export interface DutyCycleSegmentCreate {
  segment_index?: number;
  duration_s: number;
  profile_type?: string;
  discharge_current_a?: number;
  ambient_temp_c?: number;
  notes?: string;
}

export interface VehicleLoadRequest {
  vehicle_mass_kg: number;
  payload_mass_kg?: number;
  speed_kmh?: number;
  speed_mps?: number;
  grade_pct?: number;
  cr?: number;
  cd?: number;
  frontal_area_m2?: number;
  air_density_kg_per_m3?: number;
  acceleration_mps2?: number;
  drivetrain_efficiency?: number;
  regen_efficiency?: number;
  auxiliary_power_w?: number;
  nominal_pack_voltage_v?: number;
}

export interface VehicleLoadResponse {
  total_mass_kg: number;
  speed_mps: number;
  speed_kmh: number;
  grade_rad: number;
  f_rolling_n: number;
  f_grade_n: number;
  f_aero_n: number;
  f_accel_n: number;
  f_total_n: number;
  p_mech_w: number;
  p_battery_w: number;
  battery_current_a: number;
  assumptions: string[];
}

export interface SimulationMeta {
  id: number;
  run_label?: string;
  status: "pending" | "running" | "completed" | "failed";
  model_version: string;
  created_at: string;
  completed_at?: string;
  project_id: number;
  configuration_id: number;
  scenario_id?: number;
  result_nominal_voltage_v?: number;
  result_nominal_energy_wh?: number;
  result_usable_energy_wh?: number;
  result_max_temp_c?: number;
  result_min_soc?: number;
  result_energy_delivered_wh?: number;
  constraint_pass: number;
  constraint_fail: number;
  constraint_warning: number;
  constraint_unverified: number;
}

export interface ConstraintResult {
  id: number;
  rule_id: string;
  status: "pass" | "fail" | "warning" | "unverified";
  observed_value?: number;
  threshold?: number;
  units?: string;
  explanation: string;
  source_assumption?: string;
  corrective_action?: string;
}

export interface TimeSeriesPoint {
  t_s: number;
  current_a: number;
  soc: number;
  temp_c: number;
  temp_core_c?: number;
  temp_surface_c?: number;
  temp_plate_c?: number;
  voltage_v?: number;
  power_loss_w: number;
}

export interface SimulationResults {
  simulation_run_id: number;
  configuration_id?: number;
  configuration_ns?: number;
  configuration_np?: number;
  cooling_type?: string;
  status: string;
  result_nominal_voltage_v?: number;
  result_nominal_energy_wh?: number;
  result_usable_energy_wh?: number;
  result_max_temp_c?: number;
  result_min_soc?: number;
  result_energy_delivered_wh?: number;
  result_soh_capacity_pct?: number;
  result_soh_resistance_pct?: number;
  result_throughput_ah?: number;
  result_efc?: number;
  battery_aging?: {
    run_throughput_ah: number;
    run_efc: number;
    cumulative_throughput_ah: number;
    cumulative_efc: number;
    capacity_fade_pct: number;
    cycle_fade_pct?: number;
    calendar_fade_pct?: number;
    resistance_growth_pct: number;
    soh_capacity_pct: number;
    soh_resistance_pct: number;
    actual_capacity_ah: number;
    actual_r0_ohm: number;
    projected_cycles_to_80pct: number;
    lifetime_trajectory: Array<{ cycle: number; soh_pct: number; resistance_factor: number }>;
    is_committed: boolean;
    assumptions: string[];
    limitations: string[];
  };
  multi_node_thermal?: {
    enabled: boolean;
    max_core_temp_c?: number;
    max_surface_temp_c?: number;
    max_plate_temp_c?: number;
    max_gradient_c?: number;
    energy_conservation_residual_j?: number;
    assumptions?: string[];
  };
  constraint_pass: number;
  constraint_fail: number;
  constraint_warning: number;
  constraint_unverified: number;
  constraints: ConstraintResult[];
  timeseries: TimeSeriesPoint[];
  model_version: string;
  completed_at?: string;
}

export interface CompareRequest {
  simulation_run_ids: number[];
  weights?: Record<string, number>;
}

export interface CompareResult {
  runs: Record<string, unknown>[];
  metrics_table: { metric: string; unit: string; values: Record<string, unknown> }[];
  ranking: { run_id: number; run_label: string; score: number; rank: number; rank_note: string; constraint_fail: number }[];
  weights_used: Record<string, number>;
}

export interface ProvenanceParameter {
  key: string;
  label: string;
  value: unknown;
  unit: string;
  category: "manufacturer_specified" | "laboratory_measured" | "literature_calibrated" | "user_provided" | "derived" | "assumed_provisional";
  confidence: "high" | "medium" | "low";
  source: string;
  uncertainty_pct?: number;
  dependent_models: string[];
  limitation_note?: string;
}

export interface ProvenanceCatalog {
  parameters: ProvenanceParameter[];
  summary: {
    total_parameters: number;
    high_confidence_count: number;
    medium_confidence_count: number;
    low_confidence_count: number;
    provisional_count: number;
    confidence_rating: string;
  };
}

export interface ValidationReport {
  status: string;
  dataset_name: string;
  dataset_type: string;
  is_physical_laboratory_data: boolean;
  target_metric: string;
  metrics: {
    mae: number;
    rmse: number;
    mbe: number;
    max_error: number;
    r_squared: number;
    n_samples: number;
    units: string;
  };
  disclaimer: string;
}

export interface UncertaintyDistribution {
  mean: number;
  std_dev: number;
  min: number;
  p05: number;
  p50: number;
  p95: number;
  max: number;
  baseline: number;
  spread_p95_p05: number;
}

export interface UncertaintyReport {
  status: string;
  iterations: number;
  random_seed: number;
  parameter_distributions_sampled: Record<string, string>;
  distributions: {
    nominal_energy_wh: UncertaintyDistribution;
    total_cell_mass_kg: UncertaintyDistribution;
    simulated_max_temp_c: UncertaintyDistribution;
    end_terminal_voltage_v: UncertaintyDistribution;
  };
  sensitivity_ranking: {
    parameter: string;
    target: string;
    correlation_coefficient: number;
    impact_direction: string;
  }[];
  disclaimer: string;
}

export interface PackMassComponent {
  label: string;
  mass_kg: number | null;
  status: string;
  fraction_pct: number | null;
  note: string;
}

export interface PackMassBreakdown {
  cell_count: number;
  ns: number;
  np_: number;
  cooling_type: string;
  form_factor: string;
  cell_mass_kg: number | null;
  total_cell_mass_kg: number | null;
  total_pack_mass_kg: number | null;
  cell_to_pack_mass_ratio: number | null;
  gravimetric_energy_density_cell_wh_per_kg: number | null;
  gravimetric_energy_density_pack_wh_per_kg: number | null;
  components: Record<string, PackMassComponent>;
  status: string;
  assumptions: string[];
  limitations: string[];
}

export interface DriveCycleRequest {
  cycle_type: string;
  vehicle_mass_kg: number;
  payload_mass_kg?: number;
  cr?: number;
  cd?: number;
  frontal_area_m2?: number;
  air_density_kg_per_m3?: number;
  drivetrain_efficiency?: number;
  regen_efficiency?: number;
  auxiliary_power_w?: number;
  nominal_pack_voltage_v?: number;
  road_surface?: string;
  custom_points?: number[][];
}

export interface DriveCycleExportScenarioRequest {
  project_id: number;
  cycle_type: string;
  vehicle_mass_kg: number;
  payload_mass_kg?: number;
  cr?: number;
  cd?: number;
  frontal_area_m2?: number;
  drivetrain_efficiency?: number;
  regen_efficiency?: number;
  auxiliary_power_w?: number;
  nominal_pack_voltage_v?: number;
  road_surface?: string;
  scenario_name?: string;
  ambient_temp_c?: number;
}

export interface DatasetValidationReport {
  is_valid: boolean;
  total_rows: number;
  valid_rows: number;
  errors: string[];
  warnings: string[];
  column_mapping: Record<string, string>;
  time_span_s: number;
  sample_interval_mean_s: number;
  is_physical_laboratory_data: boolean;
  dataset_classification: string;
  provenance: Record<string, unknown>;
}

export interface ErrorMoments {
  mae: number;
  rmse: number;
  mbe: number;
  max_error: number;
  r_squared: number;
  p50_error: number;
  p90_error: number;
  p99_error: number;
  n_samples: number;
  units: string;
}

export interface ExperimentalValidationResult {
  status: string;
  is_experimentally_validated: boolean;
  dataset_name: string;
  dataset_classification: string;
  target_cell_model?: string;
  voltage_metrics?: ErrorMoments;
  temperature_metrics?: ErrorMoments;
  capacity_error_pct?: number;
  energy_error_pct?: number;
  split_type: string;
  aligned_samples_count: number;
  provenance_metadata: Record<string, unknown>;
  disclaimer: string;
  blockers: string[];
}

export interface DriveCycleTimePoint {
  t_s: number;
  speed_kmh: number;
  grade_pct: number;
  f_total_n: number;
  p_mech_w: number;
  p_battery_w: number;
  current_a: number;
  distance_km: number;
}

export interface DriveCycleResponse {
  cycle_type: string;
  title: string;
  duration_s: number;
  total_distance_km: number;
  total_mass_kg: number;
  cr_used: number;
  cd_used: number;
  frontal_area_m2: number;
  nominal_bus_voltage_v: number;
  gross_energy_discharged_wh: number;
  regen_energy_recovered_wh: number;
  net_energy_consumed_wh: number;
  specific_consumption_wh_per_km: number;
  peak_traction_power_w: number;
  peak_regen_power_w: number;
  peak_discharge_current_a: number;
  peak_regen_current_a: number;
  regen_recovery_pct: number;
  timeseries_sample: DriveCycleTimePoint[];
  full_timeseries_len: number;
}

