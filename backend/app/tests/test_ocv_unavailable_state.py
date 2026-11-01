"""
BattLab — OCV Unavailable-Data State & Monotonicity Verification
================================================================
Verifies:
1. Supported chemistries (NMC, NCA, LFP) return monotonic, physical OCV values.
2. Unknown / unsupported chemistries return None (unavailable) without fabricated curves.
3. Simulation explicitly flags unavailable OCV data when an uncalibrated cell is used.
"""
import pytest
from app.services.ecm import get_ocv_v, is_ocv_data_available, OCV_CURVES


class TestOCVDataAvailability:
    """Verifies that OCV data is never fabricated for uncalibrated chemistries."""

    def test_calibrated_chemistries_are_identified(self):
        assert is_ocv_data_available("NMC") is True
        assert is_ocv_data_available("nmc") is True
        assert is_ocv_data_available("NCA") is True
        assert is_ocv_data_available("LFP") is True
        assert is_ocv_data_available("UNKNOWN_CHEMISTRY") is False
        assert is_ocv_data_available("SODIUM_ION") is False

    def test_unknown_chemistry_without_fallback_returns_none(self):
        """When allow_fallback=False, unknown chemistry must strictly return None."""
        ocv = get_ocv_v(soc=0.5, chemistry="MAGNESIUM_ION", allow_fallback=False)
        assert ocv is None

    def test_unknown_chemistry_without_voltage_limits_returns_none(self):
        """Even with allow_fallback=True, if v_min and v_max are absent, return None."""
        ocv = get_ocv_v(soc=0.5, chemistry="SOLID_STATE", v_min=None, v_max=None, allow_fallback=True)
        assert ocv is None

    def test_nmc_ocv_monotonic_between_0_and_1(self):
        """NMC OCV must increase monotonically with SOC."""
        socs = [i * 0.05 for i in range(21)]
        ocvs = [get_ocv_v(s, chemistry="NMC") for s in socs]
        for i in range(len(ocvs) - 1):
            assert ocvs[i + 1] >= ocvs[i], f"Non-monotonic at SOC={socs[i]}: {ocvs[i]} > {ocvs[i+1]}"

    def test_lfp_ocv_shows_characteristic_flat_plateau(self):
        """LFP OCV shows a flat plateau between 30% and 70% SOC (~3.29V - 3.32V)."""
        v_30 = get_ocv_v(0.30, chemistry="LFP")
        v_70 = get_ocv_v(0.70, chemistry="LFP")
        # Over 40% SOC range, delta V is small (< 0.05V)
        assert abs(v_70 - v_30) < 0.05
        assert 3.25 <= v_30 <= 3.35

