# Input reference for `colab_new_building.ipynb`

This guide explains every input in the notebook: what it means, its unit, and which other values the engine accepts. Sections follow the notebook steps.

The values in the notebook describe Apartment 305 in Carlton, Melbourne, the case used in the paper. Run unchanged, they give **113.22 kWh heating + 18.54 kWh cooling = 131.76 kWh/year**. The "Effect" notes below come from test runs that changed one input of that case at a time.

**Conventions used throughout**

| Item | Convention |
|---|---|
| Azimuth | Degrees from north, clockwise: 0 = N, 90 = E, 180 = S, 270 = W |
| Tilt | 90 = vertical wall, 0 = horizontal (floor, ceiling, flat roof) |
| Hourly profiles | 24 values, one per hour starting at midnight (index 0 = 00:00–01:00) |
| Results | `Q_H` and `Q_C` are in W for each hour, so their annual sums are in Wh. Divide by 1000 for kWh. |

---

## Step 2 – General building data (`building`)

| Key | Unit | Meaning | Options / notes |
|---|---|---|---|
| `name` | – | Label for the building | Any text |
| `country` | – | Selects the public-holiday calendar. Used only if `profile_use_holidays` is True. | `"Australia"`, `"Italy"`, or a two-letter country code such as `"AU"`, `"NZ"` or `"GB"` |
| `latitude`, `longitude` | degrees | Site location. Latitude is negative in the southern hemisphere. | Must match the weather file. Latitude also sets the default `coldest_month`. |
| `azimuth_relative_to_true_north` | degrees | Kept for compatibility | Leave at 0. Give each surface its true azimuth instead. |
| `net_floor_area` | m² | Conditioned floor area | Scales internal gains, `occupancy` ventilation and the per-m² results |
| `height` | m | Floor-to-ceiling height | Volume = area × height, unless you add `zone_volume_m3` (below) |
| `n_floors` | – | Number of storeys | Must be > 0 |
| `wall_thickness` | m | Wall thickness | Used only in the ground-floor (ISO 13370) calculation |
| `exposed_perimeter` | m | Perimeter of a slab on ground | **0** for a zone with no ground contact, such as an upper-floor apartment. It also sets the engine's thermal bridges: 0.05 W/(m·K) × perimeter. **Effect:** 5 m added 1.3 kWh heating. |
| `building_type_class` | – | Usage type. Supplies the default internal gains and schedules for anything you leave out in Steps 8–9. | `"Residential_apartment"`, `"Residential_detached_house"`, `"Office"`, `"School"`, `"Kindergarten"`, `"Department_store"` |
| `construction_class` | – | Where the thermal mass sits in each wall (ISO 52016-1, Table B.13) | `"class_i"` mass on the inside (default)<br>`"class_e"` mass on the outside<br>`"class_ie"` split between inside and outside<br>`"class_d"` spread evenly through the wall<br>`"class_m"` mass in the middle<br>No effect when every `thermal_capacity` is 0. |
| `construction_year` | year or band | Used only when `envelope_permeability_q50` is **not** given in Step 7, to choose a default air leakage | A year such as `1985`, or a band such as `"1976-1990"` (see the q50 table in Step 7). **Effect:** with q50 removed, 2006 gives q50 = 11, and heating rose from 113 to 122 kWh. |
| `adj_zones_present` | True/False | Whether Step 5 defines neighbouring zones | |
| `number_adj_zone` | – | How many neighbouring zones | Must equal the number of entries in Step 5 |
| `zone_volume_m3` *(optional)* | m³ | Air volume, if it is not simply area × height | Needed if you use `constant_ach` ventilation components (Step 7) |

---

## Step 3 – Site (`site`)

These settings correct the weather-station wind to the local wind at your building. The local wind is used for the outside surface heat transfer of walls and windows.

