"""
BattLab — Calibrated Equivalent Circuit Battery Model (ECM)
============================================================
Implements:
1. Chemistry-specific Open-Circuit Voltage (OCV) vs State-of-Charge (SOC).
2. Arrhenius temperature-dependent internal ohmic resistance R0(T).
3. Thevenin 1-RC transient polarization voltage relaxation dynamics (R1, C1).
4. Low-temperature usable capacity derating.
5. Reversible entropic heat generation coupling.

Mathematical Formulation:
--------------------------
1. Cell terminal voltage:
   V_term(t) = V_oc(SOC, T) - I_cell(t) * R0(T) - V_RC(t)

2. 1-RC Polarization dynamic state equation (exact analytical discrete-time update):
   V_RC(t + dt) = V_RC(t) * exp(-dt / tau) + I_cell * R1 * (1 - exp(-dt / tau))
   where tau = R1 * C1.

3. Arrhenius temperature dependence:
   R0(T) = R0_ref * exp( (E_a / R_gas) * (1 / T_K - 1 / T_ref_K) )
   where E_a = 25,000 J/mol, R_gas = 8.314 J/(mol*K), T_ref = 298.15 K (25°C).

4. Pack terminal voltage:
   V_pack(t) = N_s * V_term(t) - I_pack(t) * R_interconnect

5. Heat generation rate per cell:
   Q_gen = I_cell^2 * R0(T) + (V_RC^2 / R1 if R1 > 0 else 0) - I_cell * T_K * (dE_oc / dT)

All sign conventions:
- Positive I_cell = DISCHARGE (decreases SOC, decreases terminal voltage, heats pack).
- Negative I_cell = CHARGE (increases SOC, increases terminal voltage).
"""
import math
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any

# Universal gas constant (J / (mol * K))
R_GAS = 8.31446261815324

# Default reference temperature (25°C in Kelvin)
T_REF_K = 298.15

# Activation energy for lithium-ion electrolyte and interfacial kinetics (J/mol)
# Literature range: 20,000 - 35,000 J/mol (Plett, Huria, Chen 2020)
DEFAULT_ACTIVATION_ENERGY_J_PER_MOL = 25000.0


# ── Chemistry-Specific OCV Reference Points ──────────────────────────────────
# Calibrated from literature open-circuit equilibrium measurements at C/25 and 25°C.
# Coordinates: (SOC [0..1], OCV [V])

OCV_CURVES: Dict[str, List[Tuple[float, float]]] = {
    "NMC": [
        (0.00, 3.00),
        (0.02, 3.25),
        (0.05, 3.45),
        (0.10, 3.58),
        (0.20, 3.65),
        (0.30, 3.70),
        (0.40, 3.75),
        (0.50, 3.82),
        (0.60, 3.90),
        (0.70, 3.98),
        (0.80, 4.05),
        (0.90, 4.13),
        (0.95, 4.17),
        (1.00, 4.20),
    ],
    "NCA": [
        (0.00, 3.00),
        (0.02, 3.28),
        (0.05, 3.48),
        (0.10, 3.60),
        (0.20, 3.66),
        (0.30, 3.71),
        (0.40, 3.76),
        (0.50, 3.82),
        (0.60, 3.91),
        (0.70, 3.99),
        (0.80, 4.06),
        (0.90, 4.14),
        (0.95, 4.18),
        (1.00, 4.20),
    ],
    "LFP": [
        (0.00, 2.50),
        (0.02, 2.95),
        (0.05, 3.16),
        (0.10, 3.22),
        (0.20, 3.28),
        (0.30, 3.29),
        (0.40, 3.29),
        (0.50, 3.30),
        (0.60, 3.31),
        (0.70, 3.32),
        (0.80, 3.33),
        (0.90, 3.36),
        (0.95, 3.45),
        (1.00, 3.65),
    ],
}


def _normalize_chemistry_key(chemistry: Any) -> str:
    """Extract standard uppercase chemistry key from string, Enum, or attribute."""
    if hasattr(chemistry, "value"):
        key = str(chemistry.value).strip().upper()
    else:
        key = str(chemistry or "").strip().upper()
    if key.startswith("CHEMISTRY."):
        key = key.split(".", 1)[1]
    return key


