"""
BattLab Backend — Database models (SQLModel)
All entities: Project, Requirements, CellSpec, ComponentSpec,
Configuration, Scenario, SimulationRun, ConstraintResult, etc.
"""
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, DateTime


def _now() -> datetime:
    """Return a naive UTC datetime (stored without tz in SQLite)."""
    return datetime.utcnow()



# ── Enumerations ─────────────────────────────────────────────────────────────

class DataStatus(str, Enum):
    verified = "verified"
    provisional = "provisional"
    unknown = "unknown"

class ConstraintStatus(str, Enum):
    pass_ = "pass"
    fail = "fail"
    warning = "warning"
    unverified = "unverified"

class Chemistry(str, Enum):
    nmc = "NMC"
    lfp = "LFP"
    nca = "NCA"
    lco = "LCO"
    lto = "LTO"
    custom = "Custom"

class FormFactor(str, Enum):
    cylindrical_18650 = "18650"
    cylindrical_21700 = "21700"
    cylindrical_26650 = "26650"
    cylindrical_4680  = "4680"
    prismatic         = "Prismatic"
    pouch             = "Pouch"
    custom            = "Custom"

class ComponentType(str, Enum):
    bms          = "BMS"
    fuse         = "Fuse"
    contactor    = "Contactor"
    busbar       = "Busbar"
    sensor       = "Sensor"
    fan          = "Fan"
    cooling_plate = "CoolingPlate"
    enclosure    = "Enclosure"
    other        = "Other"

class CoolingType(str, Enum):
    passive    = "passive"
    fan        = "fan"
    liquid     = "liquid"
    phase_change = "phase_change"

class SimulationStatus(str, Enum):
    pending   = "pending"
    running   = "running"
    completed = "completed"
    failed    = "failed"

class DesignMode(str, Enum):
    requirements_first = "requirements_first"
    manual             = "manual"

class ApplicationCategory(str, Enum):
    ev_scooter  = "EV Scooter"
    ev_bicycle  = "EV Bicycle"
    ev_car      = "EV Car"
    stationary  = "Stationary Storage"
    marine      = "Marine"
    aerospace   = "Aerospace"
    custom      = "Custom"


# ── Cell Specification ────────────────────────────────────────────────────────

class CellSpec(SQLModel, table=True):
    __tablename__ = "cell_specs"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))

    manufacturer: str
    model: str
    chemistry: Chemistry = Chemistry.custom
    form_factor: FormFactor = FormFactor.cylindrical_21700

    # Electrical
    nominal_voltage_v: float
    min_voltage_v: Optional[float] = None
    max_voltage_v: Optional[float] = None
    nominal_capacity_ah: float
    internal_resistance_ohm: Optional[float] = None
    max_continuous_discharge_a: Optional[float] = None
    max_peak_discharge_a: Optional[float] = None
    max_charge_current_a: Optional[float] = None

    # Physical
    mass_kg: Optional[float] = None
    diameter_mm: Optional[float] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None

    # Thermal
    specific_heat_j_per_kg_k: Optional[float] = None
    thermal_conductance_w_per_k: Optional[float] = None
    min_operating_temp_c: Optional[float] = None
    max_operating_temp_c: Optional[float] = None
    min_charge_temp_c: Optional[float] = None
    max_charge_temp_c: Optional[float] = None

    # Cost & meta
    unit_cost_usd: Optional[float] = None
    datasheet_url: Optional[str] = None
    datasheet_revision: Optional[str] = None
    source_notes: Optional[str] = None
    data_status: DataStatus = DataStatus.provisional
    is_seed: bool = False

    # Relationships
    configurations: List["Configuration"] = Relationship(back_populates="cell_spec")


# ── Component Specification ───────────────────────────────────────────────────