| Key | Meaning | Options |
|---|---|---|
| `terrain_class` | Terrain around your building | `"flat_open"` open water or bare flat land<br>`"open_country"` flat open country, airports<br>`"suburban"` urban, suburban or wooded<br>`"city_centre"` large city centres<br>`"as_measured"` use the station wind unchanged |
| `floor_level` | Storey of the zone (1 = ground floor). Higher storeys see more wind. | Integer ≥ 1 |
| `weather_station_terrain` | Terrain around the weather station | Same choices as `terrain_class`. Weather stations are usually at airports, so `"open_country"`. |
| `weather_station_sensor_height_m` | Height of the wind sensor, m | Usually 10 |

**Optional site keys:**
- `surface_height_m`: an explicit height for the local wind. It replaces the height calculated from `floor_level`.
- `storey_height_m`: floor-to-floor height. Defaults to `height`.

Infiltration (Step 7) always uses the **station** wind, not this corrected wind.

---

## Step 4 – Surfaces (`surfaces`)

Create one dictionary for each wall, roof, floor, ceiling or window.

### Keys for every surface

| Key | Unit | Meaning | Options / notes |
|---|---|---|---|
| `name` | – | Unique name | |
| `type` | – | What the surface is | `"opaque"` wall or roof to outdoor air<br>`"transparent"` window or glazed door<br>`"adjacent"` wall, floor or ceiling shared with a neighbouring zone (needs `name_adj_zone`)<br>`"adiabatic"` no heat flow, e.g. a wall to an identical space you don't model |
| `boundary` *(optional)* | – | Declares what is on the other side, and overrides the type | `"OUTDOORS"` (default for opaque and transparent)<br>`"GROUND"`: **the only way to make a slab-on-ground floor**<br>`"INTERNAL"`: same as `type: "adjacent"`<br>`"ADIABATIC"` |
| `area` | m² | Net area. For a wall, subtract the window area. | |
| `u_value` | W/(m²·K) | Thermal transmittance | e.g. insulated wall 0.3–0.5, brick veneer 1.0, single glazing 5.4, double glazing 2.5–3.0 |
| `orientation` | – | `{"azimuth": …, "tilt": …}` | Walls: tilt 90. Floors, ceilings and flat roofs: tilt 0. A sloped roof uses its real tilt. |
| `sky_view_factor` | 0–1 | How much of the sky the surface sees | 0.5 vertical outdoor wall or window<br>1.0 horizontal roof<br>0 internal, adjacent or ground surface |
| `solar_absorptance` | 0–1 | Share of sunlight absorbed on the outside face | Light colour 0.3, medium 0.5–0.6, dark brick 0.75, black 0.9. Use 0 for internal surfaces. |
| `thermal_capacity` | J/(m²·K) | Areal heat capacity (thermal mass) | **0 in the notebook on purpose**, to match the paper's EnergyPlus comparison. For a real building use, for example, lightweight 10 000–50 000, medium 50 000–110 000, heavy masonry or concrete 150 000–250 000. |
| `name_adj_zone` | – | Neighbouring zone on the other side | Must exactly match a `name` in Step 5. Use `None` for outdoor surfaces. |
| `height`, `length` | m | Surface dimensions | `height` is used for the window opening in `temp_wind` ventilation |

### Extra keys for windows (`type: "transparent"`)

| Key | Unit | Meaning | Options / notes |
|---|---|---|---|
| `g_value` | 0–1 | Solar heat gain coefficient (SHGC) | Clear single 0.8–0.85, clear double 0.7–0.75, low-e 0.4–0.6, tinted 0.3–0.5 |
| `glazing_panes` | 1–3 | Number of panes | Selects the default angle-dependent glass properties |
| `height`, `width` | m | Window size | Needed by overhang shading and `temp_wind` ventilation |
| `parapet` | m | Height of the window sill above the floor | Used only by `temp_wind` ventilation |
| `shading_type` | – | External fixed shading | `"horizontal_overhang"`: eave, awning or balcony above<br>`"vertical_overhang"`<br>Leave it out for no fixed shading. (`"obstacles"` is accepted but has **no effect** yet.) |
| `overhang_properties` | – | Size of the overhang | `{"width_of_horizontal_overhangs": depth_m}`: how far the overhang sticks out |
| `width_or_distance_of_shading_elements` | m | Gap between the top of the window and the overhang | |
| `solar_shading_transmittance` | 0–1 | Movable blind or screen: the share of sunlight it lets through when closed | 1 = no blind, 0.3 = typical external blind |
| `solar_shading_activation_irradiance_W_m2` | W/m² | The blind closes only above this sunlight level | e.g. 300 |
| `window_angular_coefficients` *(advanced)* | – | Six coefficients for the `karlsson_roos` model (Step 9) | Replaces the defaults chosen from `glazing_panes` |
| `shading` | – | **Not used by the engine.** Setting it to True or False changes nothing (tested). | Use `shading_type` and the keys above instead. |