def is_ocv_data_available(chemistry: Any) -> bool:
    """Return True if calibrated OCV reference points exist for chemistry."""
    return _normalize_chemistry_key(chemistry) in OCV_CURVES


def get_ocv_v(
    soc: float,
    chemistry: Any = "NMC",
    v_min: Optional[float] = None,
    v_max: Optional[float] = None,
    dE_dT: float = 0.0,
    temp_c: float = 25.0,
    allow_fallback: bool = True,
) -> Optional[float]:
    """
    Interpolate open-circuit voltage for a given SOC using monotonic piecewise interpolation.
    
    If specific chemistry data is unavailable and allow_fallback is False, returns None.
    If allow_fallback is True, linearly interpolates between v_min and v_max if available.
    """
    chem_key = _normalize_chemistry_key(chemistry)
    if chem_key not in OCV_CURVES and not allow_fallback:
        return None

    clamped_soc = max(0.0, min(1.0, float(soc)))

    if chem_key in OCV_CURVES:
        curve = OCV_CURVES[chem_key]
        # Piecewise linear interpolation on calibrated points
        for i in range(len(curve) - 1):
            s0, v0 = curve[i]
            s1, v1 = curve[i + 1]
            if s0 <= clamped_soc <= s1:
                frac = (clamped_soc - s0) / (s1 - s0) if (s1 > s0) else 0.0
                ocv_base = v0 + frac * (v1 - v0)
                break
        else:
            ocv_base = curve[-1][1]
    else:
        # Transparent fallback only if explicit limits exist; otherwise return None
        if v_min is not None and v_max is not None:
            ocv_base = v_min + clamped_soc * (v_max - v_min)
        else:
            return None

    # Entropic open circuit voltage temperature shift
    delta_T = temp_c - 25.0
    ocv = ocv_base + (dE_dT * delta_T)
    return ocv


def get_arrhenius_resistance_ohm(
    r0_ref_ohm: float,
    temp_c: float,
    activation_energy_j_per_mol: float = DEFAULT_ACTIVATION_ENERGY_J_PER_MOL,
    max_multiplier: float = 8.0,
    min_multiplier: float = 0.4,
) -> float:
    """
    Calculate temperature-dependent internal ohmic resistance using the Arrhenius kinetic equation.
    
    Cold temperatures (e.g. -10°C) increase resistance due to reduced ion mobility.
    Warm temperatures decrease resistance until high-temperature safety limits.
    """
    if r0_ref_ohm <= 0:
        return 0.0

    t_kelvin = max(200.0, min(360.0, temp_c + 273.15))
    # Arrhenius exponent: (Ea / R) * (1/T - 1/T_ref)
    exponent = (activation_energy_j_per_mol / R_GAS) * ( (1.0 / t_kelvin) - (1.0 / T_REF_K) )
    multiplier = math.exp(exponent)

    # Clamped to justified engineering limits to prevent numerical singularity
    clamped_multiplier = max(min_multiplier, min(max_multiplier, multiplier))
    return r0_ref_ohm * clamped_multiplier


def get_temperature_derated_capacity_ah(
    nominal_capacity_ah: float,
    temp_c: float,
    derating_factor_per_deg_c: float = 0.008,
) -> float:
    """
    Compute temperature-dependent usable discharge capacity.
    
    Sub-zero temperatures reduce accessible capacity due to lithium diffusion limitations.
    At 25°C: 100% capacity.
    At 0°C: ~80% capacity.
    At -10°C: ~72% capacity.
    """
    if temp_c >= 25.0:
        return nominal_capacity_ah
    temp_deficit = 25.0 - temp_c
    derate_fraction = max(0.40, 1.0 - (derating_factor_per_deg_c * temp_deficit))
    return nominal_capacity_ah * derate_fraction


@dataclass
class TheveninRCState:
    """State of the 1-RC polarization pair."""
    v_rc: float = 0.0     # Volts across RC pair


