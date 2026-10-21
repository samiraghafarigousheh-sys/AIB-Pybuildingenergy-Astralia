"""
Regression tests for the submission-review corrections.

1.  A zero exposed perimeter is accepted, not rewritten to 1 m (which created
    a spurious psi_k * 1 m thermal bridge). Negative / non-finite perimeters are
    still validation errors.
2.  The ground-temperature routine returns finite values, without a
    divide-by-zero warning, when the ground-contact area is zero.
3.  Hourly storage: the previous temperature state is COPIED (not aliased to a
    solver buffer that is overwritten in place), envelope nodal storage uses
    areal capacity x element area [J/K], and small balance residuals are no
    longer absorbed into storage. Checked on the massless base case AND on a
    case with non-zero exterior-wall capacity.
4.  Apt 305 declares the 2006-today age band and an explicit q50 = 14 study
    assumption.
5.  The EnergyPlus comparison report ranks discrepancies from the values and
    the historical-headline gate is opt-in.
6.  The airflow audit reads hourly flows from an EnergyPlus-style SQLite file.

Annual simulations make this module slow (~1 min).
"""

from __future__ import annotations

import sqlite3
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (REPO_ROOT / "pybuildingenergy" / "src", REPO_ROOT / "examples",
           REPO_ROOT / "tools" / "diagnostics"):
    sys.path.insert(0, str(_p))

from apt305_building import build_bui  # noqa: E402
from pybuildingenergy.source.check_input import sanitize_and_validate_BUI  # noqa: E402
from pybuildingenergy.source.utils import ISO52016, _q50_for_construction_age  # noqa: E402
from weather_melbourne import CANONICAL_EPW  # noqa: E402

EPW = str(REPO_ROOT / "weather_cache" / CANONICAL_EPW)
HOURLY_TOL_W = 1e-6


def _run(bui_raw):
    bui, _ = sanitize_and_validate_BUI(bui_raw, fix=True)
    hourly, annual, sankey = ISO52016.Temperature_and_Energy_needs_calculation(
        bui, weather_source="epw", path_weather_file=EPW, return_sankey_data=True)
    return bui, hourly, annual, sankey


def _hourly_residual(h):
    return (h["Q_solar_gains"] + h["Q_internal_gains"] + h["Q_HC"]
            - h["Q_ve"] - h["Q_tb"] - h["Q_ground"] - h["Q_tr_total"]
            - h["Q_storage"]).to_numpy(dtype=float)


@pytest.fixture(scope="module")
def base():
    return _run(build_bui())


@pytest.fixture(scope="module")
def massive_wall():
    raw = build_bui()
    # Apt 305 declares construction_class "class_iii", which matches no branch
    # of Areal_heat_capacity_of_element, so every envelope capacity is silently
    # zero. A recognised class is required for the capacity to reach the nodes.
    raw["building"]["construction_class"] = "class_i"
    for s in raw["building_surface"]:
        if s["name"] == "West exterior wall (opaque)":
            s["thermal_capacity"] = 150_000.0  # J/(m2 K)
    return _run(raw)


# --- 1. perimeter ----------------------------------------------------------

def test_zero_perimeter_is_preserved():
    bui, issues = sanitize_and_validate_BUI(build_bui(), fix=True)
    assert bui["building"]["exposed_perimeter"] == 0
    assert not [i for i in issues if i["path"] == "building.exposed_perimeter"
                and i["level"] == "ERROR"]


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_invalid_perimeter_is_an_error(bad):
    raw = build_bui()
    raw["building"]["exposed_perimeter"] = bad
    _bui, issues = sanitize_and_validate_BUI(raw, fix=True)
    assert any(i["path"] == "building.exposed_perimeter" and i["level"] == "ERROR"
               for i in issues)


def test_zero_perimeter_gives_no_thermal_bridge(base):
    _bui, h, annual, _s = base
    assert float(annual["Q_tb_loss_kWh"].iloc[0]) == 0.0
    assert np.all(h["Q_tb"].to_numpy() == 0.0)


# --- 2. ground temperature -------------------------------------------------

def test_ground_temperature_finite_without_contact():
    bui, _ = sanitize_and_validate_BUI(build_bui(), fix=True)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        tg = ISO52016.Temp_calculation_of_ground(
            bui, path_weather_file=EPW, weather_source="epw")
    assert tg.ground_contact_area == 0.0
    assert np.all(np.isfinite(np.asarray(tg.Theta_gr_ve, dtype=float)))
    assert tg.thermal_bridge_heat == 0.0


# --- 3. storage and closure ------------------------------------------------

def test_base_hourly_storage_is_nonzero_and_nets_to_zero(base):
    _bui, h, _a, _s = base
    q = h["Q_storage"].to_numpy(dtype=float)
    assert np.max(np.abs(q)) > 1.0, "hourly storage identically ~0: state aliasing is back"
    charge = np.sum(np.clip(q, 0, None)) / 1000.0
    discharge = np.sum(np.clip(-q, 0, None)) / 1000.0
    assert charge > 10.0 and discharge > 10.0
    assert abs(charge - discharge) < 1e-3 * charge


def test_base_hourly_closure(base):
    _bui, h, _a, sankey = base
    r = _hourly_residual(h)
    assert np.max(np.abs(r)) < HOURLY_TOL_W
    assert "Q_balance_residual" in h.columns
    np.testing.assert_allclose(h["Q_balance_residual"].to_numpy(), r, atol=1e-9)
    c = sankey["closure"]
    assert c["max_abs_hourly_residual_W"] < HOURLY_TOL_W