**Effects in Apartment 305 (west windows):**
- An overhang 1.0 m deep, 0.2 m above the windows, cut cooling from 18.5 to 10.6 kWh.
- An external blind (`solar_shading_transmittance` 0.3, closing above 300 W/m²) cut cooling from 18.5 to 3.2 kWh.

---

## Step 5 – Neighbouring zones (`adjacent_zones`)

You need one entry for every `name_adj_zone` used in Step 4.

| Key | Meaning | Options / notes |
|---|---|---|
| `name` | Zone name | Must match `name_adj_zone` in Step 4 |
| `conditioned` | Is the neighbour heated and cooled? | `True`: held at `setpoint`. Use this for occupied apartments and conditioned corridors.<br>`False`: unconditioned buffer such as a garage, attic or unheated stair. Its temperature floats between yours and outdoors (ISO 13789). |
| `setpoint` | Temperature of a conditioned neighbour, °C | Typically 18–21 |
| `volume`, `a_use` | Neighbour volume (m³) and floor area (m²) | Matter for unconditioned neighbours |
| `building_type_class` | Usage of the neighbour | Same choices as Step 2 |
| `orientation_zone` | `{"azimuth": …}` of the neighbour | |
| `area_facade_elements` | List of the neighbour's own envelope areas, m² | All four `*_elements` lists must be the same length. They matter for **unconditioned** neighbours, where they set how strongly the buffer follows outdoor temperature. |
| `typology_elements` | Type of each element | `"OP"` opaque, `"W"` window |
| `transmittance_U_elements` | U-value of each element | W/(m²·K) |
| `orientation_elements` | Direction of each element | `"NV"`, `"EV"`, `"SV"`, `"WV"`: vertical, facing north, east, south or west<br>`"HOR"`: horizontal |

**No neighbours** (for example a detached house):
- Set `adjacent_zones = []`.
- In Step 2, set `adj_zones_present: False` and `number_adj_zone: 0`.
- Use no `"adjacent"` surfaces.

---

## Step 6 – Setpoints and plant size

| Key | Unit | Meaning | Notes |
|---|---|---|---|
| `heating_setpoint` | °C | Heating target while the heating schedule is 1 | Set **-999** for a building with **no heating** |
| `heating_setback` | °C | Heating target while the heating schedule is 0 | For a fully "off" period, use a low value such as 10, or -999 |
| `cooling_setpoint` | °C | Cooling target while the cooling schedule is 1 | Set **999** for **no cooling** (tested: cooling becomes 0) |
| `cooling_setback` | °C | Cooling target while the cooling schedule is 0 | e.g. 28–32, or 999 for off |
| `heating_capacity`, `cooling_capacity` | W | Maximum plant power | `1e7` means an ideal, unlimited system (energy *need*). Use a real size to see unmet hours. |

---

## Step 7 – Ventilation and air leakage (`ventilation`)

The engine adds **two separate airflows** together:
1. **Designed ventilation**, chosen with `ventilation_type`, or with a `components` list for several streams.
2. **Envelope infiltration (air leakage)**, from `envelope_permeability_q50`. This is always added, through the outdoor-facing surfaces only.

### 7a. `ventilation_type`: the designed ventilation

