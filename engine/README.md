# pyBuildingEnergy (Australian revision): ready-to-run engine

This folder holds only what you need to run the latest revised engine: the engine code, a Melbourne weather file, two example buildings and a run script. The paper's evidence, tests and EnergyPlus models stay in `../manuscript_reproduction/`.

## Contents

| Path | What it is |
|---|---|
| `colab_new_building.ipynb` | Google Colab notebook where every building input (location, surfaces, neighbours, setpoints, ventilation, gains, schedules, model options) and the weather file are set in commented cells. |
| `run.py` | Runs one annual simulation. It prints annual heating and cooling and writes the hourly results. |
| `pybuildingenergy/` | The revised ISO 52016-1 engine, copied from `manuscript_reproduction/pybuildingenergy/src/pybuildingenergy/` without the example charts and images. |
| `buildings/apt305_repaired.json` | Apartment 305, Carlton (Melbourne) with all repairs. This is the paper's main case: **131.76 kWh/year**. |
| `buildings/apt305_au_combined.json` | The same apartment with Australian constructions and leakage (q50 = 11): **76.51 kWh/year**. |
| `weather/` | Melbourne-Essendon TMYx weather file (the canonical file used in the paper). |
| `requirements.txt` | Python packages the engine needs. |
| `LICENSE.md` | pyBuildingEnergy license. Keep it with the code. |

## Setup (once)

Use Python 3.12 or newer.

```bash
cd engine
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python run.py                                    # Apt 305, main paper case
python run.py buildings/apt305_au_combined.json  # Australian construction + leakage
python run.py my_building.json --weather weather/other.epw --out results/my_run.csv
```

Example output:

```
Heating  :   113.22 kWh/year
Cooling  :    18.54 kWh/year
Total    :   131.76 kWh/year
Hourly results written to results/apt305_repaired.csv
```

The hourly CSV has 8760 rows. Useful columns:

- `Q_H` and `Q_C`: heating and cooling need, in W.
- `T_op` and `T_air`: indoor operative and air temperature.
- `T_ext`: outdoor temperature.
- Heat-balance terms such as `Q_tr_*`, `Q_ve`, `Q_solar_gains` and `Q_internal_gains`.

## Model your own building

The easiest way is `colab_new_building.ipynb`: open it in Google Colab (File → Open notebook → GitHub), edit Steps 2–10 and run. Unchanged, it gives 131.76 kWh/year.

Or, without the notebook:

Copy one of the JSON files in `buildings/` and edit it:

- `building`: location, floor area, height, construction year and class.
- `building_surface`: one entry per wall, floor, ceiling or window. Each entry has its area, U-value, orientation and type (`opaque`, `transparent` or `adjacent`).
- `adjacent_zones`: neighbouring spaces that `adjacent` surfaces connect to.
- `building_parameters`: setpoints, ventilation and infiltration (`envelope_permeability_q50`), internal gains, heating and cooling schedules, and `simulation_options`.

For another location, put its `.epw` file in `weather/`, pass it with `--weather`, and update `latitude` and `longitude` in the building file.

## Provenance

The code here is identical to `manuscript_reproduction/pybuildingenergy/src/pybuildingenergy/` (only `Result/`, `charts/` and `assets/` were left out). Running both example buildings reproduces the saved results in `manuscript_reproduction/revision_results/` (hourly difference 0 W). If you change the engine in one place, copy the change to the other.
