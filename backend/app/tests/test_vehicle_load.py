"""
BattLab — Vehicle Tractive Force and Battery Load Tests
======================================================
Tests the vehicle load model against independent analytical formulas.

Success Criteria 11:
- Vehicle slope/load affects battery demand
- Tractive forces: rolling, grade, aero, acceleration
- Power and current calculations
- Edge cases and validation
"""
import math
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.vehicle_load import calculate_vehicle_load, GRAVITY_MPS2


# ── Independent analytical reference functions ───────────────────────────────

def ref_rolling(cr: float, m: float, grade_pct: float) -> float:
    theta = math.atan(grade_pct / 100.0)
    return cr * m * GRAVITY_MPS2 * math.cos(theta)


def ref_grade(m: float, grade_pct: float) -> float:
    theta = math.atan(grade_pct / 100.0)
    return m * GRAVITY_MPS2 * math.sin(theta)


def ref_aero(rho: float, cd: float, a: float, v_mps: float) -> float:
    return 0.5 * rho * cd * a * (v_mps ** 2)


def ref_accel(m: float, a_mps2: float) -> float:
    return m * a_mps2


# ── Unit tests for vehicle_load service ───────────────────────────────────────

class TestVehicleLoadPhysics:
    """Verifies each force and power component independently."""

    def test_flat_road_zero_speed_only_aux_load(self):
        """At v=0, P_mech=0, battery power must equal auxiliary power."""
        res = calculate_vehicle_load(
            vehicle_mass_kg=1200.0,
            payload_mass_kg=150.0,
            speed_kmh=0.0,
            grade_pct=0.0,
            auxiliary_power_w=200.0,
            nominal_pack_voltage_v=50.0,
        )
        assert res["p_mech_w"] == 0.0
        assert res["p_battery_w"] == 200.0
        # I = P / V = 200 / 50 = 4.0 A
        assert res["battery_current_a"] == pytest.approx(4.0)
        assert res["f_aero_n"] == 0.0
        assert res["f_grade_n"] == 0.0

    def test_rolling_resistance_formula(self):
        """Rolling resistance F_roll = Cr * m * g * cos(theta)."""
        m = 1000.0
        cr = 0.015
        res = calculate_vehicle_load(vehicle_mass_kg=m, cr=cr, speed_kmh=0.0, grade_pct=0.0)
        expected = ref_rolling(cr, m, 0.0)
        assert res["f_rolling_n"] == pytest.approx(expected, abs=0.05)

    def test_uphill_grade_force_increases_with_slope(self):
        """Grade force increases monotonically with grade percentage."""
        m = 1000.0
        res_0 = calculate_vehicle_load(vehicle_mass_kg=m, grade_pct=0.0, speed_kmh=50.0)
        res_5 = calculate_vehicle_load(vehicle_mass_kg=m, grade_pct=5.0, speed_kmh=50.0)
        res_10 = calculate_vehicle_load(vehicle_mass_kg=m, grade_pct=10.0, speed_kmh=50.0)

        assert res_0["f_grade_n"] == 0.0
        assert res_5["f_grade_n"] > 0
        assert res_10["f_grade_n"] > res_5["f_grade_n"]
        assert res_10["p_battery_w"] > res_5["p_battery_w"] > res_0["p_battery_w"]

        # Exact check for 5% grade
        expected_5 = ref_grade(m, 5.0)
        assert res_5["f_grade_n"] == pytest.approx(expected_5, abs=0.1)

    def test_double_mass_doubles_gravitational_and_rolling_forces(self):
        """Doubling mass at 5% grade must double F_grade and F_rolling."""
        res_1 = calculate_vehicle_load(vehicle_mass_kg=1000.0, grade_pct=5.0, speed_kmh=0.0)
        res_2 = calculate_vehicle_load(vehicle_mass_kg=2000.0, grade_pct=5.0, speed_kmh=0.0)

        assert res_2["f_grade_n"] == pytest.approx(res_1["f_grade_n"] * 2.0, abs=0.1)
        assert res_2["f_rolling_n"] == pytest.approx(res_1["f_rolling_n"] * 2.0, abs=0.1)

    def test_aerodynamic_drag_scales_quadratically_with_speed(self):
        """Doubling speed quadruples aerodynamic drag (F_aero proportional to v^2)."""
        cd = 0.32
        area = 2.0
        res_10 = calculate_vehicle_load(vehicle_mass_kg=1000.0, cd=cd, frontal_area_m2=area, speed_mps=10.0)
        res_20 = calculate_vehicle_load(vehicle_mass_kg=1000.0, cd=cd, frontal_area_m2=area, speed_mps=20.0)

        assert res_20["f_aero_n"] == pytest.approx(res_10["f_aero_n"] * 4.0, abs=0.1)
        expected_10 = ref_aero(1.225, cd, area, 10.0)
        assert res_10["f_aero_n"] == pytest.approx(expected_10, abs=0.1)

    def test_acceleration_force(self):
        """Inertial force F_accel = m * a."""
        m = 1500.0
        a = 2.0  # m/s^2
        res = calculate_vehicle_load(vehicle_mass_kg=m, acceleration_mps2=a, speed_kmh=30.0)
        expected = ref_accel(m, a)
        assert res["f_accel_n"] == pytest.approx(expected, abs=0.1)

    def test_downhill_no_regen_only_auxiliary_load(self):
        """On steep downhill where P_mech < 0, with regen=0, battery power = P_aux."""
        res = calculate_vehicle_load(
            vehicle_mass_kg=1000.0,
            grade_pct=-15.0,  # steep downhill
            speed_kmh=60.0,
            regen_efficiency=0.0,
            auxiliary_power_w=150.0,
        )
        assert res["p_mech_w"] < 0  # gravity pulls vehicle down
        assert res["p_battery_w"] == 150.0  # no regen recovery, only aux load

    def test_downhill_with_regen_delivers_negative_battery_power(self):
        """On steep downhill with regen > 0, battery power is negative (charging)."""
        res = calculate_vehicle_load(
            vehicle_mass_kg=1500.0,
            grade_pct=-12.0,
            speed_kmh=50.0,
            drivetrain_efficiency=0.90,
            regen_efficiency=0.70,
            auxiliary_power_w=100.0,
            nominal_pack_voltage_v=50.0,
        )
        assert res["p_mech_w"] < 0
        # Negative battery power means net regenerative charging
        assert res["p_battery_w"] < 0
        assert res["battery_current_a"] < 0  # charging current

    def test_invalid_inputs_raise_value_errors(self):
        with pytest.raises(ValueError, match="mass"):
            calculate_vehicle_load(vehicle_mass_kg=-10.0)
        with pytest.raises(ValueError, match="efficiency"):
            calculate_vehicle_load(vehicle_mass_kg=1000.0, drivetrain_efficiency=1.5)
        with pytest.raises(ValueError, match="voltage"):
            calculate_vehicle_load(vehicle_mass_kg=1000.0, nominal_pack_voltage_v=0.0)

    def test_grade_resistance_at_0_3_8_15_percent(self):
        """Verifies grade resistance across 0%, 3%, 8%, and 15% road grades against reference formula."""
        total_m = 195.0
        for grade in [0.0, 3.0, 8.0, 15.0]:
            res = calculate_vehicle_load(vehicle_mass_kg=120.0, payload_mass_kg=75.0, grade_pct=grade, speed_kmh=25.0)
            expected_f_grade = ref_grade(total_m, grade)
            assert res["f_grade_n"] == pytest.approx(expected_f_grade, abs=0.15), (
                f"Grade {grade}% failed: expected {expected_f_grade:.2f}N, got {res['f_grade_n']:.2f}N"
            )

    def test_issue_1_and_2_reference_case(self):
        """
        Tests the exact audit reference case:
        Vehicle curb mass 120 kg, payload 75 kg (total 195 kg),
        Speed 25 km/h (6.944 m/s), grade 8%, Cr 0.012, Cd 0.6, Frontal area 0.8 m²,
        drivetrain efficiency 0.88, auxiliary power 50 W, pack nominal voltage 51.8 V.

        Analytical reference values:
        - F_rolling: ~22.9 N (22.87 N)
        - F_grade: ~152.6 N (152.50 N)
        - F_aero: ~14.2 N (14.18 N)
        - F_total: ~189.7 N (189.55 N)
        - P_mech: ~1,317 W (1,316.31 W)
        - P_battery: ~1,547 W (1,545.81 W)
        - I_pack: ~29.9 A (29.84 A)
        """
        res = calculate_vehicle_load(
            vehicle_mass_kg=120.0,
            payload_mass_kg=75.0,
            speed_kmh=25.0,
            grade_pct=8.0,
            cr=0.012,
            cd=0.6,
            frontal_area_m2=0.8,
            drivetrain_efficiency=0.88,
            auxiliary_power_w=50.0,
            nominal_pack_voltage_v=51.8,
        )
        assert res["total_mass_kg"] == 195.0
        assert res["speed_kmh"] == 25.0
        assert res["speed_mps"] == pytest.approx(25.0 / 3.6, abs=1e-3)
        assert res["f_rolling_n"] == pytest.approx(22.9, abs=0.15)
        assert res["f_grade_n"] == pytest.approx(152.6, abs=0.2)
        assert res["f_aero_n"] == pytest.approx(14.2, abs=0.15)
        assert res["f_total_n"] == pytest.approx(189.7, abs=0.3)
        assert res["p_mech_w"] == pytest.approx(1316.3, abs=2.0)
        assert res["p_battery_w"] == pytest.approx(1545.8, abs=2.0)
        assert res["battery_current_a"] == pytest.approx(29.84, abs=0.15)

    def test_speed_conversion_and_drag_35kmh_vs_25kmh(self):
        """
        At 35 km/h (9.72 m/s), drag is 27.8 N; at 25 km/h (6.94 m/s), drag is 14.2 N.
        Confirms speed conversion occurs exactly once and drag scales with v^2.
        """
        res_25 = calculate_vehicle_load(vehicle_mass_kg=120.0, payload_mass_kg=75.0, speed_kmh=25.0, cd=0.6, frontal_area_m2=0.8)
        res_35 = calculate_vehicle_load(vehicle_mass_kg=120.0, payload_mass_kg=75.0, speed_kmh=35.0, cd=0.6, frontal_area_m2=0.8)
        assert res_25["f_aero_n"] == pytest.approx(14.18, abs=0.15)
        assert res_35["f_aero_n"] == pytest.approx(27.78, abs=0.15)
        # Ratio of aero drag must equal (35/25)^2 = 1.96
        ratio = res_35["f_aero_n"] / res_25["f_aero_n"]
        assert ratio == pytest.approx((35.0 / 25.0) ** 2, rel=0.01)


