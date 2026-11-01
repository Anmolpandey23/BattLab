"""
BattLab — Vehicle Tractive Force and Battery Load Calculation Service
=====================================================================
Calculates vehicle tractive forces, mechanical power demand, and required
battery pack electrical load (power and current) under steady, accelerating,
and sloped road conditions.

Physics Formulas:
-----------------
Total vehicle mass:
    m = vehicle_mass_kg + payload_mass_kg

Road grade angle:
    theta = arctan(grade_pct / 100)

1. Rolling resistance:
    F_rolling = Cr * m * g * cos(theta)

2. Gravitational grade force:
    F_grade = m * g * sin(theta)

3. Aerodynamic drag force:
    F_aero = 0.5 * rho * Cd * A * v^2

4. Inertial acceleration force:
    F_accel = m * a

5. Total tractive force:
    F_total = F_rolling + F_grade + F_aero + F_accel

6. Mechanical wheel power:
    P_mech = F_total * v   (Watts)

7. Electrical battery demand:
    If P_mech >= 0 (Traction / Motoring):
        P_battery = (P_mech / eta_drive) + P_aux
    If P_mech < 0 (Deceleration / Regen braking):
        P_battery = - abs(P_mech) * eta_drive * eta_regen + P_aux

8. Nominal pack current:
    I_pack = P_battery / V_pack_nominal   (Amperes)
    (Positive = discharging, Negative = regenerative charging)

Engineering Assumptions and Limitations:
-----------------------------------------
1. Constant rolling resistance coefficient Cr assumed independent of tire pressure,
   temperature, and slip.
2. Constant aerodynamic drag coefficient Cd with zero ambient wind velocity.
3. Air density rho default is 1.225 kg/m^3 at sea level and 15°C.
4. Single lumped mechanical efficiency eta_drive for inverter + motor + gearbox.
5. Linear bus voltage assumption: current computed at nominal pack bus voltage.
6. Regenerative braking recovery is bounded by eta_regen and does not model BMS charge limit cutoffs.
"""
import math
from typing import Any, Dict


GRAVITY_MPS2 = 9.80665


def calculate_vehicle_load(
    vehicle_mass_kg: float,
    payload_mass_kg: float = 0.0,
    speed_kmh: float | None = None,
    speed_mps: float | None = None,
    grade_pct: float = 0.0,
    cr: float = 0.015,
    cd: float = 0.35,
    frontal_area_m2: float = 1.8,
    air_density_kg_per_m3: float = 1.225,
    acceleration_mps2: float = 0.0,
    drivetrain_efficiency: float = 0.90,
    regen_efficiency: float = 0.0,
    auxiliary_power_w: float = 150.0,
    nominal_pack_voltage_v: float = 51.8,
) -> Dict[str, Any]:
    """Calculate tractive forces, power demand, and battery electrical load."""
    if vehicle_mass_kg <= 0:
        raise ValueError("Vehicle mass must be greater than zero.")
    if payload_mass_kg < 0:
        raise ValueError("Payload mass cannot be negative.")
    if drivetrain_efficiency <= 0 or drivetrain_efficiency > 1.0:
        raise ValueError("Drivetrain efficiency must be in range (0, 1.0].")
    if regen_efficiency < 0 or regen_efficiency > 1.0:
        raise ValueError("Regen efficiency must be in range [0, 1.0].")
    if nominal_pack_voltage_v <= 0:
        raise ValueError("Nominal pack voltage must be greater than zero.")

    # Resolve speed
    if speed_mps is not None:
        v = max(0.0, float(speed_mps))
        v_kmh = v * 3.6
    elif speed_kmh is not None:
        v_kmh = max(0.0, float(speed_kmh))
        v = v_kmh / 3.6
    else:
        v = 0.0
        v_kmh = 0.0

    total_mass = vehicle_mass_kg + payload_mass_kg
    grade_rad = math.atan(grade_pct / 100.0)

    # 1. Rolling resistance force
    f_rolling = cr * total_mass * GRAVITY_MPS2 * math.cos(grade_rad)

    # 2. Grade force (positive for uphill, negative for downhill)
    f_grade = total_mass * GRAVITY_MPS2 * math.sin(grade_rad)

    # 3. Aerodynamic drag force
    f_aero = 0.5 * air_density_kg_per_m3 * cd * frontal_area_m2 * (v ** 2)

    # 4. Acceleration force
    f_accel = total_mass * acceleration_mps2

    # 5. Total tractive force
    f_total = f_rolling + f_grade + f_aero + f_accel

    # 6. Mechanical power at wheels (W)
    p_mech = f_total * v

    # 7. Electrical battery power (W)
    if p_mech >= 0:
        p_battery = (p_mech / drivetrain_efficiency) + auxiliary_power_w
    else:
        # Negative tractive power => braking/regen recovery
        p_battery = (-abs(p_mech) * drivetrain_efficiency * regen_efficiency) + auxiliary_power_w

    # 8. Pack current (A)
    battery_current = p_battery / nominal_pack_voltage_v

    assumptions = [
        f"Lumped vehicle mass: {total_mass:.1f} kg (vehicle {vehicle_mass_kg:.1f} kg + payload {payload_mass_kg:.1f} kg).",
        f"Road grade: {grade_pct:.1f}% ({math.degrees(grade_rad):.2f}°).",
        f"Rolling resistance: Cr={cr:.4f}, Aero drag: Cd={cd:.2f}, Frontal area: {frontal_area_m2:.2f} m².",
        f"Drivetrain efficiency: {drivetrain_efficiency * 100:.1f}%, Regen recovery fraction: {regen_efficiency * 100:.1f}%.",
        f"Auxiliary load: {auxiliary_power_w:.1f} W at nominal bus voltage {nominal_pack_voltage_v:.1f} V.",
    ]

    return {
        "total_mass_kg": round(total_mass, 2),
        "speed_mps": round(v, 4),
        "speed_kmh": round(v_kmh, 2),
        "grade_rad": round(grade_rad, 6),
        "f_rolling_n": round(f_rolling, 2),
        "f_grade_n": round(f_grade, 2),
        "f_aero_n": round(f_aero, 2),
        "f_accel_n": round(f_accel, 2),
        "f_total_n": round(f_total, 2),
        "p_mech_w": round(p_mech, 2),
        "p_battery_w": round(p_battery, 2),
        "battery_current_a": round(battery_current, 3),
        "assumptions": assumptions,
    }