| Option | What it models | Keys it reads |
|---|---|---|
| `"occupancy"` *(notebook default)* | Fixed fresh-air rate per floor area, multiplied by the `ventilation_profile` | `flow_rate_per_person`: **l/(s·m² of floor)**, despite the name. Typical residential values are 0.3–0.5. The notebook's 2.0 gives 40 l/s for 20 m². It is inherited from the paper's diagnostic setup and dominates heating. |
| `"custom"` | A constant ventilation heat-transfer coefficient that you supply | `custom_heat_transfer_coefficient_ventilation`, in W/K. W/K = 1.21 × airflow in l/s. |
| `"temp_wind"` | Window opening driven by wind and stack effect (EN 16798-7) | Uses each window's `height`, `width` and `parapet`.<br>Optional: `temp_wind_opening_ratio` (0–1, default **0.9**, meaning windows 90% open), `temp_wind_c_wnd` (default 0.001), `temp_wind_c_st` (default 0.0035).<br>**Effect:** with the default 0.9, heating jumped to 1128 kWh. Lower the opening ratio for realistic use. |
| `"eplus_infiltration_ext_area"` | Same formula as EnergyPlus `ZoneInfiltration:DesignFlowRate` (flow per exterior area): q × (A + B·ΔT + C·V + D·V²) | `infiltration_flow_per_exterior_area_m3_s_m2`, `infiltration_coeff_constant` (A), `infiltration_coeff_temperature` (B), `infiltration_coeff_velocity` (C), `infiltration_coeff_velocity_squared` (D). Optional: `infiltration_wind_reduction_factor`, `infiltration_include_transparent_area`, `infiltration_exterior_area_mode` (`"outdoors_only"` or `"energyplus_like"`). |
| `"sherman_grimsrud_like"` | Effective-leakage-area model: ELA × √(Cs·ΔT + Cw·V²) | `infiltration_effective_leakage_area_m2`, `infiltration_stack_coefficient`, `infiltration_wind_coefficient`, `infiltration_schedule_multiplier` |
| `"none"` | No designed ventilation | Only the q50 infiltration remains |

`ventilation_profile` (Step 9) multiplies the designed ventilation hour by hour, from 0 = off to 1 = full.

**Effects in Apartment 305** (heating / cooling, kWh): `occupancy` 2.0 → 113 / 18.5 · `custom` 10 W/K → 0.6 / 7.2 · `none` → 0.0 / 5.4. These show that the designed ventilation causes almost all of this apartment's heating need.

### 7b. Several ventilation streams: `components` (advanced)

If `ventilation["components"]` is present, it **replaces** `ventilation_type`. The q50 infiltration is still added. Each item is a dict with a unique `name` and one of these `ventilation_type` values:

| Component type | Required keys | Notes |
|---|---|---|
| `"constant_ach"` | `air_changes_per_hour` | Needs `zone_volume_m3` in Step 2. Optional `source_temperature` (default `"outdoor"`). |
| `"prescribed"` | `heat_transfer_coefficient_w_k`, `source_temperature_c` | A fixed stream at a fixed supply temperature |
| `"mechanical_supply"` | `supply_flow_m3_h`, `sensible_heat_recovery_efficiency` (0–1), `supply_temperature_setpoint_c` | Air-handling unit with heat recovery (EN 16798-5-1).<br>Optional: `extract_flow_m3_h`, `supply_temperature_mode` (`"fixed"`, `"outdoor_compensated"`, `"extract_compensated"` with `supply_temperature_points`), `heating_coil_max_power_w`, `cooling_coil_enabled`, `frost_control`, and fan power keys (`supply_fan_specific_power_w_per_m3_s` and similar). |

Any component can also take `"profile": "<column name>"` to follow an hourly schedule.

Example: mechanical ventilation with 80% heat recovery.

```python
ventilation["components"] = [
    {"name": "mvhr", "ventilation_type": "mechanical_supply",
     "supply_flow_m3_h": 60, "sensible_heat_recovery_efficiency": 0.8,
     "supply_temperature_setpoint_c": 18},
]
```

