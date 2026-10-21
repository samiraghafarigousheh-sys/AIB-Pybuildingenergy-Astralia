"""Regression tests for four silent input-handling defects.

1. Internal-gain full loads under ``building_parameters.internal_gains`` were
   ignored (the override read only a top-level ``internal_gains`` key).
2. ``climate_parameters.coldest_month`` was ignored by the coldest-month resolver.
3. The single-zone solvers looked up a window's shading column by the name of
   the *aggregated* element, found none, and silently used F_sh = 1.
4. The example spelling ``overhang_proprieties`` was not read at all.
"""
import copy
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pybuildingenergy" / "src"))
sys.path.insert(0, str(ROOT / "examples"))

from pybuildingenergy.source import utils as u  # noqa: E402
from pybuildingenergy.source.ventilation import VentilationInternalGains  # noqa: E402

CASE = ROOT / "revision_results" / "inputs" / "repaired.json"


def _case():
    return json.loads(CASE.read_text())


# --- 1. internal gains -------------------------------------------------------

def _gain_total(bo):
    vig = VentilationInternalGains(bo)
    out = vig.internal_gains("Residential_apartment", 20.0)
    return float(np.asarray(out).reshape(-1)[0])


def test_nested_internal_gain_full_loads_are_used():
    bo = {"building_parameters": {"internal_gains": [
        {"name": "occupants", "full_load": 8.0},
        {"name": "appliances", "full_load": 5.0},
        {"name": "lighting", "full_load": 3.0},
    ]}}
    assert _gain_total(bo) == pytest.approx(20.0 * (8.0 + 5.0 + 3.0))


def test_table_values_apply_when_no_override():
    # EN 16798-1 Residential_apartment: 4.2 + 3.0 + 0 (NaN lighting) W/m2.
    assert _gain_total({"building_parameters": {}}) == pytest.approx(20.0 * 7.2)


def test_top_level_internal_gains_still_take_precedence():
    bo = {"internal_gains": [{"name": "occupants", "full_load": 1.0}],
          "building_parameters": {"internal_gains": [{"name": "occupants", "full_load": 9.0}]}}
    assert _gain_total(bo) == pytest.approx(20.0 * (1.0 + 3.0))


# --- 2. coldest month --------------------------------------------------------

@pytest.mark.parametrize("lat, explicit, expected", [
    (-37.8, None, 7), (41.9, None, 1), (41.9, 7, 7), (-37.8, 2, 2),
])
def test_coldest_month_reads_climate_parameters(lat, explicit, expected):
    bo = {"building": {"latitude": lat}, "building_parameters": {"climate_parameters": {}}}
    if explicit is not None:
        bo["building_parameters"]["climate_parameters"]["coldest_month"] = explicit
    assert u._resolve_coldest_month(bo) == expected


def test_top_level_coldest_month_still_wins():
    bo = {"building": {"latitude": 41.9},
          "building_parameters": {"coldest_month": 3, "climate_parameters": {"coldest_month": 7}}}
    assert u._resolve_coldest_month(bo) == 3


# --- 3. shading of aggregated windows ----------------------------------------

def test_aggregation_records_source_windows():
    bo = _case()
    labels = {0: "NV", 90: "EV", 180: "SV", 270: "WV"}
    for s in bo["building_surface"]:
        s["ISO52016_type_string"] = u._classify_iso52016_element(s)
        o = s["orientation"]
        s["ISO52016_orientation_string"] = (
            "HOR" if float(o["tilt"]) == 0.0 else labels[int(o["azimuth"]) % 360])
    agg = u.ISO52016()._aggregate_surfaces_by_direction(copy.deepcopy(bo))
    windows = [s for s in agg["building_surface"] if s["type"] == "transparent"]
    assert len(windows) == 1
    assert sorted(n for n, _ in windows[0]["aggregated_from"]) == [
        "West window - fixed", "West window - operable"]
    assert sum(a for _, a in windows[0]["aggregated_from"]) == pytest.approx(1.62)


def test_window_shading_series_area_weights_sources():
    sim_df = pd.DataFrame({"W_a": [1.0, 0.5, 0.0], "W_b": [1.0, 1.0, 1.0]})
    surf = {"name": "a + b", "area": 3.0, "aggregated_from": [["a", 1.0], ["b", 2.0]]}
    np.testing.assert_allclose(u._window_shading_series(sim_df, surf), [1.0, 5 / 6, 2 / 3])


def test_window_shading_series_unaggregated_and_missing():
    sim_df = pd.DataFrame({"W_a": [0.4, 0.6]})
    np.testing.assert_allclose(u._window_shading_series(sim_df, {"name": "a", "area": 1.0}), [0.4, 0.6])
    assert u._window_shading_series(sim_df, {"name": "zzz", "area": 1.0}) is None


# --- 4. overhang key spelling ------------------------------------------------

def _shading_columns(overhang_key):
    from pybuildingenergy.source.check_input import sanitize_and_validate_BUI
    from weather_melbourne import CANONICAL_EPW
    bo = _case()
    for s in bo["building_surface"]:
        if s["type"] == "transparent":
            s.update({"shading": True, "shading_type": "horizontal_overhang",
                      "width_or_distance_of_shading_elements": 0.05,
                      overhang_key: {"width_of_horizontal_overhangs": 0.25}})
            for k in ("overhang_properties", "overhang_proprieties"):
                if k != overhang_key:
                    s.pop(k, None)
    for z in bo["adjacent_zones"]:
        for k in ("area_facade_elements", "typology_elements",
                  "transmittance_U_elements", "orientation_elements"):
            z[k] = np.asarray(z[k])
    clean, _ = sanitize_and_validate_BUI(bo, fix=True)
    df = u.Calculation_ISO_52010(clean, str(ROOT / "weather_cache" / CANONICAL_EPW),
                                 weather_source="epw").sim_df
    return df["W_West window - fixed"].to_numpy()


def test_overhang_misspelling_is_read_with_warning():
    correct = _shading_columns("overhang_properties")
    assert correct.min() < 0.9, "a 0.25 m overhang must shade a west window"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        misspelt = _shading_columns("overhang_proprieties")
    np.testing.assert_allclose(misspelt, correct)
    assert any("overhang_proprieties" in str(w.message) for w in caught)
