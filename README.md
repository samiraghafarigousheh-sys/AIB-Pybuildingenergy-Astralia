# AIB-Pybuildingenergy-Astralia
Adaptation of pyBuildingEnergy (ISO 52016-1) for Australian residential buildings, including implementation repairs, optional physical methods, local building and weather inputs, and benchmarking against EnergyPlus.

## Contents

`manuscript_reproduction/` holds the revised pyBuildingEnergy source, the archived original source, simulation inputs, EnergyPlus reference models, saved hourly outputs and the verification scripts behind the manuscript. See `manuscript_reproduction/README.md`. The same package is attached to release v1.0.0 as `AIB_Repository.zip`.

Quick check (Python 3.12, no EnergyPlus needed):

```bash
cd manuscript_reproduction
pip install -r requirements-revision.txt
python verify_release.py   # source hashes, saved metrics, and all 146 values quoted in the manuscript
```