### 7c. Air leakage (infiltration)

| Key | Meaning | Options |
|---|---|---|
| `envelope_permeability_q50` | Air leakage at 50 Pa per m² of outdoor-facing envelope, m³/(h·m²). This is **not** ACH50. | Measured value if you have one. The paper's scenarios are 4 (tight), 11 (typical of 2006 or later) and 14. Set 0 for no leakage. If you **remove the key**, the default comes from `construction_year`:<br>before 1900 → 30, 1901–1920 → 28, 1921–1945 → 26, 1946–1960 → 24, 1961–1975 → 20, 1976–1990 → 16, 1991–2005 → 14, 2006 or later → 11<br>These are illustrative values, not measurements. |
| `infiltration_modulation` | How leakage varies hour by hour | `"stack_wind"`: varies with outdoor temperature and wind (default)<br>`"constant"`: the annual mean rate every hour |
| `infiltration_reference_temperature_C` | Indoor temperature used for the stack effect, °C | A number such as 20 fixes it, as in the paper. Remove the key to use the simulated indoor temperature. |
| `infiltration_multiplier_decimals` | Rounds the hourly leakage multiplier | Used only to match the paper's EnergyPlus comparison. It can be removed. |

How the engine converts q50 to an airflow: n50 = q50 × outdoor-envelope area / volume, then the mean rate = n50 / 20.

---

## Step 8 – Internal gains (`internal_gains`)

Each entry has `name`, `full_load` (W/m² of floor area), and 24-value `weekday` and `weekend` lists. Each list value is the fraction of `full_load` in that hour (0–1).

| `name` | Meaning | Default if the entry is left out (W/m², from `building_type_class`) |
|---|---|---|
| `"occupants"` | Body heat | Apartment 4.2, Detached house 2.8, Office 7, School 21.7, Kindergarten 33.3, Department store 9.3 |
| `"appliances"` | Equipment | Apartment 3, Detached house 2.4, Office 12, School 8, Kindergarten 4, Department store 1 |
| `"lighting"` | Lights | 0 |

Only these three names are recognised. If an entry is left out, its default load **and** default schedule for the building type are used.

---

## Step 9 – Schedules, climate and model options

### Operating schedules

Each schedule is `{"weekday": [24 values], "weekend": [24 values]}`. If a schedule is left out, the occupancy schedule is used instead.

| Schedule | Meaning of the values |
|---|---|
| `heating_profile` | > 0: `heating_setpoint` applies. 0: `heating_setback` applies. |
| `cooling_profile` | > 0: `cooling_setpoint` applies. 0: `cooling_setback` applies. |
| `ventilation_profile` | Multiplies the designed ventilation (0–1). Does not affect q50 infiltration. |

### Other inputs

| Key | Meaning | Notes |
|---|---|---|
| `thermal_bridges` | **Not used by the engine** (tested: 1.5 or 50 W/K give identical results) | Thermal bridges are set automatically as 0.05 W/(m·K) × `exposed_perimeter`. To represent extra bridge losses, raise the wall U-values instead. |
| `coldest_month` | Month with the coldest ground temperature (1–12) | 7 for the southern hemisphere, 1 for the northern. If omitted, it is chosen from the latitude. |

### `simulation_options`

