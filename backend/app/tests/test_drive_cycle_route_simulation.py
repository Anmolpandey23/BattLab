"""
BattLab — Drive Cycle & Dynamic Route Simulation Verification Tests
===================================================================
Verifies:
1. WLTP Class 1 cycle (1,022 seconds, light electric vehicle).
2. Hill-climb route with flat cruise, 3% approach, 8% steep climb, and -5% regen descent.
3. Road surface rolling coefficient impact (asphalt vs gravel).
4. Regenerative energy recovery during downhill braking.
5. Specific energy consumption (Wh/km).
6. Drive-cycle scenario export with DutyCycleSegments.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api import library, projects, simulations, compare_reports
from app.services.drive_cycle import simulate_drive_cycle, ROAD_SURFACE_CR


TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_session():
    with Session(test_engine) as session:
        yield session


@pytest.fixture(autouse=True)
def reset_db():
    SQLModel.metadata.create_all(test_engine)
    for router in [library, projects, simulations, compare_reports]:
        if hasattr(router, "get_session"):
            app.dependency_overrides[router.get_session] = override_get_session
    yield
    SQLModel.metadata.drop_all(test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestDriveCyclePhysics:
    """Independent verification of vehicle drive cycle longitudinal dynamics."""

    def test_wltp_class_1_cycle_runs_and_delivers_energy(self):
        """WLTP Class 1 cycle executes for 1,022 seconds and calculates distance & energy."""
        res = simulate_drive_cycle(
            cycle_type="wltp_class_1",
            vehicle_mass_kg=120.0,
            payload_mass_kg=75.0,
            cd=0.6,
            frontal_area_m2=0.8,
            nominal_pack_voltage_v=51.8,
        )
        assert res["duration_s"] == 1022.0
        assert res["total_distance_km"] > 5.0
        assert res["gross_energy_discharged_wh"] > 0
        assert res["net_energy_consumed_wh"] > 0
        assert res["specific_consumption_wh_per_km"] > 0

    def test_hill_climb_route_recovers_regen_energy_on_descent(self):
        """
        Hill climb route includes a -5% descent phase.
        Must accumulate regenerative recovered energy (e_regen_wh > 0).
        """
        res = simulate_drive_cycle(
            cycle_type="hill_climb_route",
            vehicle_mass_kg=120.0,
            payload_mass_kg=75.0,
            drivetrain_efficiency=0.88,
            regen_efficiency=0.65,
            nominal_pack_voltage_v=51.8,
        )
        assert res["regen_energy_recovered_wh"] > 0
        assert res["regen_recovery_pct"] > 0
        assert res["peak_regen_current_a"] > 0
        assert res["net_energy_consumed_wh"] < res["gross_energy_discharged_wh"]

    def test_gravel_surface_increases_energy_consumption(self):
        """Rougher road surface (gravel Cr=0.025 vs smooth asphalt Cr=0.010) increases energy."""
        res_smooth = simulate_drive_cycle(
            cycle_type="wltp_class_1",
            vehicle_mass_kg=120.0,
            road_surface="asphalt_smooth",
        )
        res_gravel = simulate_drive_cycle(
            cycle_type="wltp_class_1",
            vehicle_mass_kg=120.0,
            road_surface="gravel",
        )
        assert res_gravel["net_energy_consumed_wh"] > res_smooth["net_energy_consumed_wh"]
        assert res_gravel["specific_consumption_wh_per_km"] > res_smooth["specific_consumption_wh_per_km"]

    def test_doubling_payload_increases_climb_and_accel_forces(self):
        """Higher payload increases total traction energy demand."""
        res_solo = simulate_drive_cycle(
            cycle_type="hill_climb_route",
            vehicle_mass_kg=120.0,
            payload_mass_kg=60.0,
        )
        res_heavy = simulate_drive_cycle(
            cycle_type="hill_climb_route",
            vehicle_mass_kg=120.0,
            payload_mass_kg=120.0,
        )
        assert res_heavy["net_energy_consumed_wh"] > res_solo["net_energy_consumed_wh"]


class TestDriveCycleAPI:
    """Verifies HTTP endpoints for drive cycles."""

    def test_api_drive_cycle_simulate(self, client):
        payload = {
            "cycle_type": "hill_climb_route",
            "vehicle_mass_kg": 120.0,
            "payload_mass_kg": 75.0,
            "nominal_pack_voltage_v": 51.8,
        }
        resp = client.post("/api/vehicle-load/drive-cycle/simulate", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "net_energy_consumed_wh" in data
        assert "specific_consumption_wh_per_km" in data
        assert len(data["timeseries_sample"]) > 10

    def test_api_drive_cycle_export_scenario(self, client):
        # Create a project first
        p_res = client.post("/api/projects", json={"name": "Drive Cycle Test Project", "description": ""})
        assert p_res.status_code in (200, 201), p_res.text
        pid = p_res.json()["id"]

        payload = {
            "project_id": pid,
            "cycle_type": "hill_climb_route",
            "vehicle_mass_kg": 120.0,
            "payload_mass_kg": 75.0,
            "nominal_pack_voltage_v": 51.8,
            "ambient_temp_c": 25.0,
        }
        resp = client.post("/api/vehicle-load/drive-cycle/export-scenario", json=payload)
        assert resp.status_code == 201, resp.text
        scenario = resp.json()
        assert "id" in scenario
        assert "Route" in scenario["name"]
        sid = scenario["id"]

        # Check duty cycle segments were automatically attached
        seg_resp = client.get(f"/api/scenarios/{sid}/segments")
        assert seg_resp.status_code == 200
        segments = seg_resp.json()
        assert len(segments) >= 3
        # Should include a regenerative braking segment
        has_regen = any(s["profile_type"] == "regen" for s in segments)
        assert has_regen
