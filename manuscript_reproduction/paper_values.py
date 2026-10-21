"""Recompute every number quoted in the manuscript from the saved evidence.

Run: python paper_values.py
No simulation is run. Each value is recalculated from the archived inputs,
hourly outputs, EnergyPlus SQL and weather files, then compared with the
rounded figure printed in the manuscript. Writes paper_values.json and the
winter heat-balance table (manuscript Table 5) to tables/winter_heat_balance.tex.
"""
from pathlib import Path
import json
import sqlite3
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'pybuildingenergy/src'))
from pybuildingenergy.source import utils as u

OUT = ROOT / 'revision_results'
MONTHS = np.repeat(np.arange(1, 13), np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]) * 24)
WINTER = np.isin(MONTHS, [6, 7, 8])
RHO_CP = 1.204 * 1006  # J/(m3 K), as in the EnergyPlus ventilation audit
records = []


def check(section, name, value, printed, decimals):
    """Record a recomputed value and whether it rounds to the printed figure."""
    value = float(value)
    ok = abs(round(value, decimals) - printed) < 0.5 * 10 ** -decimals + 1e-12
    records.append(dict(section=section, quantity=name, recomputed=value,
                        manuscript=printed, decimals=decimals, matches=bool(ok)))


comparison = pd.read_csv(OUT / 'comparison.csv')
def energy(case, metric='Total', col='iso_kWh'):
    return comparison[(comparison['case'] == case) & (comparison.metric == metric)][col].iloc[0]


def hourly(case):
    return pd.read_csv(OUT / 'hourly' / (case + '.csv.gz'))


def epw(name):
    return pd.read_csv(ROOT / 'weather_cache' / name, skiprows=8, header=None)


# ---------------------------------------------------------------- Methodology
b = json.loads((OUT / 'inputs/repaired.json').read_text())
surfaces = b['building_surface']
shared = [s for s in surfaces if s['type'] == 'adjacent']
exterior = [s for s in surfaces if s['type'] == 'opaque']
windows = [s for s in surfaces if s['type'] == 'transparent']
area = lambda group: sum(s['area'] for s in group)
ua = lambda group: sum(s['area'] * s['u_value'] for s in group)
check('2.1 Case study', 'exterior opaque wall area (m2)', area(exterior), 11.88, 2)
check('2.1 Case study', 'window area (m2)', area(windows), 1.62, 2)
check('2.1 Case study', 'shared boundary area (m2)', area(shared), 75.1, 1)
check('2.1 Case study', 'shared share of envelope area (%)',
      100 * area(shared) / area(surfaces), 84.8, 1)
check('3.1 Results', 'shared share of envelope conductance (%)',
      100 * ua(shared) / ua(surfaces), 88.6, 1)
volume = b['building']['net_floor_area'] * b['building']['height']
check('2.1 Case study', 'air volume (m3)', volume, 54, 0)

ro = epw('AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw')
sel = ro[1].isin([1, 3, 7, 9])
check('2.2 Weather', 'Regional Office zero-wind hours (Jan/Mar/Jul/Sep)', (ro[21][sel] <= 0).sum(), 2941, 0)
check('2.2 Weather', 'Regional Office hours in Jan/Mar/Jul/Sep', sel.sum(), 2952, 0)
essendon = epw('AUS_VIC_Melbourne-Essendon.Fields.958660_TMYx.2011-2025.epw')
check('2.2 Weather', 'Essendon annual mean wind (m/s)', essendon[21].mean(), 4.84, 2)
factor, audit = u.resolve_local_wind_factor(b)
check('2.2 Weather', 'facade height (m)', audit['surface_height_m'], 6.75, 2)
check('2.2 Weather', 'local wind multiplier', factor, 0.6574, 4)
check('2.2 Weather', 'annual mean local wind (m/s)', factor * essendon[21].mean(), 3.18, 2)

design_flow = 0.040
check('2.4 Stage 1', 'designed ventilation (h-1)', design_flow * 3600 / volume, 2.67, 2)
check('2.6 Stage 3', 'designed ventilation conductance (W/K)', RHO_CP * design_flow, 48.4, 1)
infiltration = {}
for case, q in [('repaired', 4), ('au_leakage_only', 11), ('q14_sensitivity', 14)]:
    check('2.6 Stage 3', f'n50 at q50={q} (h-1)', q * 13.5 / volume, {4: 1.00, 11: 2.75, 14: 3.50}[q], 2)
    infiltration[q] = hourly(case).H_ve.mean() - RHO_CP * design_flow
    check('2.6 Stage 3', f'mean infiltration conductance q50={q} (W/K)', infiltration[q],
          {4: 0.76, 11: 2.09, 14: 2.66}[q], 2)
