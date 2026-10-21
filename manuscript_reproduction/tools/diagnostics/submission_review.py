"""
Submission-review runs: base case, controlled boundary/infiltration
sensitivities, and hourly energy-balance closure checks.

Every case uses the SAME final engine, weather file, zone gains and control
settings as the base case. Exactly one named assumption is changed per case.
The exposed ground perimeter is 0 m in every case except the one explicitly
labelled as the historical-perimeter reproduction (1 m, the value the old input
sanitiser used to substitute).

These are uncertainty scenarios, not calibration to measurements, and none of
them establishes the real temperature or conditioning status of the corridor or
the neighbouring apartments.

Outputs (default ``results/submission_review/``):

* ``sensitivity.csv``   one row per case: heating, cooling, latent estimate,
                        storage charge/discharge, annual and max hourly residual
* ``base_case.json``    the base-case record (sensible loads, latent estimate,
                        thermal-bridge loss, storage, closure, q50 provenance)
* ``hourly/<case>.csv`` full hourly balance per case (only with --hourly)

Usage
-----
    python tools/diagnostics/submission_review.py
    python tools/diagnostics/submission_review.py --cases base,q50_11 --hourly
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import csv
import io
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT / "examples", REPO_ROOT / "pybuildingenergy" / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DEFAULT_EPW = (REPO_ROOT / "weather_cache"
               / "AUS_VIC_Melbourne-Essendon.Fields.958660_TMYx.2011-2025.epw")
OUTDIR = REPO_ROOT / "results" / "submission_review"

APARTMENTS = ("apt_above", "apt_below", "apt_north", "apt_south")
CORRIDOR = "corridor"


# ---------------------------------------------------------------------------
# Case definitions: each is a function bui -> bui changing ONE assumption
# ---------------------------------------------------------------------------

def _neighbours_at(t: float):
    def f(bui):
        for z in bui["adjacent_zones"]:
            z["conditioned"] = True
            z["setpoint"] = float(t)
        return bui
    return f


def _unconditioned(names):
    def f(bui):
        for z in bui["adjacent_zones"]:
            if z["name"] in names:
                z["conditioned"] = False
                z.pop("setpoint", None)
        return bui
    return f


def _q50(v: float):
    def f(bui):
        bui["building_parameters"]["ventilation"]["envelope_permeability_q50"] = float(v)
        return bui
    return f


def _perimeter(p: float):
    def f(bui):
        bui["building"]["exposed_perimeter"] = float(p)
        return bui
    return f


CASES = {
    # key: (label, changed assumption, mutator)
    "base": ("Base: all neighbours 20 C, q50 = 14", "none", lambda b: b),
    "nb_18": ("All neighbours 18 C", "neighbour setpoint", _neighbours_at(18.0)),
    "nb_22": ("All neighbours 22 C", "neighbour setpoint", _neighbours_at(22.0)),
    "nb_24": ("All neighbours 24 C", "neighbour setpoint", _neighbours_at(24.0)),
    "corridor_buffer": ("Apartments 20 C; corridor unconditioned buffer",
                        "corridor conditioning", _unconditioned({CORRIDOR})),
    "all_buffer": ("All adjacent spaces unconditioned buffers",
                   "neighbour conditioning",
                   _unconditioned(set(APARTMENTS) | {CORRIDOR})),
    "q50_3.3": ("q50 = 3.3 m3/(h m2)", "envelope permeability", _q50(3.3)),
    "q50_11": ("q50 = 11 m3/(h m2) (2006-today band default)",
               "envelope permeability", _q50(11.0)),
    "perimeter_1m": ("Historical-perimeter reproduction: exposed perimeter 1 m",
                     "exposed perimeter", _perimeter(1.0)),
}


# ---------------------------------------------------------------------------

def run_case(bui_raw: dict, epw: Path, quiet: bool = True) -> dict:
    from pybuildingenergy.source.check_input import sanitize_and_validate_BUI
    from pybuildingenergy.source.utils import ISO52016

    sink = io.StringIO()
    with contextlib.ExitStack() as stack:
        if quiet:  # engine prints diagnostics and tqdm bars (stderr)
            stack.enter_context(contextlib.redirect_stdout(sink))
            stack.enter_context(contextlib.redirect_stderr(sink))
        bui, issues = sanitize_and_validate_BUI(bui_raw, fix=True)
        out = ISO52016.Temperature_and_Energy_needs_calculation(
            bui, weather_source="epw", path_weather_file=str(epw))
    hourly, annual = out[0], out[1]
    errors = [i for i in issues if i.get("level") == "ERROR"]
    if errors:
        raise RuntimeError(f"input validation errors: {errors}")

    def A(k):
        return float(pd.to_numeric(annual[k], errors="coerce").iloc[0]) \
            if k in annual.columns else float("nan")

    h = hourly
    q_in = h["Q_solar_gains"] + h["Q_internal_gains"] + h["Q_HC"]
    q_out = h["Q_ve"] + h["Q_tb"] + h["Q_ground"] + h["Q_tr_total"]
    resid = (q_in - q_out - h["Q_storage"]).to_numpy(dtype=float)
    sto = h["Q_storage"].to_numpy(dtype=float)
    through = float(np.sum(np.abs(q_in.to_numpy(dtype=float)))) / 1000.0
    return {
        "heating_kWh": A("Q_H_sensible_kWh"),
        "cooling_kWh": A("Q_C_sensible_kWh"),
        "latent_estimate_kWh": A("Q_C_latent_kWh"),
        "sensible_total_kWh": A("Q_H_sensible_kWh") + A("Q_C_sensible_kWh"),
        "thermal_bridge_loss_kWh": A("Q_tb_loss_kWh"),
        "storage_charge_kWh": float(np.sum(np.clip(sto, 0, None))) / 1000.0,
        "storage_discharge_kWh": float(np.sum(np.clip(-sto, 0, None))) / 1000.0,
        "storage_net_kWh": float(np.sum(sto)) / 1000.0,
        "annual_residual_kWh": float(np.sum(resid)) / 1000.0,
        "max_abs_hourly_residual_W": float(np.max(np.abs(resid))),
        "input_throughput_kWh": through,
        "exposed_perimeter_after_sanitise_m": float(bui["building"]["exposed_perimeter"]),
        "n_hours": int(len(h)),
        "_hourly": h,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weather", type=Path, default=DEFAULT_EPW)
    ap.add_argument("--outdir", type=Path, default=OUTDIR)
    ap.add_argument("--cases", default=",".join(CASES),
                    help=f"comma-separated subset of: {', '.join(CASES)}")
    ap.add_argument("--hourly", action="store_true",
                    help="also write the full hourly balance per case")
    ap.add_argument("--residual-tol-w", type=float, default=1e-6,
                    help="fail if any case's max |hourly residual| exceeds this")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    from apt305_building import build_bui
    from pybuildingenergy.source.utils import _q50_for_construction_age

    keys = [k.strip() for k in args.cases.split(",") if k.strip()]
    unknown = [k for k in keys if k not in CASES]
    if unknown:
        raise SystemExit(f"unknown case(s): {unknown}")
    args.outdir.mkdir(parents=True, exist_ok=True)

    rows, failures = [], []
    for k in keys:
        label, changed, mut = CASES[k]
        t0 = time.time()
        res = run_case(mut(copy.deepcopy(build_bui())), args.weather,
                       quiet=not args.verbose)
        hourly = res.pop("_hourly")
        if args.hourly:
            (args.outdir / "hourly").mkdir(exist_ok=True)
            hourly.to_csv(args.outdir / "hourly" / f"{k}.csv")
        ok = res["max_abs_hourly_residual_W"] <= args.residual_tol_w
        if not ok:
            failures.append(k)
        rows.append({"case": k, "label": label, "changed_assumption": changed,
                     **res, "closure_ok": ok})
        print(f"{k:16s} heat {res['heating_kWh']:9.2f}  cool {res['cooling_kWh']:8.2f}  "
              f"latent {res['latent_estimate_kWh']:6.2f}  "
              f"max|r| {res['max_abs_hourly_residual_W']:.2e} W  "
              f"({time.time() - t0:.0f} s)")

    cols = ["case", "label", "changed_assumption", "heating_kWh", "cooling_kWh",
            "sensible_total_kWh", "latent_estimate_kWh", "thermal_bridge_loss_kWh",
            "storage_charge_kWh", "storage_discharge_kWh", "storage_net_kWh",
            "annual_residual_kWh", "max_abs_hourly_residual_W",
            "input_throughput_kWh", "exposed_perimeter_after_sanitise_m",
            "n_hours", "closure_ok"]
    with (args.outdir / "sensitivity.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: (f"{r[c]:.6g}" if isinstance(r[c], float) else r[c])
                        for c in cols})

    base = next((r for r in rows if r["case"] == "base"), None)
    if base is not None:
        raw = build_bui()
        area = float(raw["building"]["net_floor_area"])
        rec = {k: v for k, v in base.items() if k not in ("label",)}
        rec.update({
            "net_floor_area_m2": area,
            "sensible_per_area_kWh_m2": base["sensible_total_kWh"] / area,
            "sensible_plus_latent_estimate_kWh":
                base["sensible_total_kWh"] + base["latent_estimate_kWh"],
            "sensible_plus_latent_estimate_kWh_m2":
                (base["sensible_total_kWh"] + base["latent_estimate_kWh"]) / area,
            "construction_year_band": raw["building"]["construction_year"],
            "q50_band_default": _q50_for_construction_age(raw),
            "q50_used_declared_assumption":
                raw["building_parameters"]["ventilation"]["envelope_permeability_q50"],
            "neighbour_setpoints_C": {z["name"]: z.get("setpoint")
                                      for z in raw["adjacent_zones"]},
            "weather_file": args.weather.name,
            "note": ("The latent figure is a post-processed estimate conditional "
                     "on sensible operation; it is not part of the sensible "
                     "total compared with EnergyPlus."),
        })
        (args.outdir / "base_case.json").write_text(
            json.dumps(rec, indent=2), encoding="utf-8")

    print(f"\nwritten -> {args.outdir / 'sensitivity.csv'}")
    if failures:
        raise SystemExit(f"hourly closure above {args.residual_tol_w} W in: {failures}")


if __name__ == "__main__":
    main()
