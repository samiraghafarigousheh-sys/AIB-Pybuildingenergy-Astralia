# Exact corrections to the pasted manuscript

These replacements refer to the manuscript pasted in the conversation, not an older PDF. Search for the quoted text: numeric line numbers would change with Overleaf formatting. No annual simulation result is altered by these edits.

## Issue 2 — reference-model documentation

The original appendices explain the ISO boundary treatment, airflow and material inputs, but do not fully specify the EnergyPlus implementation. The revised `AIB_Appendices_Overleaf.tex` adds Appendix D, checked against the saved IDFs, EIO reports and source. It documents:

- `Material:NoMass` for diagnostic opaque elements, while distinguishing their zero capacity from retained zone/internal storage.
- Constant 20 °C `OtherSideCoefficients` boundaries, not simulated neighbouring zones.
- Operative control with 0.5 radiant weighting, while acknowledging different radiant-temperature calculations.
- Simple glazing, U=5.4 and frame-adjusted SHGC=0.4875; this is not explicit two-pane optical equivalence.
- TARP interior convection, DOE-2 exterior convection, conduction transfer functions, and FullInteriorAndExterior solar distribution.
- Continuous ventilation, prescribed infiltration schedules and sensible-load extraction.

Replace this sentence in Section 3.3:

> Generated input files align geometry, gains, setpoint schedules, operative-temperature control, weather and prescribed airflow where supported.

with:

```latex
Generated input files use common geometry, internal-gain schedules,
temperature setpoint schedules, weather and prescribed airflow.
Both engines use operative-temperature control with equal air and
radiant weighting, although their radiant-temperature and heat-transfer
formulations differ. Appendix~\ref{app:ep_alignment} documents the
EnergyPlus constructions, neighbouring boundaries, glazing, control
and surface-exchange settings, and identifies the remaining differences.
```

After this sentence in Section 3.1:

> This deliberately removes heat storage so that implementation and boundary-condition effects can be examined more directly.

replace that sentence with:

```latex
This removes heat storage in the opaque envelope elements so that
implementation and boundary-condition effects can be examined more
directly. The models retain zone/internal storage; its representation
is described in Appendix~\ref{app:ep_alignment}.
```

Keep `\input{AIB_Appendices_Overleaf}` and replace the old appendix file with the supplied revised file. It includes `\appendix`; do not add a second appendix command.

## Issue 3 — the ventilation rate has no established physical justification

The source sets `flow_rate_per_person: 2.0` but explicitly labels it L/(s m²). The executed `occupancy` branch uses it as an area-based flow, giving 2 × 20 / 1000 = 0.040 m³/s = 2.67 ACH. No measurement or cited design requirement supporting that chosen value was found. Do not invent one, and do not replace the value in the paper while leaving the simulations unchanged.

In Section 3.4.1, replace:

```latex
Ventilation is set to $0.040\text{ m}^3/\text{s}$ and the leakage input is $q_{50} = 4\text{ m}^3/(\text{h}\cdot\text{m}^2)$.
```

with:

```latex
Designed ventilation is retained at $0.040\,\mathrm{m^3/s}$ from the
case-study input, equivalent to $2.67\,\mathrm{h^{-1}}$ for the
$54\,\mathrm{m^3}$ zone. This continuous rate is an unverified diagnostic
assumption, not a measured airflow or a demonstrated design requirement.
It is held fixed in both engines to isolate the tested changes.
The diagnostic leakage input is
$q_{50}=4\,\mathrm{m^3/(h\,m^2)}$.
```

In Table 1, replace:

```latex
Ventilation & 2.0\,l/(s\,m$^2$) \\
```

with:

```latex
Designed ventilation & 2.0\,L/(s\,m$^2$), continuous; assumed \\
```

Add after the Discussion sentence ending “continuous designed ventilation” (or replace the existing leakage sentence and its following generalisation sentence together):

```latex
Leakage had a modest effect under the apartment's small outdoor-exposed
envelope and assumed continuous ventilation of
$0.040\,\mathrm{m^3/s}$. The ventilation rate was retained for the
controlled diagnostic comparison, but its suitability for the occupied
apartment was not established. The leakage result is therefore conditional
on this assumption and should not be generalised to more exposed dwellings
or different ventilation regimes.
```

This supports a diagnostic computational paper. If claiming representative actual-apartment demand, measured/design-based ventilation and reruns would still be required.