share = {q: 100 * h / (RHO_CP * design_flow + h) for q, h in infiltration.items()}
check('2.6 Stage 3', 'infiltration share of outdoor-air conductance, q50=4 (%)', share[4], 1.5, 1)
check('2.6 Stage 3', 'infiltration share of outdoor-air conductance, q50=14 (%)', share[14], 5.2, 1)
multiplier = pd.read_csv(OUT / 'hourly/diagnostic_q4_energyplus.csv').airflow_multiplier
check('3.3 Leakage', 'annual mean weather multiplier', multiplier.mean(), 0.853, 3)

# ---------------------------------------------------------- Tables 2, 4, 6, 7
tables = {
    'Table 2': [('original', 1780.09, 628.65, 2408.74, 1430.98, 483.24),
                ('without_infiltration', 108.39, 18.15, 126.54, -19.57, 16.99),
                ('repaired', 113.22, 18.54, 131.76, -16.25, 15.59)],
    'Table 4': [('repaired', 113.22, 18.54, 131.76, -16.25, 15.59),
                ('angular_only', 113.27, 16.91, 130.18, -17.26, 15.63),
                ('convection_only', 112.08, 20.04, 132.12, -16.02, 15.06),
                ('both', 112.13, 18.37, 130.50, -17.06, 15.02)],
    'Table 6': [('both', 112.13, 18.37, 130.50, -17.06, 15.02),
                ('au_leakage_only', 120.73, 19.06, 139.78, -17.04, 15.76),
                ('au_construction_only', 67.32, 0.00, 67.32, -21.28, 19.39),
                ('au_combined', 76.51, 0.00, 76.51, -18.61, 20.29)],
}
for table, rows in tables.items():
    for case, heat, cool, total, bias, rmse in rows:
        check(table, f'{case} ISO heating', energy(case, 'Heating'), heat, 2)
        check(table, f'{case} ISO cooling', energy(case, 'Cooling'), cool, 2)
        check(table, f'{case} ISO total', energy(case), total, 2)
        check(table, f'{case} total bias (%)', energy(case, col='bias_pct'), bias, 2)
        check(table, f'{case} total RMSE (W)', energy(case, col='RMSE_W'), rmse, 2)
check('Table 2', 'EnergyPlus heating', energy('repaired', 'Heating', 'ep_kWh'), 136.38, 2)
check('Table 2', 'EnergyPlus cooling', energy('repaired', 'Cooling', 'ep_kWh'), 20.95, 2)
check('Table 2', 'EnergyPlus total', energy('repaired', col='ep_kWh'), 157.33, 2)
for case, total in [('au_leakage_only', 168.49), ('au_construction_only', 85.52), ('au_combined', 94.01)]:
    check('Table 6', f'{case} EnergyPlus total', energy(case, col='ep_kWh'), total, 2)
for case, rows in [('au_leakage_only', (120.73, 19.06, 146.83, 21.66)),
                   ('q14_sensitivity', (124.51, 19.35, 151.51, 21.95)),
                   ('q11_constant', (119.81, 18.87, 145.50, 21.48))]:
    for (metric, col), printed in zip([('Heating', 'iso_kWh'), ('Cooling', 'iso_kWh'),
                                       ('Heating', 'ep_kWh'), ('Cooling', 'ep_kWh')], rows):
        check('Table 7', f'{case} {col[:-4]} {metric.lower()}', energy(case, metric, col), printed, 2)
check('3.2 Methods', 'fixed-method heating RMSE (W)', energy('repaired', 'Heating', 'RMSE_W'), 13.16, 2)
check('3.2 Methods', 'combined heating RMSE (W)', energy('both', 'Heating', 'RMSE_W'), 13.51, 2)
check('3.2 Methods', 'fixed-method cooling RMSE (W)', energy('repaired', 'Cooling', 'RMSE_W'), 8.37, 2)
check('3.2 Methods', 'combined cooling RMSE (W)', energy('both', 'Cooling', 'RMSE_W'), 6.55, 2)

# ------------------------------------------------------- Interactions (text)
for engine, col, printed in [('ISO', 'iso_kWh', -0.10), ('EnergyPlus', 'ep_kWh', -2.67)]:
    value = (energy('au_combined', col=col) - energy('au_leakage_only', col=col)
             - energy('au_construction_only', col=col) + energy('both', col=col))
    check('3.4 Inputs', f'{engine} leakage x construction interaction (kWh)', value, printed, 2)
check('3.2 Methods', 'angular x convection interaction (kWh)',
      energy('both') - energy('angular_only') - energy('convection_only') + energy('repaired'), -0.04, 2)
check('3.3 Leakage', 'ISO heating, weather minus constant flow (kWh)',
      energy('au_leakage_only', 'Heating') - energy('q11_constant', 'Heating'), 0.92, 2)