class ComponentSpec(SQLModel, table=True):
    __tablename__ = "component_specs"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))

    name: str
    component_type: ComponentType
    manufacturer: Optional[str] = None
    model: Optional[str] = None

    max_voltage_v: Optional[float] = None
    max_current_a: Optional[float] = None
    mass_kg: Optional[float] = None
    unit_cost_usd: Optional[float] = None
    dimensions_mm: Optional[str] = None   # JSON string "LxWxH"
    source_notes: Optional[str] = None
    data_status: DataStatus = DataStatus.provisional
    is_seed: bool = False

    # Cooling-specific
    thermal_conductance_w_per_k: Optional[float] = None
    aux_power_w: Optional[float] = None

    # Relationships
    config_components: List["ConfigurationComponent"] = Relationship(back_populates="component_spec")


# ── Project ───────────────────────────────────────────────────────────────────

class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))

    name: str
    description: Optional[str] = None
    application_category: ApplicationCategory = ApplicationCategory.custom
    engineer_label: Optional[str] = None
    design_version: str = "0.1"
    units: str = "SI"
    is_demo: bool = False

    # Relationships
    requirements: List["Requirement"] = Relationship(back_populates="project")
    configurations: List["Configuration"] = Relationship(back_populates="project")
    simulation_runs: List["SimulationRun"] = Relationship(back_populates="project")
    reports: List["Report"] = Relationship(back_populates="project")


# ── Requirement ───────────────────────────────────────────────────────────────

class Requirement(SQLModel, table=True):
    __tablename__ = "requirements"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))

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
    hard_constraints_json: Optional[str] = None   # JSON list of field names that are hard constraints

    project: Optional[Project] = Relationship(back_populates="requirements")


# ── Configuration ─────────────────────────────────────────────────────────────

class Configuration(SQLModel, table=True):
    __tablename__ = "configurations"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    cell_spec_id: Optional[int] = Field(default=None, foreign_key="cell_specs.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))

    label: str = "Baseline"
    design_mode: DesignMode = DesignMode.manual
    ns: int = 14          # series count
    np: int = 8           # parallel count
    cells_per_module: Optional[int] = None
    modules_in_series: Optional[int] = None
    modules_in_parallel: Optional[int] = None
    cooling_type: CoolingType = CoolingType.passive
    usable_soc_window: float = 0.80   # fraction e.g. 0.80 = 80%
    interconnect_resistance_ohm: float = 0.0
    notes: Optional[str] = None
    is_baseline: bool = False

    # Calculated cache (updated on save)
    calc_nominal_voltage_v: Optional[float] = None
    calc_nominal_energy_wh: Optional[float] = None
    calc_total_cells: Optional[int] = None
    calc_cell_mass_kg: Optional[float] = None
    calc_bom_cost_usd: Optional[float] = None

    # Relationships
    project: Optional[Project] = Relationship(back_populates="configurations")
    cell_spec: Optional[CellSpec] = Relationship(back_populates="configurations")
    components: List["ConfigurationComponent"] = Relationship(back_populates="configuration")
    simulation_runs: List["SimulationRun"] = Relationship(back_populates="configuration")


# ── ConfigurationComponent (join table) ──────────────────────────────────────

class ConfigurationComponent(SQLModel, table=True):
    __tablename__ = "configuration_components"

    id: Optional[int] = Field(default=None, primary_key=True)
    configuration_id: int = Field(foreign_key="configurations.id")
    component_spec_id: int = Field(foreign_key="component_specs.id")
    quantity: int = 1
    notes: Optional[str] = None

    configuration: Optional[Configuration] = Relationship(back_populates="components")
    component_spec: Optional[ComponentSpec] = Relationship(back_populates="config_components")


# ── Scenario ──────────────────────────────────────────────────────────────────

class Scenario(SQLModel, table=True):
    __tablename__ = "scenarios"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    is_seed: bool = False

    ambient_temp_c: float = 25.0
    initial_cell_temp_c: float = 25.0
    initial_soc: float = 1.0
    duration_s: float = 3600.0
    time_step_s: float = 1.0
    profile_type: str = "steady_cruise"  # steady_cruise, mixed, high_load, custom
    current_profile_json: Optional[str] = None   # JSON list of (t, I) pairs
    capacity_variation_pct: float = 0.0
    resistance_variation_pct: float = 0.0
    resistance_multiplier: float = 1.0
    cooling_override: Optional[str] = None

    # User-specified pack discharge current (A).
    # If None the simulation falls back to 1C (pack.capacity_ah / 1.0).
    discharge_current_a: Optional[float] = None

    simulation_runs: List["SimulationRun"] = Relationship(back_populates="scenario")
    duty_cycle_segments: List["DutyCycleSegment"] = Relationship(back_populates="scenario")


class DutyCycleSegment(SQLModel, table=True):
    __tablename__ = "duty_cycle_segments"

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="scenarios.id")
    segment_index: int = 0
    duration_s: float
    profile_type: str = "steady_cruise"
    discharge_current_a: Optional[float] = None
    ambient_temp_c: Optional[float] = None
    notes: Optional[str] = None

    scenario: Optional[Scenario] = Relationship(back_populates="duty_cycle_segments")