## Issue 4 — remove the unsupported construction-age inference

Keep q50=4, 11 and 14 as explicit illustrative sensitivity inputs. Remove the historical age-band table from the paper; do not replace its numbers with invented literature-derived values. The final runner explicitly sets these inputs, so this change of interpretation requires no simulation rerun.

In Literature Review subsection “Australian inputs and the scope of adaptation”, replace the entire paragraph beginning “The present study uses age-banded leakage scenarios” with:

```latex
The present study examines explicitly prescribed leakage scenarios rather
than predicting airtightness from construction age. Australian evidence
motivates testing leakage variability, but the selected permeability
values are illustrative assumptions and are not measured properties of
the apartment. Measurements reported as air changes per hour at 50 Pa
require conversion using the corresponding tested volume and envelope
area. Whole-unit apartment tests may also include shared-boundary leakage,
whereas the present model includes outdoor-envelope leakage only.
```

In Section 3.6.1, KEEP the first paragraph reporting the CSIRO studies. Replace EVERYTHING from “The project adapts this evidence into a construction-age lookup table” through the end of Table `tab:AU_leakage` with:

```latex
Three envelope-permeability values are prescribed explicitly:
$q_{50}=4$, 11 and 14 $\mathrm{m^3/(h\,m^2)}$ at 50 Pa.
The value 4 retains the low-leakage diagnostic input used in Stages~1
and~2; 11 defines the primary higher-leakage scenario, and 14 provides
an additional sensitivity case. These are illustrative scenario inputs,
not measured apartment properties, calibrated age-based estimates or
representative averages for Australian construction periods.

Australian airtightness evidence motivates examining leakage variability
but does not establish these particular values for the case study.
All final simulations set permeability explicitly, so the provisional
construction-age lookup retained in the archived code does not determine
the reported results. Appendix~\ref{app:age} records the scope of these
assumptions, and Appendix~\ref{app:infiltration} describes the conversion
to prescribed outdoor airflow.
```

In Section 3.6.3, replace:

> The two-factor comparison crosses $q_{50}=4$ and 11 with diagnostic and material-derived construction.

with:

```latex
The two-factor comparison crosses the explicit permeability scenarios
$q_{50}=4$ and 11 with diagnostic and material-derived construction.
```

In Section 4.4, replace “Australian leakage only” in the table row with “Higher leakage only”. Replace “Australian construction only” with “Material-derived construction only”, and “Combined Australian inputs” with “Combined input scenario”. The numerical values stay unchanged. Keeping “Australian input scenarios” as the stage heading is possible if the text clearly limits the regional claim, but “Leakage and construction input scenarios” is more precise.

The supplied appendix already replaces C1 with explicit-scenario wording and removes its historical age table. The engine's archived lookup is preserved for provenance; these edits do not claim it is calibrated.

## Issue 5 — exact consistency corrections

### Abstract: number of runs

Find:

```latex
Twelve annual
pyBuildingEnergy runs and seven EnergyPlus references use controlled weather, schedules
and scenario inputs.
```

Replace with:

```latex
Twelve main annual pyBuildingEnergy runs and seven EnergyPlus references
use controlled weather, schedules and scenario inputs. Sixteen additional
annual runs examine the effects and interactions of four Stage~1 change groups.
```

Also replace:

```latex
Implementation repairs reduce annual sensible demand from 2408.74 to
```

with:

```latex
Combined implementation and boundary-condition changes reduce annual
sensible demand from 2408.74 to
```

### Incorrect Results cross-reference

In Section 3.6.3 find:

```latex
Section 4.3 reports the matched-reference results and interaction.
```

Replace with:

```latex
Section~\ref{subsec:results_australian_inputs} reports the
matched-reference results and interaction.
```

This resolves to Section 4.4 in the current manuscript.

### ISO edition and wording

Find the sentence beginning:

```latex
The international Organization for Standardization (ISO)~52016-1:2018 standard~\cite{iso52016} is the current European and
internationally adopted simplified hourly method, replacing the earlier EN~ISO~13790
5R1C single-capacitance model with a multi-node resistance--capacitance network that
more accurately represents the thermal mass and dynamic behaviour of building
envelopes.
```

Replace the whole sentence with:

```latex
The hourly method in ISO~52016-1:2017~\cite{iso52016}, published by the
International Organization for Standardization, represents building
elements using a multi-node resistance--capacitance network.
It provides a more detailed representation of envelope heat storage
than the five-resistance, one-capacitance simple hourly method in
ISO~13790.
```