check('3.3 Leakage', 'EP heating, weather minus constant flow (kWh)',
      energy('au_leakage_only', 'Heating', 'ep_kWh') - energy('q11_constant', 'Heating', 'ep_kWh'), 1.33, 2)
check('3.3 Leakage', 'ISO total, q50 11 to 14 (kWh)',
      energy('q14_sensitivity') - energy('au_leakage_only'), 4.1, 1)
check('3.3 Leakage', 'EP total, q50 11 to 14 (kWh)',
      energy('q14_sensitivity', col='ep_kWh') - energy('au_leakage_only', col='ep_kWh'), 5.0, 1)

# ------------------------------------------------------ Table 3 and Stage 1
combinations = pd.read_csv(ROOT / 'stage1_results/combinations.csv', dtype={'mask': str}).set_index('mask')
for mask, printed in [('1000', 72.67), ('1100', 126.81), ('1110', 126.54), ('1111', 131.76)]:
    check('Table 3', f'state {mask} total', combinations.loc[mask, 'total_kWh'], printed, 2)
for before, after, printed in [('0000', '1000', -2336.07), ('1000', '1100', 54.14),
                               ('1100', '1110', -0.27), ('1110', '1111', 5.23)]:
    check('Table 3', f'change {before} to {after}',
          combinations.loc[after, 'total_kWh'] - combinations.loc[before, 'total_kWh'], printed, 2)
check('3.1 Results', 'direct gains applied alone (kWh)',
      combinations.loc['0100', 'total_kWh'] - combinations.loc['0000', 'total_kWh'], 1549.98, 2)
check('3.1 Results', 'direct gains after other three (kWh)',
      combinations.loc['1111', 'total_kWh'] - combinations.loc['1011', 'total_kWh'], 58.41, 2)


# ---------------------------------------- Winter heat balance (Table 5)
def energyplus_series(reference):
    """Hourly EnergyPlus report variables (J), keyed by (variable, key)."""
    with sqlite3.connect(OUT / 'energyplus' / reference / 'referenceout.sql') as con:
        data = pd.read_sql(
            'SELECT d.Name, d.KeyValue, r.Value, t.Month, t.Day, t.Hour FROM ReportData r '
            'JOIN ReportDataDictionary d ON r.ReportDataDictionaryIndex = d.ReportDataDictionaryIndex '
            'JOIN Time t ON r.TimeIndex = t.TimeIndex WHERE COALESCE(t.WarmupFlag, 0) = 0', con)
    table = data.pivot_table(index=['Month', 'Day', 'Hour'], columns=['Name', 'KeyValue'], values='Value')
    assert len(table) == 8760
    return table.sort_index()


def winter_balance(case='repaired', reference='diagnostic_q4'):
    """Selected heat-balance terms over June-August heated hours, heat in positive (kWh)."""
    h = hourly(case)
    ep = energyplus_series(reference)
    iso_heat = np.maximum(h.Q_HC.to_numpy(), 0)
    ep_heat = pd.read_csv(OUT / 'hourly' / (reference + '_energyplus.csv')).heating_W.to_numpy()
    mask = WINTER & ((iso_heat > 0) | (ep_heat > 0))
    kwh = lambda series: float(np.asarray(series)[mask].sum() / 1000)
    joule = lambda name, keys: float(sum(ep[(name, k)].to_numpy()[mask].sum() for k in keys) / 3.6e6)
    conduction = 'Surface Average Face Conduction Heat Transfer Energy'
    window = 'Surface Window Net Heat Transfer Energy'
    shared_keys = ['NORTHWALL', 'EASTWALL', 'SOUTHWALL', 'FLOORSLAB', 'CEILINGSLAB']
    exterior_wall = [c for c in h if c.startswith('Q_tr_surface_West_exterior_wall')]
    air = (joule('Zone Infiltration Sensible Heat Gain Energy', ['APT305'])
           - joule('Zone Infiltration Sensible Heat Loss Energy', ['APT305'])
           + joule('Zone Ventilation Sensible Heat Gain Energy', ['APT305'])
           - joule('Zone Ventilation Sensible Heat Loss Energy', ['APT305']))
    # pyBuildingEnergy reports transmission and ventilation as losses (positive out).
    terms = {
        'Heating supplied': (kwh(iso_heat), kwh(ep_heat)),
        'Heat gained from neighbouring spaces': (-kwh(h.Q_tr_adjacent), joule(conduction, shared_keys)),
        'Exterior-wall exchange': (-kwh(h[exterior_wall].sum(axis=1)), joule(conduction, ['WESTWALL'])),
        'Outdoor-air exchange': (-kwh(h.Q_ve), air),
        'Window exchange, net': (kwh(h.Q_solar_gains) - kwh(h.Q_tr_window),
                                 joule(window, ['WESTWIN_FIXED', 'WESTWIN_OPERABLE'])),
    }
    temperatures = (float(h.T_op.to_numpy()[mask].mean()),
                    float(ep[('Zone Operative Temperature', 'APT305')].to_numpy()[mask].mean()))
    return int(mask.sum()), temperatures, terms


