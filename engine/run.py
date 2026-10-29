"""Run one annual ISO 52016-1 simulation with the revised pyBuildingEnergy engine.

Usage:
    python run.py                                   # default: Apt 305, repaired engine
    python run.py buildings/apt305_au_combined.json
    python run.py my_building.json --weather weather/other.epw --out results/my_building.csv

From Python or a notebook:
    from run import load_building, simulate
    b = load_building("buildings/apt305_repaired.json")
    b["building_surface"][0]["u_value"] = 0.5
    hourly = simulate(b, "weather/other.epw")
"""
import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pybuildingenergy.source import utils as u
from pybuildingenergy.source.check_input import sanitize_and_validate_BUI

DEFAULT_BUILDING = HERE / "buildings" / "apt305_repaired.json"
DEFAULT_WEATHER = HERE / "weather" / "AUS_VIC_Melbourne-Essendon.Fields.958660_TMYx.2011-2025.epw"


def load_building(path):
    """Read a building JSON file into a Python dict you can edit."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def prepare(building):
    """Return an engine-ready copy of a building dict."""
    b = copy.deepcopy(building)
    # The engine expects numpy arrays for the adjacent-zone element lists.
    for zone in b.get("adjacent_zones", []):
        for key in ["area_facade_elements", "typology_elements",
                    "transmittance_U_elements", "orientation_elements"]:
            if key in zone:
                zone[key] = np.asarray(zone[key])
    return b


def simulate(building, weather=DEFAULT_WEATHER):
    """Run one year for a building dict (or JSON path) and EPW file.

    Returns the hourly results DataFrame; Q_H and Q_C are in W.
    """
    if not isinstance(building, dict):
        building = load_building(building)
    clean, issues = sanitize_and_validate_BUI(prepare(building), fix=True)
    errors = [i for i in issues if i["level"] == "ERROR"]
    if errors:
        raise ValueError(f"Input errors: {errors}")
    return u.ISO52016.Temperature_and_Energy_needs_calculation(
        clean, weather_source="epw", path_weather_file=str(weather))[0]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("building", nargs="?", default=str(DEFAULT_BUILDING), help="building input JSON")
    p.add_argument("--weather", default=str(DEFAULT_WEATHER), help="EPW weather file")
    p.add_argument("--out", help="hourly results CSV (default: results/<building>.csv)")
    args = p.parse_args()

    try:
        hourly = simulate(args.building, args.weather)
    except ValueError as e:
        sys.exit(str(e))

    out = Path(args.out) if args.out else HERE / "results" / (Path(args.building).stem + ".csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    hourly.to_csv(out, index=False)

    heating = hourly.Q_H.sum() / 1000
    cooling = hourly.Q_C.sum() / 1000
    print(f"Building : {Path(args.building).name}")
    print(f"Weather  : {Path(args.weather).name}")
    print(f"Heating  : {heating:8.2f} kWh/year")
    print(f"Cooling  : {cooling:8.2f} kWh/year")
    print(f"Total    : {heating + cooling:8.2f} kWh/year")
    print(f"Hourly results written to {out}")


if __name__ == "__main__":
    main()