def test_residual_not_absorbed_into_storage(base):
    _bui, h, _a, sankey = base
    c = sankey["closure"]
    # Storage reported is the signed physical sum, not storage + residual.
    q = h["Q_storage"].to_numpy(dtype=float)
    assert c["storage_Wh"] == pytest.approx(float(np.sum(q)), abs=1e-3)
    assert c["residual_Wh"] == pytest.approx(
        c["inputs_Wh"] - c["outputs_Wh"] - c["storage_Wh"], abs=1e-6)


def test_massive_wall_closure_and_units(massive_wall, base):
    _bui, h, _a, _s = massive_wall
    r = _hourly_residual(h)
    assert np.max(np.abs(r)) < HOURLY_TOL_W, (
        "closure fails with non-zero envelope capacity: storage units/area wrong")
    q_m = np.sum(np.abs(h["Q_storage"].to_numpy(dtype=float)))
    q_b = np.sum(np.abs(base[1]["Q_storage"].to_numpy(dtype=float)))
    assert q_m > q_b, "adding wall capacity must add hourly storage"


def test_unrecognised_construction_class_is_flagged():
    raw = build_bui()
    raw["building"]["construction_class"] = "class_iii"
    _bui, issues = sanitize_and_validate_BUI(raw, fix=True)
    assert any(i["path"] == "building.construction_class" and i["level"] == "WARN"
               for i in issues)


# --- 4. age band / q50 ----------------------------------------------------

def test_apt305_age_band_and_declared_q50():
    raw = build_bui()
    assert raw["building"]["construction_year"] == "2006-today"
    assert raw["building_parameters"]["ventilation"]["envelope_permeability_q50"] == 14.0
    assert _q50_for_construction_age(raw) == 11.0


# --- 5. comparison report -------------------------------------------------

def _report_module():
    import importlib
    return importlib.import_module("corrected_vs_energyplus")


def test_discrepancy_ranking_from_values():
    m = _report_module()
    iso = {"heating_kWh": 122.61, "cooling_kWh": 19.88}
    ep = {"heating_kWh": 148.97, "cooling_kWh": 21.59}
    rk = {r["component"]: r for r in m.discrepancy_ranking(iso, ep)}
    assert rk["Sensible heating"]["rank_abs"] == 1
    assert rk["Sensible heating"]["rank_rel"] == 1
    txt = m._largest(iso, ep)
    assert "heating is the larger" in txt and "also in relative terms" in txt
    # Reverse the relative ordering and the text must follow the numbers.
    iso2 = {"heating_kWh": 95.0, "cooling_kWh": 10.0}
    ep2 = {"heating_kWh": 100.0, "cooling_kWh": 20.0}
    rk2 = {r["component"]: r for r in m.discrepancy_ranking(iso2, ep2)}
    assert rk2["Sensible cooling"]["rank_abs"] == 1
    assert rk2["Sensible cooling"]["rank_rel"] == 1


def test_path_note_asserts_no_cause():
    m = _report_module()
    paths = [{"path": "West windows", "iso": 488.1, "ep": 389.1},
             {"path": "Designed ventilation", "iso": -1748.5, "ep": -1663.0},
             {"path": "Five party surfaces", "iso": 713.1, "ep": 704.3}]
    note = m._largest_path_note(paths)
    assert note.index("West windows") < note.index("Designed ventilation") \
        < note.index("Five party surfaces")
    assert "does not establish" in note


def test_headline_gate_is_opt_in():
    src = (REPO_ROOT / "examples" / "corrected_vs_energyplus.py").read_text()
    assert "--expect-paper-headline" in src
    assert "if args.expect_paper_headline:" in src


# --- 6. airflow audit -----------------------------------------------------

def test_airflow_audit_on_synthetic_sql(tmp_path):
    from audit_energyplus_airflow import audit_airflow
    db = tmp_path / "eplusout.sql"
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE EnvironmentPeriods (EnvironmentPeriodIndex INT, EnvironmentType INT);
    CREATE TABLE Time (TimeIndex INT, EnvironmentPeriodIndex INT);
    CREATE TABLE ReportVariableDataDictionary (ReportVariableDataDictionaryIndex INT,
        VariableName TEXT, KeyValue TEXT, ReportingFrequency TEXT);
    CREATE TABLE ReportVariableData (TimeIndex INT,
        ReportVariableDataDictionaryIndex INT, VariableValue REAL);
    INSERT INTO EnvironmentPeriods VALUES (1, 3);
    """)
    names = [(1, "Zone Ventilation Standard Density Volume Flow Rate", "APT305"),
             (2, "Schedule Value", "ALWAYS1"),
             (3, "Zone Ideal Loads Supply Air Sensible Heating Energy", "IL"),
             (4, "Zone Ideal Loads Supply Air Sensible Cooling Energy", "IL")]
    cur.executemany("INSERT INTO ReportVariableDataDictionary VALUES (?,?,?,'Hourly')", names)
    for t in range(1, 25):
        cur.execute("INSERT INTO Time VALUES (?,1)", (t,))
        cur.execute("INSERT INTO ReportVariableData VALUES (?,1,?)", (t, 0.04 + 0.001 * (t % 3)))
        cur.execute("INSERT INTO ReportVariableData VALUES (?,2,1.0)", (t,))
        cur.execute("INSERT INTO ReportVariableData VALUES (?,3,?)", (t, 1000.0 if t < 4 else 0.0))
        cur.execute("INSERT INTO ReportVariableData VALUES (?,4,0.0)", (t,))
    con.commit()
    con.close()
    res = audit_airflow(db)
    assert res["n_hours"] == 24
    assert res["hours_flow_positive"] == 24
    assert res["plant_off_hours"] == 21
    assert res["plant_off_hours_flow_positive"] == 21
    assert res["schedule_min"] == 1.0
    assert res["continuous_ventilation_verified"] is True
