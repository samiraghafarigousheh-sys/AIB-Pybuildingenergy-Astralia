# October methodology revision

This package implements the three-stage experiment in the revised methodology.
EnergyPlus 24.1.0 algorithms are unchanged. Results describe ideal sensible energy
need for assumed inputs, not actual electricity consumption or measured accuracy.

## Reproduce

Use Python 3.12 and an installed EnergyPlus 24.1.0 executable. Create a virtual
environment, install `requirements-revision.txt`, and run from this directory:

```bash
python -m pytest tests/test_revision_design.py tests/test_internal_gains_adjacency.py tests/test_conditioned_adjacent_zones.py tests/test_ground_contact_area.py tests/test_dynamic_window_properties.py tests/test_dynamic_surface_coefficients.py -q
python run_revision.py --energyplus /absolute/path/to/energyplus --outdir revision_results
python audit_revision.py
```

The source is supplied in `pybuildingenergy/src`. Do not replace it with another
upstream installation. The original engine snapshot is in `original`; only the
worker's calendar adapter changes its execution. Its thermal equations are intact.
The original source commit is 2e6e910c1297ff3e88bad3184a4f1e74e1a93815.
The corrected starting point is the September 29 Australian code archive.

## What changed

1. Numeric construction years resolve to the existing provisional age bands.
   For example, 2006 now gives q50=11, consistent with `2006-today`.
2. Optional prescribed stack-driver temperature and multiplier rounding allow
   both engines to receive identical weather-driven infiltration. Omitting these
   options retains the existing indoor-temperature feedback behaviour.
3. A new runner explicitly separates implementation repairs, the solar/convection
   factorial, and the four Australian input configurations. It saves inputs,
   reference files, hourly outputs, error metrics, checks and source hashes.
4. Construction inputs are derived from the archived illustrative material layers.
   The ISO `class_i` allocation is retained. The experimental layer-network
   override is never enabled in these comparisons.
5. The window pane setting is held at two across every comparison; the earlier
   construction script changed it to one. Pane count is an optical scenario
   assumption, not a verified property of the apartment.

## Comparison design

- Stages 1 and 2: diagnostic zero-capacity construction, q50=4, prescribed
  weather-dependent infiltration, one fixed EnergyPlus reference.
- Stage 1: original, repaired, and a deliberate no-infiltration ablation.
- Stage 2: repaired fixed methods, angular only, convection only, both.
- Stage 3: both optional methods retained; q50=4 versus 11 crossed with the
  diagnostic construction versus illustrative material-derived resistance and
  capacity. Each physical scenario has its own matched EnergyPlus input file.
- Sensitivity: q50=14 and constant versus weather-dependent infiltration at 11.
- Reproduction: the historical q50=14 constant-flow, fixed-method result.

The q50=4 starting value is a retained historical low-leakage scenario. The
q50=11 regional value is the provisional 2006 age-band assumption. Neither is a
measurement, and the lookup table is not an empirically calibrated age model.

The weather multiplier uses outdoor temperature and station wind with a prescribed
20 C stack temperature, rounded to six decimals before application. This is an
explicit controlled-input mode. It is not a prediction of measured infiltration.
Local facade wind remains the separate input to external convection.

## Construction interpretation

The reference construction is the original diagnostic zero-capacity model. The
material-based configuration restores heat storage and updates resistance together.
Its effect cannot be attributed to material resistance alone or capacity alone.
The model retains ISO capacity classes: merely supplying layers does not make it
sensitive to their order when total R and C are unchanged. The EnergyPlus reference
retains explicit layers. Actual apartment layers remain unverified.

## Output interpretation

`comparison.csv` includes annual heating, cooling, totals, bias, hourly RMSE and
MAE. Percent bias is undefined when the EnergyPlus result is zero. A successful
`COMPLETE.json` requires finite full-year outputs, corrected balance residuals
below 1e-6 W, unchanged references, and equal gains and airflow across Stage 2.
`audit_revision.json` provides additional independent checks. Tests verify the
implementation, not accuracy for Australian housing. No calibration is performed.

The original legacy runners remain for provenance; use `run_revision.py` for this
methodology. Older archived results must not be mixed into the new comparison.

To regenerate the manuscript formats after running the audit, run `python build_results.py`.

To regenerate the complete Results, Discussion and Conclusion, run `python add_figures.py` followed by `python append_discussion.py`. Discussion source is `AIB_Discussion_Conclusion.md`.
