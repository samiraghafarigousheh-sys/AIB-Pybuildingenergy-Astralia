# pyBuildingEnergy: manuscript reproduction package

This folder consolidates the saved final October main comparison and the subsequent sixteen-combination Stage 1 experiment. It supersedes older result sets for the manuscript reporting **2408.74 → 131.76 kWh** against **157.33 kWh**.

## Upload

Upload this folder intact as `manuscript_reproduction/` inside the AIB repository. Keeping it self-contained avoids mixing the final source with the older repository root. Run the commands below from inside this folder. The repository is https://github.com/samiraghafarigousheh-sys/AIB-Pybuildingenergy-Astralia ; the manuscript cites the `AIB_Repository.zip` asset of release v1.0.0. No upload or publication was performed when preparing this package.

All individual files are below 25 MB. For a browser upload, extract the ZIP and upload the folder contents, not the ZIP as the source release. A repository client is more convenient for the full folder. The uncompressed package contains both source and saved evidence.

## What is included

- `pybuildingenergy/src/`: exact revised thermal source used for the saved main runs.
- `original/pybuildingenergy/src/`: archived original thermal source.
- `run_revision.py`, `revision_worker.py`: twelve main runs and seven EnergyPlus references.
- `run_stage1_attribution.py`, `stage1_worker.py`: sixteen repair combinations.
- `revision_results/`: inputs, hourly outputs, reference IDFs, SQL, error logs, comparisons, monthly totals and checks.
- `stage1_results/`: hourly outputs, combinations, attribution and provenance.
- `weather_cache/`: archived weather, including the canonical Essendon EPW.
- `tests/`, `requirements-revision.txt`: checks and pinned direct dependencies.
- `manuscript/AIB_Appendices_Overleaf.tex`: updated appendices, including reference settings and explicit leakage-scenario interpretation.
- `manuscript/Manuscript_Exact_Replacements.md`: exact replacements for the pasted manuscript.
- `verify_release.py`: independently recomputes saved metrics and verifies recorded source hashes.
- `paper_values.py`: recomputes every number quoted in the manuscript (146 values) from the saved evidence, and writes the winter heat-balance table (manuscript Table 5) to `tables/winter_heat_balance.tex`.
- `release_verification.json`, `release_tests.log`, `release_smoke_test.json`: preparation-time verification.

The older manuscript generators and draft sections supplied in the original archive remain for provenance. They predate the latest Stage 1 text and leakage interpretation. Do not overwrite your current main manuscript using `build_results.py` or `append_discussion.py`. `add_figures.py` regenerates the archived numeric figures. The current main manuscript is the author's separately maintained Overleaf document; it is not represented by the older draft files in this archive.

## Verify saved evidence (no EnergyPlus installation required)

Use Python 3.12 in a virtual environment:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-revision.txt
python verify_release.py
```

Verification covers 43 main-run source hashes, 85 overlapping Stage 1 source/input hashes, both weather checksums, annual energies and hourly error metrics for all twelve cases, all sixteen repair combinations, their endpoint equality and order-averaged allocations, and the seven-reference airflow audit. It finishes by running `paper_values.py`, so a pass also means the manuscript text matches the evidence. It verifies archived computational evidence, not empirical accuracy.

## Run the simulations again

Install EnergyPlus **24.1.0** separately. From a fresh copy of this folder:

```bash
python run_revision.py --energyplus /absolute/path/to/energyplus --outdir revision_results
python audit_revision.py
python run_stage1_attribution.py
python verify_release.py
```

Without EnergyPlus, the twelve ISO runs can be regenerated against the archived EnergyPlus references:

```bash
python run_revision.py --reuse-energyplus revision_results --outdir new_results
```

Compare `new_results` with `revision_results`. The archived references are copied, not re-simulated.

On Windows, pass the full path to `energyplus.exe` in quotes. These commands intentionally regenerate the saved output directories, so retain an untouched copy of the archive if preserving the supplied evidence is important. The Stage 1 runner reads `revision_results` and writes `stage1_results`. No engine download or external weather request is required once EnergyPlus and Python dependencies are installed.

Focused tests:

```bash
python -m pytest tests/test_revision_design.py tests/test_internal_gains_adjacency.py tests/test_conditioned_adjacent_zones.py tests/test_ground_contact_area.py tests/test_dynamic_window_properties.py tests/test_dynamic_surface_coefficients.py -q
```

## Verification actually performed during packaging

The pinned requirements installed successfully under Python 3.12. The full suite gives **261 passed, 17 skipped** (`release_tests.log`; all 17 skips are legacy branch-comparison tests that check out `claude/*-fix` development branches not present in this repository). After the input-handling patch (`README_FIXES.md`), all twelve main ISO runs were regenerated with `--reuse-energyplus`: hourly outputs, inputs, `comparison.csv`, `monthly.csv` and `checks.json` were identical to the archive (maximum difference 0 W), and `revision_results/COMPLETE.json` was updated to the patched source hashes. The sixteen Stage 1 runs had already been regenerated with the patched source. EnergyPlus was **not rerun**; its saved inputs, SQL and hourly results were audited. `verify_release.py` and `paper_values.py` (146 manuscript values) pass.

## Interpretation and provenance

Permeability values 4, 11 and 14 m³/(h m²) are explicit illustrative scenarios, not measured apartment leakage or a calibrated construction-age model. The archived age lookup remains for provenance and is not needed by these explicit inputs. The continuous 0.040 m³/s designed ventilation is an inherited diagnostic input without a verified empirical/design basis in the available records.

The baseline project commit is `2e6e910c1297ff3e88bad3184a4f1e74e1a93815`; recorded upstream ancestry is `1236ace2fcc54f570cc4e7686b6fa3c1fa8b0573`. Revised source identity is given by file hashes, not an invented release commit. Once uploaded, cite the actual repository commit or tagged release. Root package version 2.0.3 alone does not identify these changes.

The canonical weather file is `AUS_VIC_Melbourne-Essendon.Fields.958660_TMYx.2011-2025.epw`, SHA-256 `d4453a2fe299304554a4f7ba14b8857cff701dd11f407975627ecd3ee9aaeb4d`. Source download locations are retained in `examples/weather_melbourne.py`.

## Licensing

Retain `pybuildingenergy/LICENSE.md` and the upstream copyright headers. The software license should not be assumed to grant rights over case photographs or third-party weather data. The photographs from the manuscript are not added to this source release.