def update_thevenin_rc(
    state: TheveninRCState,
    i_cell_a: float,
    dt_s: float,
    r1_ohm: float,
    c1_farad: float,
) -> TheveninRCState:
    """
    Exact discrete-time update for 1-RC polarization dynamic circuit:
    V_RC(t + dt) = V_RC(t) * exp(-dt / (R1*C1)) + I_cell * R1 * (1 - exp(-dt / (R1*C1)))
    """
    if r1_ohm <= 1e-9 or c1_farad <= 1e-9 or dt_s <= 0:
        return TheveninRCState(v_rc=0.0)

    tau = r1_ohm * c1_farad
    decay = math.exp(-dt_s / tau)
    v_rc_next = state.v_rc * decay + (i_cell_a * r1_ohm * (1.0 - decay))
    return TheveninRCState(v_rc=v_rc_next)


@dataclass
class ECMStepResult:
    """Outputs of a single ECM calculation step."""
    soc: float
    ocv_cell_v: float
    r0_cell_ohm: float
    v_rc_v: float
    v_term_cell_v: float
    v_pack_v: float
    p_delivered_w: float
    q_cell_w: float
    q_pack_w: float


def ecm_step(
    soc: float,
    i_pack_a: float,
    dt_s: float,
    temp_c: float,
    ns: int,
    np_: int,
    nominal_capacity_ah: float,
    r0_ref_ohm: float,
    r1_ohm: float = 0.0,
    c1_farad: float = 1000.0,
    rc_state: Optional[TheveninRCState] = None,
    r_interconnect_ohm: float = 0.0,
    chemistry: str = "NMC",
    v_min_cell: Optional[float] = None,
    v_max_cell: Optional[float] = None,
    enable_arrhenius: bool = True,
    dE_dT: float = 0.0,
) -> Tuple[ECMStepResult, TheveninRCState]:
    """
    Execute one complete time step of the Equivalent Circuit Model (ECM).
    
    Returns (ECMStepResult, updated_TheveninRCState).
    """
    if np_ <= 0 or ns <= 0:
        raise ValueError("Series and parallel cell counts must be >= 1")
    if dt_s < 0:
        raise ValueError("Time step dt_s must be >= 0")

    i_cell = i_pack_a / np_
    active_rc = rc_state or TheveninRCState(v_rc=0.0)

    # 1. Update Thevenin polarization state
    if dt_s > 0:
        next_rc = update_thevenin_rc(active_rc, i_cell, dt_s, r1_ohm, c1_farad)
    else:
        next_rc = active_rc

    # 2. Temperature-dependent resistance
    if enable_arrhenius:
        r0 = get_arrhenius_resistance_ohm(r0_ref_ohm, temp_c)
    else:
        r0 = r0_ref_ohm

    # 3. OCV from chemistry curve
    ocv = get_ocv_v(
        soc=soc,
        chemistry=chemistry,
        v_min=v_min_cell,
        v_max=v_max_cell,
        dE_dT=dE_dT,
        temp_c=temp_c,
    )

    # 4. Terminal cell voltage: V_term = V_oc - I * R0 - V_rc
    v_term_cell = ocv - (i_cell * r0) - next_rc.v_rc

    # 5. Pack terminal voltage: V_pack = Ns * V_term - I_pack * R_interconnect
    v_pack = (ns * v_term_cell) - (i_pack_a * r_interconnect_ohm)

    # 6. Electrical power delivered at pack terminals
    p_delivered = v_pack * i_pack_a

    # 7. Heat generation per cell (Joule ohmic + RC loss + reversible entropic)
    t_kelvin = temp_c + 273.15
    q_ohmic = (i_cell ** 2) * r0
    q_polarization = (next_rc.v_rc ** 2) / r1_ohm if r1_ohm > 1e-9 else 0.0
    q_entropic = - (i_cell * t_kelvin * dE_dT) if dE_dT != 0.0 else 0.0
    q_cell = max(0.0, q_ohmic + q_polarization + q_entropic)
    q_pack = q_cell * ns * np_

    res = ECMStepResult(
        soc=soc,
        ocv_cell_v=round(ocv, 4),
        r0_cell_ohm=round(r0, 6),
        v_rc_v=round(next_rc.v_rc, 4),
        v_term_cell_v=round(v_term_cell, 4),
        v_pack_v=round(v_pack, 3),
        p_delivered_w=round(p_delivered, 2),
        q_cell_w=round(q_cell, 4),
        q_pack_w=round(q_pack, 2),
    )
    return res, next_rc