### Rounding: do not alter the results

Add to the end of the Results opening paragraph that defines units:

```latex
Totals and changes are calculated from unrounded outputs; sums or
differences of displayed values may therefore differ by 0.01~kWh.
```

Keep these values:

- Leakage-only total: **139.78**, from 139.784113 kWh.
- Sequential infiltration increment: **+5.23**, from 5.226135 kWh.

The earlier suggestion that these could be numerical errors is resolved by the archived full-precision outputs.

### EnergyPlus documentation citation

Replace the COMPLETE `energyplus_ior` bibliography item with:

```latex
\bibitem{energyplus_ior}
{EnergyPlus Development Team}.
\newblock \emph{EnergyPlus Input--Output Reference, Version~24.1}.
\newblock U.S. Department of Energy.
\newblock \url{https://bigladdersoftware.com/epx/docs/24-1/input-output-reference/overview.html}.
```

The updated Appendix D cites this item. Move this item in the manually ordered bibliography to its first-citation position if required by the venue.

### Additional discrepancy found in Appendix C4

The main infiltration-off JSON actually sets q50=0. The separate Stage 1 switch experiment retains q50=4 and disables the pathway. Their loads match exactly. The updated appendix distinguishes them; the previous wording claiming both retained q50=4 was inaccurate. No load values need changing.

## Issue 6 — code release

The public repository checkout examined during this review was at `0a383e6` and contained older results. The final main archive and Stage 1 archive have been combined without conflicting common files. No revised thermal source has been changed during packaging.

Upload the supplied folder intact as `manuscript_reproduction/` in:

https://github.com/samiraghafarigousheh-sys/AIB

The folder includes both engines' input/output evidence, original and revised ISO source, scripts, weather, tests, dependency pins, a checksum manifest and reproduction instructions. EnergyPlus 24.1.0 itself must be installed separately. The revised code is identified by verified hashes; do not cite the old public HEAD as if it generated these results.

After uploading, add before the appendices:

```latex
\section*{Code and data availability}
The simulation source, archived original implementation, scenario inputs,
weather record, EnergyPlus input files, hourly outputs and verification
scripts are provided in the \nolinkurl{manuscript_reproduction} directory
of the project repository:
\url{https://github.com/samiraghafarigousheh-sys/AIB}.
The package README describes reproduction using Python~3.12 and
EnergyPlus~24.1.0. Source and evidence checksums identify the supplied
files; Appendix~\ref{app:provenance} records the baseline provenance.
```

This statement should be inserted only after the folder is actually uploaded. Before submitting, pin the link/citation to the resulting real commit or release. The package is ready for that upload but this task has not published it or created a permanent release.

Replace the old notebook bibliography entry `aibteam_comparison` if you intend to cite the code:

```latex
\bibitem{aibteam_comparison}
{AIB Research Team}.
\newblock pyBuildingEnergy manuscript reproduction package.
\newblock Source code, simulation inputs and archived results, 2026.
\newblock \url{https://github.com/samiraghafarigousheh-sys/AIB}.
```

Add `\cite{aibteam_comparison}` to the code-availability paragraph if retaining that bibliography entry. After upload, add the actual commit identifier or release DOI; none has been invented here.

## Issue 7 — exact editorial and LaTeX corrections

| Find exactly | Replace with |
|---|---|
| `\textbf{Keywords:} SO 52016-1;` | `\textbf{Keywords:} ISO 52016-1;` |
| `\subsection{Stage 1:implementation repair}` | `\subsection{Stage 1: Implementation and boundary-condition changes}` |
| `\subsubsection{Ground contact ventilation and infiltration}` | `\subsubsection{Ground contact, ventilation and infiltration}` |
| `\subsubsection{Evaluation of the two hanges}` | `\subsubsection{Evaluation of the two changes}` |
| `\caption{case study geometry schematic reproduced from the supplied case documentation.}` | `\caption{Case-study geometry schematic reproduced from the supplied case documentation.}` |
| `\caption{Case-study photographs, plan and thermal-boundary.}` | `\caption{Case-study photographs, plan and thermal boundaries.}` |
| `Section 4.1 reports the results` | `Section~\ref{subsec:results_repairs} reports the results.` |
| `Section 4.2 reports annual and hourly outcomes.` | `Section~\ref{subsec:results_physical_methods} reports annual and hourly outcomes.` |
| `q50 = 4` | `$q_{50}=4\,\mathrm{m^3/(h\,m^2)}$` in the Stage 2 evaluation paragraph |

