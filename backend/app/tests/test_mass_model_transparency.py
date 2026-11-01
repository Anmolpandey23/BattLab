"""
BattLab — Transparent Pack Mass Model Independent Verification Tests
=====================================================================
Verifies:
1. Component-level breakdown calculations for 3S16P, 14S8P, and 14S16P.
2. Cell mass scales strictly with Ns * Np * m_cell.
3. Auxiliary components scale with their physical drivers:
   - Busbars scale with cell count
   - BMS scales with series count (Ns)
   - Enclosure scales with cell count
   - Cooling scales with cooling architecture (passive vs fan vs liquid)
4. Missing cell mass sets pack mass strictly to UNAVAILABLE (no invented cell masses).
5. Gravimetric energy density (Wh/kg) and cell-to-pack mass ratios.
"""
import pytest
from app.services.mass_model import calculate_pack_mass_breakdown, PackMassBreakdown


class TestPackMassModelCalculations:
    """Independent reference calculations for transparent pack mass breakdown."""

    def test_3s16p_passive_mass_breakdown(self):
        """
        3S16P (48 cells, 3.7V, 5Ah, 888 Wh, 70g cell):
        - Cells: 48 * 0.070 = 3.360 kg
        - Busbars: 48 * 0.0045 = 0.216 kg
        - BMS: 0.250 + 3 * 0.005 = 0.265 kg
        - Enclosure: 0.800 + 48 * 0.018 = 1.664 kg
        - Cooling (passive): 0.000 kg
        - Wiring: 0.220 + 3 * 0.002 = 0.226 kg
        - Total: 3.360 + 0.216 + 0.265 + 1.664 + 0.0 + 0.226 = 5.731 kg
        """
        res = calculate_pack_mass_breakdown(
            ns=3, np_=16, cell_mass_kg=0.070, cooling_type="passive", nominal_energy_wh=888.0
        )
        assert res.cell_count == 48
        assert res.total_cell_mass_kg == pytest.approx(3.360, abs=1e-3)
        assert res.components["busbars_interconnects"]["mass_kg"] == pytest.approx(0.216, abs=1e-3)
        assert res.components["bms_electronics"]["mass_kg"] == pytest.approx(0.265, abs=1e-3)
        assert res.components["enclosure_structure"]["mass_kg"] == pytest.approx(1.664, abs=1e-3)
        assert res.components["cooling_hardware"]["mass_kg"] == 0.0
        assert res.components["wiring_connectors"]["mass_kg"] == pytest.approx(0.226, abs=1e-3)
        assert res.total_pack_mass_kg == pytest.approx(5.731, abs=1e-3)
        assert res.status == "complete"
        assert res.cell_to_pack_mass_ratio == pytest.approx(3.360 / 5.731, rel=1e-3)

    def test_14s8p_passive_mass_breakdown(self):
        """
        14S8P (112 cells, 51.8V, 40Ah, 2072 Wh, 70g cell):
        - Cells: 112 * 0.070 = 7.840 kg
        - Busbars: 112 * 0.0045 = 0.504 kg
        - BMS: 0.250 + 14 * 0.005 = 0.320 kg
        - Enclosure: 0.800 + 112 * 0.018 = 2.816 kg
        - Cooling: 0.0 kg
        - Wiring: 0.220 + 14 * 0.002 = 0.248 kg
        - Total: 7.840 + 0.504 + 0.320 + 2.816 + 0.0 + 0.248 = 11.728 kg
        """
        res = calculate_pack_mass_breakdown(
            ns=14, np_=8, cell_mass_kg=0.070, cooling_type="passive", nominal_energy_wh=2072.0
        )
        assert res.cell_count == 112
        assert res.total_cell_mass_kg == pytest.approx(7.840, abs=1e-3)
        assert res.total_pack_mass_kg == pytest.approx(11.728, abs=1e-3)
        assert res.gravimetric_energy_density_cell_wh_per_kg == pytest.approx(2072.0 / 7.840, abs=0.1)
        assert res.gravimetric_energy_density_pack_wh_per_kg == pytest.approx(2072.0 / 11.728, abs=0.1)

    def test_14s16p_liquid_cooling_mass_breakdown(self):
        """
        14S16P (224 cells, 51.8V, 80Ah, 4144 Wh, 70g cell, Liquid cooling):
        - Cells: 224 * 0.070 = 15.680 kg
        - Busbars: 224 * 0.0045 = 1.008 kg
        - BMS: 0.250 + 14 * 0.005 = 0.320 kg
        - Enclosure: 0.800 + 224 * 0.018 = 4.832 kg
        - Cooling (liquid): cold plate (224*0.012=2.688) + coolant (0.3+224*0.006=1.644) + fittings (0.2) = 4.532 kg
        - Wiring: 0.220 + 14 * 0.002 = 0.248 kg
        - Total: 15.680 + 1.008 + 0.320 + 4.832 + 4.532 + 0.248 = 26.620 kg
        """
        res = calculate_pack_mass_breakdown(
            ns=14, np_=16, cell_mass_kg=0.070, cooling_type="liquid", nominal_energy_wh=4144.0
        )
        assert res.cell_count == 224
        assert res.total_cell_mass_kg == pytest.approx(15.680, abs=1e-3)
        assert res.components["cooling_hardware"]["mass_kg"] == pytest.approx(4.532, abs=1e-3)
        assert res.total_pack_mass_kg == pytest.approx(26.620, abs=1e-3)
        assert res.cell_to_pack_mass_ratio == pytest.approx(15.680 / 26.620, rel=1e-3)

    def test_cooling_type_changes_cooling_mass(self):
        """Different cooling architectures produce distinct, justifiable cooling hardware masses."""
        passive = calculate_pack_mass_breakdown(14, 16, 0.070, cooling_type="passive")
        fan = calculate_pack_mass_breakdown(14, 16, 0.070, cooling_type="fan")
        liquid = calculate_pack_mass_breakdown(14, 16, 0.070, cooling_type="liquid")

        assert passive.components["cooling_hardware"]["mass_kg"] == 0.0
        assert fan.components["cooling_hardware"]["mass_kg"] > 0.0
        assert liquid.components["cooling_hardware"]["mass_kg"] > fan.components["cooling_hardware"]["mass_kg"]
        assert liquid.total_pack_mass_kg > fan.total_pack_mass_kg > passive.total_pack_mass_kg

    def test_missing_cell_mass_returns_unavailable_total_pack_mass(self):
        """
        CRITICAL TRANSPARENCY REQUIREMENT:
        When cell mass is None or unavailable in the library, total pack mass MUST be None,
        preventing fabricated pack mass figures.
        """
        res = calculate_pack_mass_breakdown(14, 16, cell_mass_kg=None)
        assert res.total_cell_mass_kg is None
        assert res.total_pack_mass_kg is None
        assert res.cell_to_pack_mass_ratio is None
        assert res.status == "unavailable"
        assert res.components["cells"]["status"] == "unavailable"

    def test_invalid_cell_counts_raise_value_error(self):
        with pytest.raises(ValueError):
            calculate_pack_mass_breakdown(0, 16, 0.070)
        with pytest.raises(ValueError):
            calculate_pack_mass_breakdown(14, -1, 0.070)