# ── SimulationRun ─────────────────────────────────────────────────────────────

class SimulationRun(SQLModel, table=True):
    __tablename__ = "simulation_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    configuration_id: int = Field(foreign_key="configurations.id")
    scenario_id: Optional[int] = Field(default=None, foreign_key="scenarios.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))
    completed_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))

    run_label: Optional[str] = None
    model_version: str = "0.2.0-beta"
    status: SimulationStatus = SimulationStatus.pending
    error_message: Optional[str] = None

    # Snapshot of inputs (JSON)
    inputs_snapshot_json: Optional[str] = None

    # Summary metrics (from results)
    result_nominal_voltage_v: Optional[float] = None
    result_nominal_energy_wh: Optional[float] = None
    result_usable_energy_wh: Optional[float] = None
    result_max_temp_c: Optional[float] = None
    result_min_soc: Optional[float] = None
    result_energy_delivered_wh: Optional[float] = None
    result_soh_capacity_pct: Optional[float] = None
    result_soh_resistance_pct: Optional[float] = None
    result_throughput_ah: Optional[float] = None
    result_efc: Optional[float] = None
    constraint_pass: int = 0
    constraint_fail: int = 0
    constraint_warning: int = 0
    constraint_unverified: int = 0

    # Time-series stored as JSON (acceptable for initial local app)
    timeseries_json: Optional[str] = None
    # Model assumptions stored as JSON list of strings
    assumptions_json: Optional[str] = None
    # Detailed aging and multi-node thermal summaries
    battery_aging_json: Optional[str] = None
    multi_node_thermal_json: Optional[str] = None

    # Relationships
    project: Optional[Project] = Relationship(back_populates="simulation_runs")
    configuration: Optional[Configuration] = Relationship(back_populates="simulation_runs")
    scenario: Optional[Scenario] = Relationship(back_populates="simulation_runs")
    constraint_results: List["ConstraintResult"] = Relationship(back_populates="simulation_run")


# ── ConstraintResult ──────────────────────────────────────────────────────────

class ConstraintResult(SQLModel, table=True):
    __tablename__ = "constraint_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    simulation_run_id: int = Field(foreign_key="simulation_runs.id")

    rule_id: str
    status: ConstraintStatus
    observed_value: Optional[float] = None
    threshold: Optional[float] = None
    units: Optional[str] = None
    explanation: str
    source_assumption: Optional[str] = None
    corrective_action: Optional[str] = None

    simulation_run: Optional[SimulationRun] = Relationship(back_populates="constraint_results")


# ── Report ────────────────────────────────────────────────────────────────────

class Report(SQLModel, table=True):
    __tablename__ = "reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime))

    format: str = "pdf"    # pdf, csv, json
    filename: str
    file_path: str
    simulation_run_ids_json: Optional[str] = None  # JSON list

    project: Optional[Project] = Relationship(back_populates="reports")