The duplicate punctuation in “construction period. .” disappears when the Section 3.6.1 replacement above is made. If retaining that paragraph, replace it with “construction period.”

Remove literal line-end word splits in the source:

- `representa-` followed by a newline and `tion` → `representation`.
- `solar-` followed by a newline and `angle-dependent` → `solar-angle-dependent` on one source line.
- `southern-` followed by a newline and `hemisphere` → `southern-hemisphere` on one source line.
- `neighbour-` followed by a newline and `aware` → `neighbour-aware` on one source line.

These are source-formatting fixes; LaTeX should handle printed line breaks.

### Equation reference

Add `\label{eq:balance}` immediately after `\begin{equation}` for the energy-balance residual. Replace:

```latex
Equation~4 defines the hourly energy-balance residual, r.
```

with:

```latex
Equation~\ref{eq:balance} defines the hourly energy-balance residual, $r$.
```

### Title

The current title has an awkward hyphen and implies a wider residential scope than the single case supports. Recommended complete replacement:

```latex
\title{
    \vspace{-0.5cm}
    \LARGE\textbf{Revising pyBuildingEnergy for an Australian Apartment:
    Implementation Checks and Controlled Comparison with EnergyPlus}
    \vspace{0.3cm}
}
```

Use the same title on the appendix title page if retaining that page.

### Authors and affiliations

`\author{AIB Research Team...}` is not a complete author block for most non-anonymised submissions. Enter the actual agreed authors, affiliations, corresponding-author email and any ORCIDs the venue requires. Their names and order cannot be inferred reliably from the code or the older notebook citation. For anonymous review, follow the venue's anonymisation instructions instead.

### Compilation and bibliography

Find:

```latex
%  Compile: pdflatex → pdflatex → bibtex → pdflatex → pdflatex
```

Replace with:

```latex
% Compile: pdflatex -> pdflatex (manual thebibliography; no BibTeX step)
```

Delete:

```latex
\bibliographystyle{unsrt}
```

It does not sort manually written `\bibitem` entries. If the journal uses citation-order numbering, reorder the entries manually or convert the references to a `.bib` database. In the current manuscript, `karlsson2000` first appears before the CSIRO paragraphs in Section 3.6, but after CSIRO citations already made in Section 2; place it after the last earlier first-cited source (`yourhomeairtightness`) and before sources first cited only later.

Delete the second command:

```latex
\providecommand{\doi}[1]{\url{https://doi.org/#1}}
```

The preamble already defines `\doi`; this duplicate is harmless but unused. Keep the original `\newcommand`.

Delete the stale bibliography comment claiming entries are “not cited in the supplied excerpt”. For the final main text plus updated appendix, remove bibliography entries that are never cited, or add a genuine relevant citation where they support the method. Do not add citations just to retain an unused reference.

The `eurac2024` entry lacks version/date/location. The baseline's exact source provenance is now documented in the appendix and reproduction folder, but a complete software citation is still needed. Use verified metadata for the exact upstream version, rather than assuming the existing version-2.0.2 Zenodo item identifies the archived 2.0.3-derived baseline. The actual baseline commit and upstream repository URL can be used when no matching version DOI is available.

### Venue-dependent items, not automatic errors

The contents page and appendix title page are not LaTeX faults. Retain or remove them according to the target venue; the requested appendix title page may remain. Similarly, conflict-of-interest, funding, author-contribution and data statements must reflect real information and the venue's requirements. The venue has not been specified, so these are submission checks rather than proven defects.

## What was verified

- All 43 main-run source hashes and all 85 overlapping Stage 1 source/input hashes match.
- Twelve main annual totals and hourly RMSE values were recomputed from saved hourly outputs.
- All sixteen repair combinations, endpoint loads and order-averaged allocations were checked.
- Saved SQL/input airflow checks passed for all seven EnergyPlus references.
- Pinned Python requirements installed successfully.
- 129 focused tests passed.
- A fresh 8760-hour repaired ISO run reproduced archived hourly loads exactly (maximum difference 0 W).
- Updated appendix LaTeX compiled in an isolated wrapper. Main-document references require the full Overleaf manuscript.

Other annual ISO runs and EnergyPlus were not rerun during this packaging task. No measured-building validation is claimed.
