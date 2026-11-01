"""
BattLab — Tests for mass calculations and discharge_current_a in simulation.

Phase B4: mass recalculates correctly when config changes.
Phase C:  discharge_current_a propagates through simulation.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api import library, projects, simulations, compare_reports


# ── In-memory DB fixture ───────────────────────────────────────────────────────

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


# ── Reference calculations ─────────────────────────────────────────────────────

def ref_cell_mass_kg(ns: int, np: int, mass_per_cell_kg: float) -> float:
    """Reference: total cell mass = ns × np × mass_per_cell_kg."""
    return ns * np * mass_per_cell_kg


# ── Mass calculation tests ─────────────────────────────────────────────────────

class TestMassCalculations:
    """Phase B4 — mass recalculates correctly for different series/parallel counts."""

    @pytest.mark.parametrize("ns,np,mass_cell_kg,expected_kg", [
        (3,  8,  0.050,  1.20),
        (3,  16, 0.050,  2.40),
        (3,  32, 0.050,  4.80),
        (6,  32, 0.050,  9.60),
        (14, 8,  0.070,  7.84),   # 21700-5P reference: 14S×8P×0.070
        (14, 8,  0.045,  5.04),   # 18650-3P reference: 14S×8P×0.045
        (14, 8,  0.090, 10.08),   # LFP-26650 reference: 14S×8P×0.090
        (1,  1,  0.100,  0.10),   # single-cell edge case
        (100, 1, 0.070,  7.00),   # many series
        (1, 100, 0.070,  7.00),   # many parallel
    ])
    def test_cell_mass_formula(self, ns, np, mass_cell_kg, expected_kg):
        """Total cell mass = ns × np × mass_per_cell."""
        result = ref_cell_mass_kg(ns, np, mass_cell_kg)
        assert result == pytest.approx(expected_kg, abs=1e-9)

    @pytest.mark.parametrize("ns,np,mass_cell_kg", [
        (14, 8, 0.070),
        (14, 8, 0.045),
    ])
    def test_mass_doubles_when_parallel_doubles(self, ns, np, mass_cell_kg):
        mass_single = ref_cell_mass_kg(ns, np, mass_cell_kg)
        mass_double = ref_cell_mass_kg(ns, np * 2, mass_cell_kg)
        assert mass_double == pytest.approx(mass_single * 2, rel=1e-9)

    @pytest.mark.parametrize("ns,np,mass_cell_kg", [
        (14, 8, 0.070),
        (7, 16, 0.045),
    ])
    def test_mass_doubles_when_series_doubles(self, ns, np, mass_cell_kg):
        mass_single = ref_cell_mass_kg(ns, np, mass_cell_kg)
        mass_double = ref_cell_mass_kg(ns * 2, np, mass_cell_kg)
        assert mass_double == pytest.approx(mass_single * 2, rel=1e-9)

    def test_mass_zero_cells_is_zero(self):
        """Edge case: 0 parallel → 0 total cells → 0 mass."""
        result = ref_cell_mass_kg(14, 0, 0.070)
        assert result == 0.0

    @pytest.mark.parametrize("ns,np,expected_cells,expected_v,expected_ah,expected_wh,expected_usable_wh,expected_mass_kg", [
        (3, 16, 48, 11.1, 80.0, 888.0, 710.4, 3.36),
        (14, 8, 112, 51.8, 40.0, 2072.0, 1657.6, 7.84),
        (14, 16, 224, 51.8, 80.0, 4144.0, 3315.2, 15.68),
    ])
    def test_user_case_study_three_configurations(
        self, ns, np, expected_cells, expected_v, expected_ah, expected_wh, expected_usable_wh, expected_mass_kg
    ):
        """
        Verifies the three key configurations from the engineering audit:
        - 3S16P: 48 cells, 11.1 V, 80 Ah, 888 Wh gross, 710.4 Wh usable, 3.36 kg cells
        - 14S8P: 112 cells, 51.8 V, 40 Ah, 2072 Wh gross, 1657.6 Wh usable, 7.84 kg cells
        - 14S16P: 224 cells, 51.8 V, 80 Ah, 4144 Wh gross, 3315.2 Wh usable, 15.68 kg cells
        """
        v_cell = 3.7
        ah_cell = 5.0
        mass_cell = 0.070
        soc_window = 0.80

        cells = ns * np
        v_pack = ns * v_cell
        ah_pack = np * ah_cell
        wh_pack = v_pack * ah_pack
        usable_wh = wh_pack * soc_window
        mass_kg = cells * mass_cell

        assert cells == expected_cells
        assert v_pack == pytest.approx(expected_v, abs=1e-5)
        assert ah_pack == pytest.approx(expected_ah, abs=1e-5)
        assert wh_pack == pytest.approx(expected_wh, abs=1e-5)
        assert usable_wh == pytest.approx(expected_usable_wh, abs=1e-5)
        assert mass_kg == pytest.approx(expected_mass_kg, abs=1e-5)

    def test_mass_configuration_api(self, client):
        """Configuration API should include calc_cell_mass_kg when cell has mass data."""
        proj = client.post("/api/projects", json={"name": "Mass Test", "description": ""})
        assert proj.status_code in (200, 201)
        pid = proj.json()["id"]

        cell_resp = client.post("/api/library/cells", json={
            "manufacturer": "Test Cells",
            "model": "TEST-MASS-CELL",
            "chemistry": "NMC",
            "form_factor": "21700",
            "nominal_voltage_v": 3.7,
            "nominal_capacity_ah": 5.0,
            "internal_resistance_ohm": 0.025,
            "mass_kg": 0.070,
            "specific_heat_j_per_kg_k": 900.0,
            "max_continuous_discharge_a": 10.0,
            "data_status": "provisional",
        })
        assert cell_resp.status_code in (200, 201), cell_resp.text
        cell_id = cell_resp.json()["id"]

        cfg_resp = client.post(f"/api/projects/{pid}/configurations", json={
            "name": "14S8P Test",
            "ns": 14,
            "np": 8,
            "cell_spec_id": cell_id,
            "cooling_type": "passive",
        })
        assert cfg_resp.status_code in (200, 201), cfg_resp.text
        cfg = cfg_resp.json()

        expected_mass = 14 * 8 * 0.070  # 7.84 kg
        assert cfg.get("calc_cell_mass_kg") == pytest.approx(expected_mass, abs=1e-6), (
            f"Expected calc_cell_mass_kg≈{expected_mass}, got {cfg.get('calc_cell_mass_kg')}"
        )

    def test_mass_unknown_when_cell_mass_null(self, client):
        """Configuration with null cell mass should have calc_cell_mass_kg = None."""
        proj = client.post("/api/projects", json={"name": "Null Mass Test"})
        pid = proj.json()["id"]

        cell_resp = client.post("/api/library/cells", json={
            "manufacturer": "Test",
            "model": "NULL-MASS-CELL",
            "chemistry": "NMC",
            "form_factor": "18650",
            "nominal_voltage_v": 3.6,
            "nominal_capacity_ah": 3.0,
            "internal_resistance_ohm": 0.030,
            "data_status": "provisional",
        })
        cell_id = cell_resp.json()["id"]

        cfg_resp = client.post(f"/api/projects/{pid}/configurations", json={
            "name": "No Mass Config",
            "ns": 14,
            "np": 8,
            "cell_spec_id": cell_id,
            "cooling_type": "passive",
        })
        assert cfg_resp.status_code in (200, 201), cfg_resp.text
        cfg = cfg_resp.json()
        assert cfg.get("calc_cell_mass_kg") is None, (
            f"Expected None for calc_cell_mass_kg when cell mass is null, got {cfg.get('calc_cell_mass_kg')}"
        )


# ── Discharge current tests ────────────────────────────────────────────────────

class TestDischargeCurrentScenario:
    """Phase C — discharge_current_a propagates through scenario → simulation."""

    def test_scenario_create_with_discharge_current(self, client):
        resp = client.post("/api/scenarios", json={
            "name": "40A Discharge Test",
            "ambient_temp_c": 25.0,
            "duration_s": 3600.0,
            "time_step_s": 10.0,
            "profile_type": "steady_cruise",
            "discharge_current_a": 40.0,
        })
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert data["discharge_current_a"] == pytest.approx(40.0)

    def test_scenario_create_without_discharge_current_defaults_none(self, client):
        resp = client.post("/api/scenarios", json={
            "name": "Default Current Test",
            "ambient_temp_c": 25.0,
            "duration_s": 1800.0,
            "time_step_s": 10.0,
            "profile_type": "steady_cruise",
        })
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert data.get("discharge_current_a") is None

    def test_scenario_discharge_current_must_be_positive(self, client):
        resp = client.post("/api/scenarios", json={
            "name": "Negative Current",
            "discharge_current_a": -5.0,
        })
        assert resp.status_code == 422, (
            f"Expected 422 for negative discharge_current_a, got {resp.status_code}"
        )

    def _create_cell_config(self, client, prefix: str):
        """Helper: create project + cell + config, return (pid, cell_id, cfg_id)."""
        proj = client.post("/api/projects", json={"name": f"{prefix} Project"})
        pid = proj.json()["id"]

        cell_resp = client.post("/api/library/cells", json={
            "manufacturer": "Test",
            "model": f"TEST-{prefix}-CELL",
            "chemistry": "NMC",
            "form_factor": "21700",
            "nominal_voltage_v": 3.7,
            "nominal_capacity_ah": 5.0,
            "internal_resistance_ohm": 0.025,
            "mass_kg": 0.070,
            "specific_heat_j_per_kg_k": 900.0,
            "max_continuous_discharge_a": 10.0,
            "data_status": "provisional",
        })
        cell_id = cell_resp.json()["id"]

        cfg_resp = client.post(f"/api/projects/{pid}/configurations", json={
            "name": "14S8P",
            "ns": 14,
            "np": 8,
            "cell_spec_id": cell_id,
            "cooling_type": "passive",
        })
        cfg_id = cfg_resp.json()["id"]
        return pid, cell_id, cfg_id

    def test_simulation_uses_discharge_current_a(self, client):
        _, _, cfg_id = self._create_cell_config(client, "40A")

        scen_resp = client.post("/api/scenarios", json={
            "name": "40A Discharge",
            "ambient_temp_c": 25.0,
            "duration_s": 60.0,
            "time_step_s": 10.0,
            "profile_type": "steady_cruise",
            "discharge_current_a": 40.0,
        })
        scen_id = scen_resp.json()["id"]

        sim_resp = client.post(f"/api/configurations/{cfg_id}/simulate", json={
            "configuration_id": cfg_id,
            "scenario_id": scen_id,
        })
        assert sim_resp.status_code == 202, sim_resp.text
        sim_id = sim_resp.json()["simulation_id"]

        # Fetch full results
        results_resp = client.get(f"/api/simulations/{sim_id}/results")
        assert results_resp.status_code == 200, results_resp.text
        assumptions = results_resp.json().get("assumptions", [])
        joined = " ".join(assumptions).lower()
        assert "40.0 a" in joined or "user-specified" in joined, (
            f"Expected assumptions to mention 40A. Got: {assumptions}"
        )

    def test_simulation_fallback_to_1c_when_no_discharge_current(self, client):
        _, _, cfg_id = self._create_cell_config(client, "1C")

        scen_resp = client.post("/api/scenarios", json={
            "name": "Default 1C",
            "ambient_temp_c": 25.0,
            "duration_s": 60.0,
            "time_step_s": 10.0,
            "profile_type": "steady_cruise",
        })
        scen_id = scen_resp.json()["id"]

        sim_resp = client.post(f"/api/configurations/{cfg_id}/simulate", json={
            "configuration_id": cfg_id,
            "scenario_id": scen_id,
        })
        assert sim_resp.status_code == 202, sim_resp.text
        sim_id = sim_resp.json()["simulation_id"]

        results_resp = client.get(f"/api/simulations/{sim_id}/results")
        assert results_resp.status_code == 200, results_resp.text
        assumptions = results_resp.json().get("assumptions", [])
        joined = " ".join(assumptions).lower()
        assert "1c" in joined or "no discharge_current_a" in joined, (
            f"Expected 1C fallback note. Got: {assumptions}"
        )

