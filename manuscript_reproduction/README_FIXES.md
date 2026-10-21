# AIB input-handling fixes

Three silent defects in how the engine reads its inputs, plus one input typo. None changes any result in the paper, provided the engine and input changes are applied **together** (verified; see below).

## What the patch changes

| # | Defect | Where | Fix |
|---|---|---|---|
| 1 | Internal-gain `full_load` values under `building_parameters.internal_gains` were ignored; the EN 16798-1 table always applied. Inherited from upstream. | `source/ventilation.py`, `internal_gains()` | Read overrides from `building_parameters.internal_gains` when no top-level list exists. |
| 2 | `building_parameters.climate_parameters.coldest_month` was ignored. | `source/utils.py`, `_resolve_coldest_month()` | Also read the `climate_parameters` location; a top-level value still wins. |
| 3 | When identical windows are merged into one element, the single-zone solvers looked for a shading column under the merged name, found none, and used F_sh = 1. Inherited from upstream. | `source/utils.py`, aggregation and both single-zone solvers | Aggregation records `aggregated_from` (name, area); new `_window_shading_series()` area-weights the source windows' `W_<name>` columns. |
| 4 | The example key `overhang_proprieties` was never read. | `source/utils.py`, `Shading_reduction_factor_window()` | Accept the misspelling with a warning. |
| — | Case input declared gains (8/5/3 W/m²) and an overhang that were never applied. | `examples/apt305_building.py` | Declare the executed gains (4.2/3.0/0 W/m²); set `shading: False` to match the EnergyPlus model. |

Why the input change is required: with fixes 1 and 3–4 alone, the engine would start honouring the old declared gains and overhang, and every result would change.

## Apply

From the root of the AIB repository:

```bash
git apply aib_input_handling_fixes.patch
```

Files touched: `utils.py`, `ventilation.py`, `examples/apt305_building.py`, and the new `tests/test_input_key_paths.py`.

## Regenerate the archived evidence

The patch changes executed source files, so the recorded source hashes no longer match and `verify_release.py` will stop at the hash check until the runs are regenerated. With EnergyPlus 24.1.0:

```bash
cd manuscript_reproduction
python run_revision.py --energyplus /path/to/energyplus --outdir revision_results
python audit_revision.py
python run_stage1_attribution.py
python verify_release.py
python add_figures.py
```

Expected outcome: every annual energy, RMSE, attribution value and figure is identical to the current archive.

## Verification already done

- All 12 main ISO cases rerun with the patched engine and regenerated inputs: hourly loads identical to the archive (maximum difference 0 W).
- All 16 Stage 1 switch combinations rerun: identical to the archive.
- Regenerated EnergyPlus inputs differ from the archived files in one line only: the value of the unreferenced schedule `Activity_W`, which no EnergyPlus object uses. EnergyPlus results are therefore unchanged.
- Test suite: 261 passed, 17 skipped (previously 249 passed). The 12 new tests fail on the unpatched engine (7 defect tests) and pass after the patch.
- With an overhang active, merged and separate windows now give identical hourly loads (difference about 1e-11 W). Previously, merging removed the shading entirely.

## Effect if you later model the overhang

With the 0.25 m overhang active (and no matching shading in EnergyPlus), the repaired case changes from 18.54 to 15.61 kWh cooling and 131.76 to 128.85 kWh total; window solar gains fall from 810.5 to 711.1 kWh. To include it, add a matching `Shading:Overhang` (or `Shading:Zone:Detailed`) object to the reference IDFs.

## Manuscript

`manuscript_fixes.tex` lists the text changes. Group A is needed for consistency; Group B strengthens the paper; Group C covers small corrections.