hours, (t_iso, t_ep), terms = winter_balance()
check('Table 5', 'winter heated hours', hours, 430, 0)
check('Table 5', 'mean operative temperature, ISO (C)', t_iso, 17.51, 2)
check('Table 5', 'mean operative temperature, EP (C)', t_ep, 17.49, 2)
printed = {'Heating supplied': (78.10, 94.21, 16.11),
           'Heat gained from neighbouring spaces': (160.61, 140.97, -19.64),
           'Exterior-wall exchange': (-53.25, -54.17, -0.92),
           'Outdoor-air exchange': (-190.83, -189.56, 1.27),
           'Window exchange, net': (-39.01, -32.19, 6.82)}
for term, (iso, ep) in terms.items():
    p_iso, p_ep, p_diff = printed[term]
    check('Table 5', f'{term}, ISO', iso, p_iso, 2)
    check('Table 5', f'{term}, EP', ep, p_ep, 2)
    check('Table 5', f'{term}, difference', ep - iso, p_diff, 2)
monthly = pd.read_csv(OUT / 'monthly.csv')
heat = monthly[(monthly['case'] == 'repaired') & (monthly.metric == 'Heating')]
gap = heat.ep_kWh - heat.iso_kWh
winter_gap = gap[heat.month.isin([6, 7, 8])].sum()
check('3.1 Results', 'annual heating shortfall (kWh)', gap.sum(), 23.16, 2)
check('3.1 Results', 'June-August heating shortfall (kWh)', winter_gap, 16.11, 2)
check('3.1 Results', 'winter share of heating shortfall (%)', 100 * winter_gap / gap.sum(), 69.6, 1)

# ------------------------------------------------------- 3.5 Verification
checks = json.loads((OUT / 'checks.json').read_text())
residuals = [c['max_balance_residual_W'] for c in checks.values() if 'max_balance_residual_W' in c]
check('3.5 Verification', 'corrected simulations', len(residuals), 11, 0)
check('3.5 Verification', 'largest residual (1e-11 W)', max(residuals) * 1e11, 9.19, 2)
audit = json.loads((OUT / 'audit_revision.json').read_text())
entries = {c['transmission_surface_entries'] for c in audit['cases'].values() if 'transmission_surface_entries' in c}
check('3.5 Verification', 'diagnostic transmission entries', min(entries), 7, 0)
check('3.5 Verification', 'material-derived transmission entries', max(entries), 8, 0)
check('3.5 Verification', 'EnergyPlus references with continuous ventilation',
      sum(r['continuous_ventilation_verified'] for r in audit['references'].values()), 7, 0)
check('3.5 Verification', 'historical reproduction ISO heating', energy('archive_reproduction', 'Heating'), 124.46, 2)
check('3.5 Verification', 'historical reproduction ISO cooling', energy('archive_reproduction', 'Cooling'), 19.30, 2)
check('3.5 Verification', 'historical reproduction EP total', energy('archive_reproduction', col='ep_kWh'), 171.47, 2)

# ---------------------------------------------------------------- outputs
table = pd.DataFrame(records)
(ROOT / 'paper_values.json').write_text(json.dumps(
    {'status': 'passed' if table.matches.all() else 'failed',
     'checked': len(table), 'mismatched': int((~table.matches).sum()),
     'values': records}, indent=2) + '\n')
signed = lambda x: f'${x:.2f}$' if x < 0 else f'{x:.2f}'
rows = '\n'.join(f'{term}\n& {signed(iso)} & {signed(ep)} & ${ep - iso:+.2f}$ \\\\'
                 for term, (iso, ep) in terms.items())
(ROOT / 'tables').mkdir(exist_ok=True)
(ROOT / 'tables/winter_heat_balance.tex').write_text(
    '% Generated by paper_values.py from revision_results; do not edit by hand.\n'
    '\\begin{tabularx}{\\textwidth}{@{}Xrrr@{}}\n\\toprule\n'
    'Term & pyBuildingEnergy & EnergyPlus & Difference \\\\\n\\midrule\n'
    f'{rows}\n\\bottomrule\n\\end{{tabularx}}\n'
    f'% {hours} heated hours; mean operative temperature {t_iso:.2f} C (ISO), {t_ep:.2f} C (EnergyPlus).\n')
bad = table[~table.matches]
print(f'{len(table)} manuscript values recomputed; {len(bad)} mismatched.')
if len(bad):
    print(bad.to_string(index=False))
    sys.exit(1)