# ── Integration tests via HTTP API ────────────────────────────────────────────

client = TestClient(app)


class TestVehicleLoadAPI:
    """Verifies POST /api/vehicle-load/calculate endpoint."""

    def test_api_vehicle_load_success(self):
        payload = {
            "vehicle_mass_kg": 150.0,      # e-scooter/e-bike
            "payload_mass_kg": 75.0,
            "speed_kmh": 25.0,
            "grade_pct": 5.0,
            "cr": 0.008,
            "cd": 0.7,
            "frontal_area_m2": 0.6,
            "auxiliary_power_w": 20.0,
            "nominal_pack_voltage_v": 48.0,
        }
        resp = client.post("/api/vehicle-load/calculate", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_mass_kg"] == 225.0
        assert data["f_grade_n"] > 0
        assert data["p_battery_w"] > 0
        assert data["battery_current_a"] > 0
        assert len(data["assumptions"]) >= 4

    def test_api_vehicle_load_validation_error(self):
        resp = client.post("/api/vehicle-load/calculate", json={
            "vehicle_mass_kg": -100.0,
        })
        assert resp.status_code == 422

    def test_api_vehicle_load_exact_audit_case(self):
        """Verifies API response for the exact 195 kg, 25 km/h, 8% slope audit scenario."""
        payload = {
            "vehicle_mass_kg": 120.0,
            "payload_mass_kg": 75.0,
            "speed_kmh": 25.0,
            "grade_pct": 8.0,
            "cr": 0.012,
            "cd": 0.6,
            "frontal_area_m2": 0.8,
            "drivetrain_efficiency": 0.88,
            "auxiliary_power_w": 50.0,
            "nominal_pack_voltage_v": 51.8,
        }
        resp = client.post("/api/vehicle-load/calculate", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_mass_kg"] == 195.0
        assert data["speed_kmh"] == 25.0
        assert data["f_rolling_n"] == pytest.approx(22.9, abs=0.2)
        assert data["f_grade_n"] == pytest.approx(152.6, abs=0.2)
        assert data["f_aero_n"] == pytest.approx(14.2, abs=0.2)
        assert data["f_total_n"] == pytest.approx(189.7, abs=0.3)
        assert data["p_mech_w"] == pytest.approx(1316.3, abs=2.0)
        assert data["p_battery_w"] == pytest.approx(1545.8, abs=2.0)
        assert data["battery_current_a"] == pytest.approx(29.84, abs=0.15)
        # Verify assumptions explicitly document 8.0% grade and 1.225 kg/m3
        assumptions_text = " ".join(data["assumptions"])
        assert "Road grade: 8.0%" in assumptions_text
        assert "195.0 kg" in assumptions_text

