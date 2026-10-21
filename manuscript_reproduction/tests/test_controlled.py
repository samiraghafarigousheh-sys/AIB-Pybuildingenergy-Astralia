"""Controlled-flow option must not alter the default infiltration calculation."""
import copy
import math
import pytest
from apt305_building import build_bui
from pybuildingenergy.source import utils as u


def test_constant_infiltration_is_independent_of_temperature_and_wind():
    b = build_bui()
    b['building_parameters']['ventilation']['infiltration_modulation'] = 'constant'
    expected = u._RHO_CP_AIR_WH_M3K * 54 * .175
    for ti, te, wind in [(20,0,0),(30,40,15),(15,15,3)]:
        assert u._infiltration_h_ve_inf_w_k(b,ti,te,wind) == pytest.approx(expected)


def test_default_infiltration_retains_stack_and_wind_equation():
    b = build_bui()
    expected = u._RHO_CP_AIR_WH_M3K * 54 * .175 * math.sqrt(
        (u._INF_C_STACK*20 + u._INF_C_WIND*25) /
        (u._INF_C_STACK*u._INF_DT_REF + u._INF_C_WIND*u._INF_U_REF**2))
    assert u._infiltration_h_ve_inf_w_k(b,20,0,5) == pytest.approx(expected)
    b['building_parameters']['ventilation']['infiltration_modulation'] = 'typo'
    with pytest.raises(ValueError):
        u._infiltration_h_ve_inf_w_k(b,20,0,5)


def test_offline_country_fallback_never_calls_requests(monkeypatch):
    import requests
    from pybuildingenergy.source.generate_profile import get_country_code_from_latlon
    def forbidden(*args, **kwargs):
        raise AssertionError('Network request must not occur')
    monkeypatch.setattr(requests, 'get', forbidden)
    assert get_country_code_from_latlon(-37.8,144.9,default='AU') == 'AU'


def test_pinned_calendar_can_disable_holidays():
    from pybuildingenergy.source.generate_profile import HourlyProfileGenerator
    gen=HourlyProfileGenerator(country='AU',start_year=2025,use_holidays=False)
    frame=gen.generate()
    assert len(frame)==9504
    assert not frame['is_holiday'].any()
    assert str(frame['datetime'].iloc[744]) == '2026-01-01 00:00:00'
