# AIB-Pybuildingenergy-Astralia
Adaptation of pyBuildingEnergy (ISO 52016-1) for Australian residential buildings, including implementation repairs, optional physical methods, local building and weather inputs, and benchmarking against EnergyPlus.

## Contents

`engine/` is the ready-to-run engine: only the revised source, Melbourne weather, two example buildings and a `run.py` script. Use it to run simulations. See `engine/README.md`.

```bash
cd engine
pip install -r requirements.txt
python run.py   # Apartment 305, Melbourne: 131.76 kWh/year
```

`manuscript_reproduction/` holds the revised pyBuildingEnergy source, the archived original source, simulation inputs, EnergyPlus reference models, saved hourly outputs and the verification scripts behind the manuscript. See `manuscript_reproduction/README.md`. The same package is attached to release v1.0.0 as `AIB_Repository.zip`.

Quick check (Python 3.12, no EnergyPlus needed):

```bash
cd manuscript_reproduction
pip install -r requirements-revision.txt
python verify_release.py   # source hashes, saved metrics, and all 146 values quoted in the manuscript
```