| Key | Meaning | Options (default in **bold**) |
|---|---|---|
| `profile_start_year` | Calendar year used for weekdays and weekends | e.g. 2025 |
| `profile_use_holidays` | Treat public holidays (from `country`) as weekend days | `False`, **`True`** |
| `dynamic_window_properties` | Paper repair: window U and g vary with the conditions | **`True`**, `False` (original engine behaviour) |
| `dynamic_surface_heat_transfer` | Paper repair: wind-dependent outside heat transfer on all surfaces | **`True`**, `False` |
| `window_angular_solar_model` | How window g-value drops at low sun angles | `"none"`, `"constant"` (fixed 0.9 factor), `"karlsson_roos"` (angle-dependent).<br>**Effect:** `karlsson_roos` cut cooling from 18.5 to 16.9 kWh. |
| `window_convection_model` | Outside convection on windows | `"table"` (ISO constant), `"simplecombined"` (4 + 4·wind), `"doe2"`, `"mowitt"`, `"blast"` (EnergyPlus correlations). Default is **`"simplecombined"`** when the key is left out. |
| `external_convection_model` | Outside convection on opaque walls and roofs | Same choices as above |
| `external_convection_h_min` | Lowest allowed outside convection coefficient, W/(m²·K) | **2.0** |
| `internal_convection_model` | Inside convection | **`"table"`**, `"tarp"` |
| `external_radiation_model` | Outside long-wave radiation coefficient | **`"table"`** (constant), `"dynamic"` |
| `sky_temperature_model` | Sky temperature for radiation to the sky | **`"berdahl_fromberg"`**, `"swinbank"`, `"epw_ir"` (from the weather file). Has an effect only when `external_radiation_model` is `"dynamic"`. |
| `external_emissivity_default` | Long-wave emissivity of outside surfaces | **0.9** |
| `ground_temperature_model` | Ground temperature under slabs | **`"iso13370"`**, `"monthly"` (then give `ground_temperature_monthly`: 12 values in °C) |
| `wind_profile` | Apply the Step 3 terrain correction to the wind | **`True`**, `False` |

---

## Step 10 – Weather

The weather file must be an EnergyPlus **`.epw`** file.

- **Australian sites:** download from climate.onebuilding.org. Choose TMYx files, as used in the paper.
- **Other countries:** same website, or energyplus.net/weather.
- In Colab, upload it with the `files.upload()` line in Step 10.

When you change city, also update `latitude`, `longitude` and `coldest_month`.

---

## Step 11 – Results

`simulate(BUI, weather)` returns a table with 8760 hourly rows.

| Column | Meaning | Unit |
|---|---|---|
| `Q_H`, `Q_C` | Heating and cooling need | W |
| `Q_HC` | Net need (heating +, cooling −) | W |
| `T_air`, `T_op` | Indoor air and operative temperature | °C |
| `T_ext` | Outdoor temperature | °C |
| `H_ve` | Total ventilation + infiltration heat-transfer coefficient | W/K |
| `Q_ve` | Ventilation heat flow | W |
| `Q_solar_gains`, `Q_internal_gains` | Solar and internal gains | W |
| `Q_tr_opaque`, `Q_tr_window`, `Q_tr_adjacent`, `Q_ground`, `Q_tb` | Transmission through walls, windows, party surfaces, ground and thermal bridges | W |
| `Q_tr_surface_<name>` | Transmission through each surface | W |
| `Q_H_attr_*`, `Q_C_attr_*` | Heating and cooling need attributed to each heat path | W |
| `Q_balance_residual` | Heat-balance check. It should be about 0. | W |

Useful lines:

```python
h.Q_H.sum() / 1000                                    # annual heating, kWh
h[["Q_H", "Q_C"]].resample("ME").sum() / 1000          # monthly, kWh (after setting a date index)
h.T_op.max()                                          # peak indoor temperature
```

---

## Common mistakes

| Symptom | Likely cause |
|---|---|
| Error mentioning an adjacent zone | A `name_adj_zone` doesn't match any zone `name`, or `number_adj_zone` is wrong |
| Very large heating | `flow_rate_per_person` is too high (it is per m², not per person), `temp_wind` is used with a 0.9 opening ratio, or q50 is too high |
| Ground floor behaves like an upper floor | The floor needs `"boundary": "GROUND"` and `exposed_perimeter` > 0 |
| Shading has no effect | `shading: True` alone does nothing. Set `shading_type`, the overhang keys and the window `height` and `width`. |
| Results the same after changing `thermal_bridges` | That key isn't read (see Step 9) |
| Strange seasonal pattern | `latitude` or `coldest_month` doesn't match the weather file's hemisphere |
