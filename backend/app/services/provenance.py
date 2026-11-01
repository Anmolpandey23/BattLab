"""
BattLab — Parameter Provenance & Confidence Tracking Engine
============================================================
Tracks data provenance, uncertainty bounds, and model dependency graphs
for every engineering input parameter used in electrical, thermal,
and vehicle tractive simulations.

Provenance Categories:
- MANUFACTURER_SPECIFIED: From formal OEM datasheet or specification sheet.
- LABORATORY_MEASURED: Experimentally characterized via cycler, EIS, or calorimeter.
- LITERATURE_CALIBRATED: Parameterized from peer-reviewed electrochemical literature.
- USER_PROVIDED: Explicitly entered by the design engineer.
- DERIVED: Calculated from other input parameters.
- ASSUMED_PROVISIONAL: Unverified placeholder/estimate. Low confidence.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class ProvenanceCategory(str, Enum):
    MANUFACTURER_SPECIFIED = "manufacturer_specified"
    LABORATORY_MEASURED   = "laboratory_measured"
    LITERATURE_CALIBRATED = "literature_calibrated"
    USER_PROVIDED         = "user_provided"
    DERIVED               = "derived"
    ASSUMED_PROVISIONAL   = "assumed_provisional"


class ConfidenceLevel(str, Enum):
    HIGH    = "high"        # OEM certified or lab measured
    MEDIUM  = "medium"      # Standard literature calibration or user provided
    LOW     = "low"         # Provisional assumption with unknown tolerance


@dataclass
class ParameterProvenance:
    key: str
    label: str
    value: Any
    unit: str
    category: ProvenanceCategory
    confidence: ConfidenceLevel
    source: str
    uncertainty_pct: Optional[float] = None
    dependent_models: List[str] = field(default_factory=list)
    limitation_note: Optional[str] = None


def generate_provenance_catalog(
    cell: Any,
    configuration: Any,
    scenario: Any,
    requirement: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Construct a complete provenance and confidence inventory for a simulation run.
    """
    params: List[Dict[str, Any]] = []

    # 1. Cell Parameters
    is_seed = getattr(cell, "is_seed", False)
    cat_cell = ProvenanceCategory.ASSUMED_PROVISIONAL if is_seed else ProvenanceCategory.USER_PROVIDED
    conf_cell = ConfidenceLevel.LOW if is_seed else ConfidenceLevel.MEDIUM

    # Nominal Voltage
    params.append(ParameterProvenance(
        key="cell_nominal_voltage_v",
        label="Cell Nominal Voltage",
        value=cell.nominal_voltage_v,
        unit="V",
        category=cat_cell,
        confidence=conf_cell,
        source="Provisional seed catalog" if is_seed else "User-defined cell spec",
        uncertainty_pct=1.0,
        dependent_models=["Electrical Pack Sizing", "OCV Interpolation", "Energy Calculation"],
        limitation_note="Cell nominal voltage is a single-point reference; terminal voltage varies with SOC and load."
    ).__dict__)

    # Cell Capacity
    params.append(ParameterProvenance(
        key="cell_nominal_capacity_ah",
        label="Cell Nominal Capacity",
        value=cell.nominal_capacity_ah,
        unit="Ah",
        category=cat_cell,
        confidence=conf_cell,
        source="Provisional seed catalog" if is_seed else "User-defined cell spec",
        uncertainty_pct=3.0,
        dependent_models=["Pack Capacity", "Coulomb Counting SOC", "Energy Delivered"],
        limitation_note="Actual discharge capacity depends on discharge rate (Peukert effect) and temperature."
    ).__dict__)

    # Internal Resistance
    r_val = getattr(cell, "internal_resistance_ohm", None)
    params.append(ParameterProvenance(
        key="cell_internal_resistance_ohm",
        label="Cell Internal Resistance (R0)",
        value=r_val,
        unit="Ω",
        category=ProvenanceCategory.ASSUMED_PROVISIONAL if is_seed or not r_val else ProvenanceCategory.USER_PROVIDED,
        confidence=ConfidenceLevel.LOW if not r_val or is_seed else ConfidenceLevel.MEDIUM,
        source="Provisional seed catalog" if is_seed else "User cell library",
        uncertainty_pct=10.0 if r_val else None,
        dependent_models=["Ohmic Voltage Drop", "Joule Heat Generation", "Pack Efficiency"],
        limitation_note="DC equivalent resistance is assumed uniform across cells; real cells exhibit manufacturing impedance spread."
    ).__dict__)

    # Cell Mass
    mass_val = getattr(cell, "mass_kg", None)
    params.append(ParameterProvenance(
        key="cell_mass_kg",
        label="Cell Unit Mass",
        value=mass_val,
        unit="kg",
        category=ProvenanceCategory.ASSUMED_PROVISIONAL if is_seed else (ProvenanceCategory.USER_PROVIDED if mass_val else ProvenanceCategory.ASSUMED_PROVISIONAL),
        confidence=ConfidenceLevel.LOW if not mass_val or is_seed else ConfidenceLevel.MEDIUM,
        source="Assumed standard 21700/18650 mass" if is_seed else "Cell specification",
        uncertainty_pct=2.0 if mass_val else None,
        dependent_models=["Thermal Mass (m*Cp)", "Total Pack Cell Mass", "MASS_LIMIT Constraint"],
        limitation_note="Omits structural modules, cooling jackets, busbars, and BMS enclosure mass."
    ).__dict__)

    # Specific Heat Capacity
    cp_val = getattr(cell, "specific_heat_j_per_kg_k", None) or 900.0
    params.append(ParameterProvenance(
        key="cell_specific_heat_j_per_kg_k",
        label="Specific Heat Capacity (Cp)",
        value=cp_val,
        unit="J/(kg·K)",
        category=ProvenanceCategory.LITERATURE_CALIBRATED if getattr(cell, "specific_heat_j_per_kg_k", None) else ProvenanceCategory.ASSUMED_PROVISIONAL,
        confidence=ConfidenceLevel.MEDIUM if getattr(cell, "specific_heat_j_per_kg_k", None) else ConfidenceLevel.LOW,
        source="Typical 900-1050 J/(kg·K) literature range for cylindrical Li-ion cells",
        uncertainty_pct=8.0,
        dependent_models=["Lumped Thermal Transient ODE", "Thermal Time Constant tau"],
        limitation_note="Specific heat varies with temperature and jelly-roll electrolyte saturation."
    ).__dict__)

    # 2. Configuration Parameters
    params.append(ParameterProvenance(
        key="series_count",
        label="Series Cell Count (Ns)",
        value=configuration.ns,
        unit="count",
        category=ProvenanceCategory.USER_PROVIDED,
        confidence=ConfidenceLevel.HIGH,
        source="Pack Architecture Design Input",
        uncertainty_pct=0.0,
        dependent_models=["Pack Voltage", "Busbar Current", "Total Cell Count"],
    ).__dict__)

    params.append(ParameterProvenance(
        key="parallel_count",
        label="Parallel String Count (Np)",
        value=configuration.np,
        unit="count",
        category=ProvenanceCategory.USER_PROVIDED,
        confidence=ConfidenceLevel.HIGH,
        source="Pack Architecture Design Input",
        uncertainty_pct=0.0,
        dependent_models=["Pack Capacity", "Cell Current Sharing", "Total Cell Count"],
    ).__dict__)

    # 3. Scenario Parameters
    params.append(ParameterProvenance(
        key="ambient_temperature_c",
        label="Ambient Temperature",
        value=scenario.ambient_temp_c,
        unit="°C",
        category=ProvenanceCategory.USER_PROVIDED,
        confidence=ConfidenceLevel.HIGH,
        source="Operating Scenario Specification",
        uncertainty_pct=2.0,
        dependent_models=["Newton Cooling Heat Dissipation", "Arrhenius Resistance R(T)"],
    ).__dict__)

    # Summary confidence metrics
    total_params = len(params)
    high_count = sum(1 for p in params if p["confidence"] == ConfidenceLevel.HIGH)
    med_count  = sum(1 for p in params if p["confidence"] == ConfidenceLevel.MEDIUM)
    low_count  = sum(1 for p in params if p["confidence"] == ConfidenceLevel.LOW)

    score = ((high_count * 1.0) + (med_count * 0.6) + (low_count * 0.2)) / (total_params or 1)

    return {
        "parameters": params,
        "summary": {
            "total_parameters": total_params,
            "high_confidence_count": high_count,
            "medium_confidence_count": med_count,
            "low_confidence_count": low_count,
            "overall_confidence_score": round(score * 100, 1),
            "confidence_rating": "MODERATE" if score >= 0.55 else "PROVISIONAL_LOW",
        },
    }

