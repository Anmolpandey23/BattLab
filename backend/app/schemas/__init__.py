"""
BattLab — Pydantic/SQLModel schemas for API request/response validation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from app.models import (
    ApplicationCategory, Chemistry, ComponentType, CoolingType,
    ConstraintStatus, DataStatus, DesignMode, FormFactor, SimulationStatus,
)


# ── Cell Spec ─────────────────────────────────────────────────────────────────

class CellSpecCreate(BaseModel):
    manufacturer: str
    model: str
    chemistry: Chemistry = Chemistry.custom
    form_factor: FormFactor = FormFactor.cylindrical_21700
    nominal_voltage_v: float
    min_voltage_v: Optional[float] = None
    max_voltage_v: Optional[float] = None
    nominal_capacity_ah: float
    internal_resistance_ohm: Optional[float] = None
    max_continuous_discharge_a: Optional[float] = None
    max_peak_discharge_a: Optional[float] = None
    max_charge_current_a: Optional[float] = None
    mass_kg: Optional[float] = None
    diameter_mm: Optional[float] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    specific_heat_j_per_kg_k: Optional[float] = None
    thermal_conductance_w_per_k: Optional[float] = None
    min_operating_temp_c: Optional[float] = None
    max_operating_temp_c: Optional[float] = None
    min_charge_temp_c: Optional[float] = None
    max_charge_temp_c: Optional[float] = None
    unit_cost_usd: Optional[float] = None
    datasheet_url: Optional[str] = None
    datasheet_revision: Optional[str] = None
    source_notes: Optional[str] = None
    data_status: DataStatus = DataStatus.provisional

class CellSpecUpdate(BaseModel):
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    chemistry: Optional[Chemistry] = None
    form_factor: Optional[FormFactor] = None
    nominal_voltage_v: Optional[float] = None
    min_voltage_v: Optional[float] = None
    max_voltage_v: Optional[float] = None
    nominal_capacity_ah: Optional[float] = None
    internal_resistance_ohm: Optional[float] = None
    max_continuous_discharge_a: Optional[float] = None
    max_peak_discharge_a: Optional[float] = None
    max_charge_current_a: Optional[float] = None
    mass_kg: Optional[float] = None
    diameter_mm: Optional[float] = None
    length_mm: Optional[float] = None
    specific_heat_j_per_kg_k: Optional[float] = None
    thermal_conductance_w_per_k: Optional[float] = None
    min_operating_temp_c: Optional[float] = None
    max_operating_temp_c: Optional[float] = None
    unit_cost_usd: Optional[float] = None
    data_status: Optional[DataStatus] = None

class CellSpecRead(BaseModel):
    id: int
    created_at: datetime
    manufacturer: str
    model: str
    chemistry: Chemistry
    form_factor: FormFactor
    nominal_voltage_v: float
    min_voltage_v: Optional[float]
    max_voltage_v: Optional[float]
    nominal_capacity_ah: float
    internal_resistance_ohm: Optional[float]
    max_continuous_discharge_a: Optional[float]
    max_peak_discharge_a: Optional[float]
    max_charge_current_a: Optional[float]
    mass_kg: Optional[float]
    diameter_mm: Optional[float]
    length_mm: Optional[float]
    width_mm: Optional[float]
    height_mm: Optional[float]
    specific_heat_j_per_kg_k: Optional[float]
    thermal_conductance_w_per_k: Optional[float]
    min_operating_temp_c: Optional[float]
    max_operating_temp_c: Optional[float]
    unit_cost_usd: Optional[float]
    datasheet_url: Optional[str]
    source_notes: Optional[str]
    data_status: DataStatus
    is_seed: bool

    model_config = {"from_attributes": True}


# ── Component Spec ────────────────────────────────────────────────────────────

class ComponentSpecCreate(BaseModel):
    name: str
    component_type: ComponentType
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    max_voltage_v: Optional[float] = None
    max_current_a: Optional[float] = None
    mass_kg: Optional[float] = None
    unit_cost_usd: Optional[float] = None
    thermal_conductance_w_per_k: Optional[float] = None
    aux_power_w: Optional[float] = None
    source_notes: Optional[str] = None
    data_status: DataStatus = DataStatus.provisional

class ComponentSpecRead(BaseModel):
    id: int
    name: str
    component_type: ComponentType
    manufacturer: Optional[str]
    model: Optional[str]
    max_voltage_v: Optional[float]
    max_current_a: Optional[float]
    mass_kg: Optional[float]
    unit_cost_usd: Optional[float]
    thermal_conductance_w_per_k: Optional[float]
    aux_power_w: Optional[float]
    source_notes: Optional[str]
    data_status: DataStatus
    is_seed: bool

    model_config = {"from_attributes": True}


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    application_category: ApplicationCategory = ApplicationCategory.custom
    engineer_label: Optional[str] = None
    design_version: str = "0.1"
    units: str = "SI"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    application_category: Optional[ApplicationCategory] = None
    engineer_label: Optional[str] = None
    design_version: Optional[str] = None

class ProjectRead(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    name: str
    description: Optional[str]
    application_category: ApplicationCategory
    engineer_label: Optional[str]
    design_version: str
    units: str
    is_demo: bool

    model_config = {"from_attributes": True}

class ProjectSummary(ProjectRead):
    latest_sim_status: Optional[str] = None
    warning_count: int = 0
    configuration_count: int = 0


# ── Requirement ───────────────────────────────────────────────────────────────

class RequirementCreate(BaseModel):
    target_voltage_v: Optional[float] = None
    target_energy_wh: Optional[float] = None
    energy_is_usable: bool = False
    continuous_current_a: Optional[float] = None
    peak_current_a: Optional[float] = None
    peak_duration_s: Optional[float] = None
    max_mass_kg: Optional[float] = None
    max_cost_usd: Optional[float] = None
    charge_time_h: Optional[float] = None
    min_ambient_temp_c: Optional[float] = None
    max_ambient_temp_c: Optional[float] = None
    cooling_preference: CoolingType = CoolingType.passive
    design_notes: Optional[str] = None
    hard_constraints: Optional[list[str]] = None

class RequirementRead(BaseModel):
    id: int
    project_id: int
    target_voltage_v: Optional[float]
    target_energy_wh: Optional[float]
    energy_is_usable: bool
    continuous_current_a: Optional[float]
    peak_current_a: Optional[float]
    peak_duration_s: Optional[float]
    max_mass_kg: Optional[float]
    max_cost_usd: Optional[float]
    charge_time_h: Optional[float]
    min_ambient_temp_c: Optional[float]
    max_ambient_temp_c: Optional[float]
    cooling_preference: CoolingType
    design_notes: Optional[str]
    hard_constraints: Optional[list[str]] = None

    model_config = {"from_attributes": True}


# ── Configuration ─────────────────────────────────────────────────────────────

class ConfigurationCreate(BaseModel):
    label: str = "Baseline"
    design_mode: DesignMode = DesignMode.manual
    cell_spec_id: Optional[int] = None
    ns: int = Field(ge=1)
    np: int = Field(ge=1)
    cells_per_module: Optional[int] = None
    modules_in_series: Optional[int] = None
    modules_in_parallel: Optional[int] = None
    cooling_type: CoolingType = CoolingType.passive
    usable_soc_window: float = Field(default=0.80, ge=0.1, le=1.0)
    interconnect_resistance_ohm: float = 0.0
    notes: Optional[str] = None
    is_baseline: bool = False

class ConfigurationUpdate(BaseModel):
    label: Optional[str] = None
    ns: Optional[int] = None
    np: Optional[int] = None
    cell_spec_id: Optional[int] = None
    cooling_type: Optional[CoolingType] = None
    usable_soc_window: Optional[float] = None
    interconnect_resistance_ohm: Optional[float] = None
    notes: Optional[str] = None
    is_baseline: Optional[bool] = None

class ConfigurationRead(BaseModel):
    id: int
    project_id: int
    label: str
    design_mode: DesignMode
    cell_spec_id: Optional[int]
    ns: int
    np: int
    cells_per_module: Optional[int]
    modules_in_series: Optional[int]
    modules_in_parallel: Optional[int]
    cooling_type: CoolingType
    usable_soc_window: float
    interconnect_resistance_ohm: float
    notes: Optional[str]
    is_baseline: bool
    calc_nominal_voltage_v: Optional[float]
    calc_nominal_energy_wh: Optional[float]
    calc_total_cells: Optional[int]
    calc_cell_mass_kg: Optional[float]
    calc_bom_cost_usd: Optional[float]
    cell_spec: Optional[CellSpecRead] = None

    model_config = {"from_attributes": True}


# ── Candidate Generation ──────────────────────────────────────────────────────

class CandidateRequest(BaseModel):
    cell_spec_id: int
    target_voltage_v: float
    target_energy_wh: float
    energy_is_usable: bool = False
    max_mass_kg: Optional[float] = None
    max_cost_usd: Optional[float] = None
    continuous_current_a: Optional[float] = None
    max_candidates: int = 10

class CandidateSummary(BaseModel):
    ns: int
    np: int
    total_cells: int
    nominal_voltage_v: float
    nominal_energy_wh: float
    estimated_usable_energy_wh: Optional[float]
    estimated_cell_mass_kg: Optional[float]
    estimated_bom_cost_usd: Optional[float]
    voltage_error_pct: float
    energy_error_pct: float
    status: str   # feasible, unverified, infeasible
    pass_notes: list[str]
    fail_notes: list[str]
    warning_notes: list[str]


# ── Scenario ──────────────────────────────────────────────────────────────────

class ScenarioCreate(BaseModel):
    name: str
    description: Optional[str] = None
    ambient_temp_c: float = 25.0
    initial_cell_temp_c: float = 25.0
    initial_soc: float = Field(default=1.0, ge=0.0, le=1.0)
    duration_s: float = Field(default=3600.0, gt=0)
    time_step_s: float = Field(default=1.0, gt=0)
    profile_type: str = "steady_cruise"
    current_profile: Optional[list[tuple[float, float]]] = None  # [(t_s, I_A)]
    capacity_variation_pct: float = 0.0
    resistance_variation_pct: float = 0.0
    resistance_multiplier: float = 1.0
    # User-specified pack discharge current. None → simulation defaults to 1C.
    discharge_current_a: Optional[float] = Field(default=None, gt=0)

class ScenarioRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    ambient_temp_c: float
    initial_cell_temp_c: float
    initial_soc: float
    duration_s: float
    time_step_s: float
    profile_type: str
    capacity_variation_pct: float
    resistance_variation_pct: float
    resistance_multiplier: float
    discharge_current_a: Optional[float]
    is_seed: bool

    model_config = {"from_attributes": True}


class DutyCycleSegmentCreate(BaseModel):
    segment_index: int = 0
    duration_s: float = Field(gt=0)
    profile_type: str = "steady_cruise"
    discharge_current_a: Optional[float] = Field(default=None, ge=0)
    ambient_temp_c: Optional[float] = None
    notes: Optional[str] = None


class DutyCycleSegmentRead(BaseModel):
    id: int
    scenario_id: int
    segment_index: int
    duration_s: float
    profile_type: str
    discharge_current_a: Optional[float]
    ambient_temp_c: Optional[float]
    notes: Optional[str]

    model_config = {"from_attributes": True}


# ── Vehicle Load Analysis ────────────────────────────────────────────────────

class VehicleLoadRequest(BaseModel):
    vehicle_mass_kg: float = Field(gt=0, description="Curb mass of the vehicle (kg)")
    payload_mass_kg: float = Field(default=0.0, ge=0, description="Passenger + cargo load (kg)")
    speed_kmh: Optional[float] = Field(default=None, ge=0, description="Vehicle speed in km/h")
    speed_mps: Optional[float] = Field(default=None, ge=0, description="Vehicle speed in m/s")
    grade_pct: float = Field(default=0.0, description="Road gradient as a percentage (e.g. 5.0 for 5%)")
    cr: float = Field(default=0.015, gt=0, description="Rolling resistance coefficient")
    cd: float = Field(default=0.35, gt=0, description="Aerodynamic drag coefficient")
    frontal_area_m2: float = Field(default=1.8, gt=0, description="Vehicle frontal cross-section area (m²)")
    air_density_kg_per_m3: float = Field(default=1.225, gt=0, description="Ambient air density (kg/m³)")
    acceleration_mps2: float = Field(default=0.0, description="Acceleration (m/s²)")
    drivetrain_efficiency: float = Field(default=0.90, gt=0, le=1.0, description="Transmission + motor efficiency (0-1)")
    regen_efficiency: float = Field(default=0.0, ge=0, le=1.0, description="Regenerative braking recovery fraction (0-1)")
    auxiliary_power_w: float = Field(default=150.0, ge=0, description="Auxiliary electrical load (BMS, lights, telemetry) in Watts")
    nominal_pack_voltage_v: float = Field(default=51.8, gt=0, description="Nominal battery pack bus voltage (V)")


class VehicleLoadResponse(BaseModel):
    total_mass_kg: float
    speed_mps: float
    speed_kmh: float
    grade_rad: float
    f_rolling_n: float
    f_grade_n: float
    f_aero_n: float
    f_accel_n: float
    f_total_n: float
    p_mech_w: float
    p_battery_w: float
    battery_current_a: float
    assumptions: list[str]


# ── Simulation ────────────────────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    configuration_id: int
    scenario_id: int
    run_label: Optional[str] = None
    enable_multi_node_thermal: bool = False
    is_committed: bool = False

class ConstraintResultRead(BaseModel):
    id: int
    rule_id: str
    status: ConstraintStatus
    observed_value: Optional[float]
    threshold: Optional[float]
    units: Optional[str]
    explanation: str
    source_assumption: Optional[str]
    corrective_action: Optional[str]

    model_config = {"from_attributes": True}

class TimeSeriesPoint(BaseModel):
    t_s: float
    current_a: float
    soc: float
    temp_c: float
    temp_core_c: Optional[float] = None
    temp_surface_c: Optional[float] = None
    temp_plate_c: Optional[float] = None
    voltage_v: Optional[float] = None
    power_loss_w: float

class SimulationResultRead(BaseModel):
    simulation_run_id: int
    status: SimulationStatus
    result_nominal_voltage_v: Optional[float]
    result_nominal_energy_wh: Optional[float]
    result_usable_energy_wh: Optional[float]
    result_max_temp_c: Optional[float]
    result_min_soc: Optional[float]
    result_energy_delivered_wh: Optional[float]
    result_soh_capacity_pct: Optional[float] = None
    result_soh_resistance_pct: Optional[float] = None
    result_throughput_ah: Optional[float] = None
    result_efc: Optional[float] = None
    battery_aging: Optional[dict[str, Any]] = None
    multi_node_thermal: Optional[dict[str, Any]] = None
    constraint_pass: int
    constraint_fail: int
    constraint_warning: int
    constraint_unverified: int
    constraints: list[ConstraintResultRead]
    timeseries: list[TimeSeriesPoint]
    assumptions: list[str]
    model_version: str
    completed_at: Optional[datetime]


# ── Comparison ────────────────────────────────────────────────────────────────

class CompareRequest(BaseModel):
    simulation_run_ids: list[int]
    weights: Optional[dict[str, float]] = None  # objective weights

class CompareRow(BaseModel):
    metric: str
    unit: str
    values: dict[str, Any]   # run_label -> value

class CompareResult(BaseModel):
    runs: list[dict]
    metrics_table: list[CompareRow]
    ranking: list[dict]
    warnings_diff: list[dict]


# ── Uncertainty & Validation ──────────────────────────────────────────────────

class UncertaintyRequest(BaseModel):
    n_iterations: int = Field(default=50, ge=10, le=500)
    random_seed: int = Field(default=42)
    capacity_sigma_pct: float = Field(default=2.0, ge=0.1, le=10.0)
    resistance_sigma_pct: float = Field(default=5.0, ge=0.1, le=20.0)
    mass_sigma_pct: float = Field(default=1.5, ge=0.1, le=10.0)
    temp_sigma_c: float = Field(default=1.0, ge=0.1, le=10.0)


class ExperimentalValidationRequest(BaseModel):
    csv_content: str
    custom_mapping: Optional[dict[str, str]] = None
    is_physical_laboratory_data: bool = False
    dataset_name: str = "Imported Battery Test"
    split_ratio_calibration: Optional[float] = None
    split_mode: str = "FULL_DATASET"
    voltage_rmse_threshold_v: Optional[float] = 0.050
    temp_rmse_threshold_c: Optional[float] = 2.5
    min_r2_threshold: Optional[float] = 0.95
    min_aligned_samples: Optional[int] = 10


# ── Drive Cycle & Route Simulation ──────────────────────────────────────────

class DriveCycleRequest(BaseModel):
    cycle_type: str = "hill_climb_route"
    vehicle_mass_kg: float = 120.0
    payload_mass_kg: float = 75.0
    cr: Optional[float] = None
    cd: float = 0.60
    frontal_area_m2: float = 0.80
    air_density_kg_per_m3: float = 1.225
    drivetrain_efficiency: float = 0.88
    regen_efficiency: float = 0.65
    auxiliary_power_w: float = 50.0
    nominal_pack_voltage_v: float = 51.8
    road_surface: str = "asphalt_average"
    custom_points: Optional[list[list[float]]] = None

class DriveCycleExportScenarioRequest(BaseModel):
    project_id: int
    cycle_type: str = "hill_climb_route"
    vehicle_mass_kg: float = 120.0
    payload_mass_kg: float = 75.0
    cr: Optional[float] = None
    cd: float = 0.60
    frontal_area_m2: float = 0.80
    drivetrain_efficiency: float = 0.88
    regen_efficiency: float = 0.65
    auxiliary_power_w: float = 50.0
    nominal_pack_voltage_v: float = 51.8
    road_surface: str = "asphalt_average"
    scenario_name: Optional[str] = None
    ambient_temp_c: float = 25.0


