"""
BattLab — Vehicle Drive-Cycle and Dynamic Route Simulation Engine
=================================================================
Simulates time-dependent vehicle longitudinal dynamics over realistic drive cycles
and multi-elevation terrain routes.

Calculates second-by-second:
1. Vehicle velocity v(t), acceleration a(t), and road slope theta(t).
2. Longitudinal tractive force breakdown:
     F_rolling(t) = Cr * m * g * cos(theta(t))
     F_grade(t)   = m * g * sin(theta(t))
     F_aero(t)    = 0.5 * rho * Cd * A * v(t)^2
     F_accel(t)   = m * a(t)
     F_total(t)   = F_rolling + F_grade + F_aero + F_accel
3. Mechanical wheel power demand:
     P_mech(t)    = F_total(t) * v(t)   (Watts)
4. Electrical battery power and pack current:
     If P_mech >= 0 (Traction / Acceleration / Uphill):
         P_battery = (P_mech / eta_drive) + P_aux
     If P_mech < 0 (Braking / Deceleration / Downhill):
         P_battery = - abs(P_mech) * eta_drive * eta_regen + P_aux
     I_pack(t)    = P_battery(t) / V_pack_nominal
5. Cumulative energy integration:
     E_discharge_wh += max(0, P_battery) * dt / 3600
     E_regen_wh     += max(0, -P_battery) * dt / 3600
     E_net_wh        = E_discharge_wh - E_regen_wh
     Wh_per_km       = E_net_wh / max(0.001, distance_km)

Supported Standard Drive Cycles & Routes:
- WLTP Class 1 (Light electric vehicles / 2-wheelers up to 50 km/h)
- Hill-Climb Terrain Route (Flat approach -> 3% grade -> 8% climb -> crest -> -5% downhill regen)
- Urban Stop-and-Go Delivery Cycle (Repeated 2 m/s² accelerations, cruises, regen stops)
- Custom Segment Profile (User-defined speed, slope, duration segments)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

GRAVITY_MPS2 = 9.80665

# Road surface rolling resistance baseline coefficients
ROAD_SURFACE_CR: Dict[str, float] = {
    "asphalt_smooth": 0.010,
    "asphalt_average": 0.012,
    "concrete": 0.015,
    "gravel": 0.025,
}


def _generate_wltp_class_1_profile() -> List[Tuple[float, float, float]]:
    """
    Generate the standardized WLTP Class 1 speed-time profile (Light EV / 2-wheeler).
    Duration: 1,022 seconds. Max speed: 50.0 km/h.
    Returns: list of (time_s, speed_kmh, grade_pct)
    """
    profile: List[Tuple[float, float, float]] = []
    # Low speed phase (0 - 300 s): urban stop and go up to 30 km/h
    # Medium speed phase (300 - 600 s): suburban cruise up to 45 km/h
    # High speed phase (600 - 1022 s): outer suburban up to 50 km/h
    for t in range(1023):
        ts = float(t)
        if ts < 20:
            speed = 0.0
        elif ts < 40:
            speed = (ts - 20) * 1.5   # accel to 30 km/h
        elif ts < 90:
            speed = 30.0              # cruise
        elif ts < 110:
            speed = max(0.0, 30.0 - (ts - 90) * 1.5)  # decel
        elif ts < 140:
            speed = 0.0              # idle stop
        elif ts < 165:
            speed = (ts - 140) * 1.4  # accel to 35 km/h
        elif ts < 240:
            speed = 35.0              # cruise
        elif ts < 260:
            speed = max(0.0, 35.0 - (ts - 240) * 1.75)
        elif ts < 300:
            speed = 0.0              # idle
        elif ts < 340:
            speed = (ts - 300) * 1.125 # accel to 45 km/h
        elif ts < 480:
            speed = 45.0 + 3.0 * math.sin(ts / 15.0)  # rolling cruise
        elif ts < 510:
            speed = max(0.0, 45.0 - (ts - 480) * 1.5)
        elif ts < 550:
            speed = 0.0
        elif ts < 600:
            speed = (ts - 550) * 1.0  # accel to 50 km/h
        elif ts < 900:
            speed = 48.0 + 2.0 * math.cos(ts / 25.0)  # fast cruise
        elif ts < 940:
            speed = max(0.0, 50.0 - (ts - 900) * 1.25) # decel
        else:
            speed = 0.0
        profile.append((ts, round(speed, 2), 0.0))
    return profile


def _generate_hill_climb_route() -> List[Tuple[float, float, float]]:
    """
    Generate a multi-elevation terrain route:
    - 0 to 120s: Flat road cruise (45 km/h, 0% grade)
    - 120 to 240s: Moderate approach climb (35 km/h, +3% grade)
    - 240 to 450s: Steep mountain climb (25 km/h, +8% grade)
    - 450 to 520s: Mountain crest (30 km/h, 0% grade)
    - 520 to 750s: Descent with regenerative braking (35 km/h, -5% grade)
    - 750 to 900s: Flat return cruise (40 km/h, 0% grade)
    """
    profile: List[Tuple[float, float, float]] = []
    for t in range(901):
        ts = float(t)
        if ts < 120:
            speed, grade = 45.0, 0.0
        elif ts < 240:
            speed, grade = 35.0, 3.0
        elif ts < 450:
            speed, grade = 25.0, 8.0
        elif ts < 520:
            speed, grade = 30.0, 0.0
        elif ts < 750:
            speed, grade = 35.0, -5.0
        else:
            speed, grade = 40.0, 0.0
        profile.append((ts, speed, grade))
    return profile


def _generate_urban_delivery_cycle() -> List[Tuple[float, float, float]]:
    """
    Urban stop-and-go delivery cycle: 10 repeated delivery stop cycles.
    Each cycle (60s): 10s accel -> 25s cruise at 35 km/h -> 10s regen braking -> 15s stop.
    Duration: 600s.
    """
    profile: List[Tuple[float, float, float]] = []
    for t in range(601):
        ts = float(t)
        t_mod = ts % 60.0
        if t_mod < 10.0:
            speed = t_mod * 3.5          # accel to 35 km/h (0.97 m/s²)
        elif t_mod < 35.0:
            speed = 35.0                 # steady cruise
        elif t_mod < 45.0:
            speed = max(0.0, 35.0 - (t_mod - 35.0) * 3.5) # regen decel
        else:
            speed = 0.0                  # delivery stop
        profile.append((ts, round(speed, 2), 0.0))
    return profile


def simulate_drive_cycle(
    cycle_type: str,
    vehicle_mass_kg: float,
    payload_mass_kg: float = 75.0,
    cr: Optional[float] = None,
    cd: float = 0.60,
    frontal_area_m2: float = 0.80,
    air_density_kg_per_m3: float = 1.225,
    drivetrain_efficiency: float = 0.88,
    regen_efficiency: float = 0.65,
    auxiliary_power_w: float = 50.0,
    nominal_pack_voltage_v: float = 51.8,
    road_surface: str = "asphalt_average",
    custom_points: Optional[List[Tuple[float, float, float]]] = None,
) -> Dict[str, Any]:
    """
    Run second-by-second longitudinal dynamic drive-cycle simulation.
    """
    if vehicle_mass_kg <= 0:
        raise ValueError("Vehicle curb mass must be greater than zero.")
    if drivetrain_efficiency <= 0 or drivetrain_efficiency > 1.0:
        raise ValueError("Drivetrain efficiency must be in (0, 1.0].")
    if regen_efficiency < 0 or regen_efficiency > 1.0:
        raise ValueError("Regen recovery efficiency must be in [0, 1.0].")
    if nominal_pack_voltage_v <= 0:
        raise ValueError("Nominal pack voltage must be positive.")

    # Select rolling resistance
    cr_val = cr if (cr is not None and cr > 0) else ROAD_SURFACE_CR.get(road_surface, 0.012)
    total_mass = vehicle_mass_kg + max(0.0, payload_mass_kg)

    # Resolve speed-slope profile
    if cycle_type == "wltp_class_1":
        raw_profile = _generate_wltp_class_1_profile()
        cycle_title = "Standardized WLTP Class 1 Driving Cycle"
    elif cycle_type == "hill_climb_route":
        raw_profile = _generate_hill_climb_route()
        cycle_title = "Multi-Elevation Hill Climb & Regenerative Descent Route"
    elif cycle_type == "urban_delivery":
        raw_profile = _generate_urban_delivery_cycle()
        cycle_title = "Urban Stop-and-Go Courier Delivery Profile"
    elif cycle_type == "custom" and custom_points:
        raw_profile = sorted(custom_points, key=lambda x: x[0])
        cycle_title = "User-Configured Route Profile"
    else:
        raw_profile = _generate_hill_climb_route()
        cycle_title = "Default Terrain Route"

    timeseries: List[Dict[str, Any]] = []
    e_discharge_wh = 0.0
    e_regen_wh = 0.0
    total_distance_m = 0.0
    peak_traction_power_w = 0.0
    peak_regen_power_w = 0.0
    peak_current_a = 0.0
    peak_regen_current_a = 0.0

    n_pts = len(raw_profile)
    for i in range(n_pts):
        t_s, speed_kmh, grade_pct = raw_profile[i]
        v = max(0.0, speed_kmh / 3.6)

        # Acceleration from adjacent points
        if i < n_pts - 1:
            dt = max(0.1, raw_profile[i + 1][0] - t_s)
            v_next = max(0.0, raw_profile[i + 1][1] / 3.6)
            a = (v_next - v) / dt
        else:
            dt = 1.0
            a = 0.0

        grade_rad = math.atan(grade_pct / 100.0)

        # Forces
        f_rolling = cr_val * total_mass * GRAVITY_MPS2 * math.cos(grade_rad)
        f_grade = total_mass * GRAVITY_MPS2 * math.sin(grade_rad)
        f_aero = 0.5 * air_density_kg_per_m3 * cd * frontal_area_m2 * (v ** 2)
        f_accel = total_mass * a
        f_total = f_rolling + f_grade + f_aero + f_accel

        # Mechanical power
        p_mech = f_total * v

        # Battery electrical power
        if p_mech >= 0:
            p_battery = (p_mech / drivetrain_efficiency) + auxiliary_power_w
        else:
            # Braking regen: only inertial decel and downhill forces deliver recovery
            p_battery = (-abs(p_mech) * drivetrain_efficiency * regen_efficiency) + auxiliary_power_w

        # Current
        i_pack = p_battery / nominal_pack_voltage_v

        # Accumulate metrics
        dt_wh = dt / 3600.0
        if p_battery > 0:
            e_discharge_wh += p_battery * dt_wh
        else:
            e_regen_wh += abs(p_battery) * dt_wh

        step_dist_m = v * dt
        total_distance_m += step_dist_m

        peak_traction_power_w = max(peak_traction_power_w, p_battery)
        if p_battery < 0:
            peak_regen_power_w = max(peak_regen_power_w, abs(p_battery))
        peak_current_a = max(peak_current_a, i_pack)
        if i_pack < 0:
            peak_regen_current_a = max(peak_regen_current_a, abs(i_pack))

        # Thin time series for response if longer than 600 points (sample every N steps)
        timeseries.append({
            "t_s": round(t_s, 1),
            "speed_kmh": round(speed_kmh, 1),
            "grade_pct": round(grade_pct, 1),
            "f_total_n": round(f_total, 1),
            "p_mech_w": round(p_mech, 1),
            "p_battery_w": round(p_battery, 1),
            "current_a": round(i_pack, 2),
            "distance_km": round(total_distance_m / 1000.0, 3),
        })

    total_distance_km = total_distance_m / 1000.0
    net_energy_wh = e_discharge_wh - e_regen_wh
    specific_energy_wh_per_km = (net_energy_wh / total_distance_km) if total_distance_km > 0.05 else 0.0

    return {
        "cycle_type": cycle_type,
        "title": cycle_title,
        "duration_s": round(raw_profile[-1][0], 1),
        "total_distance_km": round(total_distance_km, 2),
        "total_mass_kg": round(total_mass, 1),
        "cr_used": cr_val,
        "cd_used": cd,
        "frontal_area_m2": frontal_area_m2,
        "nominal_bus_voltage_v": nominal_pack_voltage_v,
        "gross_energy_discharged_wh": round(e_discharge_wh, 2),
        "regen_energy_recovered_wh": round(e_regen_wh, 2),
        "net_energy_consumed_wh": round(net_energy_wh, 2),
        "specific_consumption_wh_per_km": round(specific_energy_wh_per_km, 1),
        "peak_traction_power_w": round(peak_traction_power_w, 1),
        "peak_regen_power_w": round(peak_regen_power_w, 1),
        "peak_discharge_current_a": round(peak_current_a, 2),
        "peak_regen_current_a": round(peak_regen_current_a, 2),
        "regen_recovery_pct": round((e_regen_wh / e_discharge_wh * 100.0), 1) if e_discharge_wh > 0 else 0.0,
        "timeseries_sample": timeseries[::max(1, len(timeseries) // 300)],
        "full_timeseries_len": len(timeseries),
    }

