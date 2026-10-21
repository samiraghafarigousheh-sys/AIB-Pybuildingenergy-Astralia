# Wording needed to align the methodology with the executed comparisons

## Initial leakage assumption

Stages 1 and 2 retain an explicit q50 of 4 m³/(h m²), representing the historical
low-leakage scenario. Stage 3 changes this input to the provisional q50 of 11 for
the recorded construction year of 2006. The value of 14 is retained as a sensitivity
case. These values are assumptions; no measured airtightness is available for the
apartment, and the age-band lookup is not a calibrated national relationship.

## Weather-dependent infiltration

For the controlled comparisons, both engines receive the same hourly infiltration
multiplier calculated from weather-station wind, outdoor temperature and a
prescribed indoor reference temperature of 20 °C. Multipliers are rounded to six
decimal places before application. This prevents differences in simulated indoor
temperature from changing the airflow input between engines. The native model's
indoor-temperature feedback remains available outside this controlled mode.

## Construction inputs

The Stage 3 reference retains the diagnostic construction with zero opaque heat
capacity. The Australian construction scenario replaces this with the existing
illustrative brick-veneer, partition and slab material inputs. Resistance and total
heat capacity are calculated from the materials, while the ISO class_i allocation
is retained. This changes both resistance and storage relative to the diagnostic
case. It does not resolve layer order within the ISO network, and must not be
described as reproducing the location of each material's thermal capacity. The
construction inputs are scenarios, not verified layers of Apartment 305.

## Reference and optical consistency

The four Stage 2 variants share one unchanged EnergyPlus reference. Stage 3 changes
the physical input assumptions, so each leakage/construction configuration has a
corresponding EnergyPlus model. EnergyPlus algorithms are unchanged. All comparisons
retain the same two-pane setting for the angular optical approximation; this is a
declared assumption rather than a pane count inferred from U-value.

## Reported metrics

Report annual sensible heating, cooling and their sum, together with signed annual
bias, hourly RMSE and MAE over 8760 hours. Report zero-reference cooling as an
absolute difference without a percentage. Exclude the unvalidated humidity diagnostic
from the primary energy totals. Corrected hourly heat-balance residuals must remain
below 1e-6 W. December 2025 provides warm-up; the reporting schedules use 2026 with
no holiday overrides.

## Individual implementation repairs

The baseline comparison measures the repair package. The infiltration-off case
isolates the contribution of infiltration. Unit and diagnostic checks establish
gain accounting, adjacency, ground routing and coefficient behaviour, but do not
assign independent annual energy savings to every repair. Do not reuse the older
cumulative fourteen-step sequence as an isolated causal decomposition.
