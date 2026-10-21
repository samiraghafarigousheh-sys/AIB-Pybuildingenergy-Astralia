"""Audit archived evidence without running either simulation engine.

Run: python verify_release.py
Requires numpy and pandas. Writes release_verification.json and paper_values.json.
"""
from pathlib import Path
import hashlib
import itertools
import json
import math
import subprocess
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

report = {'verification_type': 'saved evidence audit; not a fresh simulation'}
for name, key in [('revision_results/COMPLETE.json', 'sources'),
                  ('stage1_results/COMPLETE.json', 'sources_sha256')]:
    record = json.loads((ROOT/name).read_text())
    for path, expected in record[key].items():
        assert sha(ROOT/path) == expected, ('source hash mismatch', path)
    report[name] = {'matching_source_hashes': len(record[key])}
    weather = ROOT/'weather_cache/AUS_VIC_Melbourne-Essendon.Fields.958660_TMYx.2011-2025.epw'
    assert sha(weather) == record['weather_sha256']

comparison = pd.read_csv(ROOT/'revision_results/comparison.csv')
assert len(comparison) == 36
for case, group in comparison.groupby('case'):
    hourly = pd.read_csv(ROOT/f'revision_results/hourly/{case}.csv.gz')
    reference = group.reference.iloc[0]
    ep = pd.read_csv(ROOT/f'revision_results/hourly/{reference}_energyplus.csv')
    assert len(hourly) == len(ep) == 8760
    q = hourly.Q_HC.to_numpy()
    assert np.isfinite(q).all()
    heat, cool = np.maximum(q, 0), np.maximum(-q, 0)
    for metric, y, z in [('Heating',heat,ep.heating_W),
                         ('Cooling',cool,ep.cooling_W),
                         ('Total',heat+cool,ep.heating_W+ep.cooling_W)]:
        row = group[group.metric == metric].iloc[0]
        np.testing.assert_allclose(y.sum()/1000, row.iso_kWh, rtol=0, atol=1e-8)
        np.testing.assert_allclose(z.sum()/1000, row.ep_kWh, rtol=0, atol=1e-8)
        np.testing.assert_allclose(np.sqrt(np.mean((y-z)**2)), row.RMSE_W, rtol=0, atol=1e-8)
        if z.sum() > 1e-5:
            np.testing.assert_allclose(100*(y.sum()-z.sum())/z.sum(), row.bias_pct, rtol=0, atol=1e-8)
report['main_cases_recomputed_from_hourly'] = 12

combinations = pd.read_csv(ROOT/'stage1_results/combinations.csv', dtype={'mask':str}).set_index('mask')
all_hours = {}
for mask in [''.join(x) for x in itertools.product('01', repeat=4)]:
    h = pd.read_csv(ROOT/f'stage1_results/hourly/{mask}.csv.gz')
    all_hours[mask] = h
    assert len(h) == 8760 and np.isfinite(h.Q_HC).all()
    for metric, y in [('heating_kWh',np.maximum(h.Q_HC,0)),
                      ('cooling_kWh',np.maximum(-h.Q_HC,0)),('total_kWh',abs(h.Q_HC))]:
        np.testing.assert_allclose(y.sum()/1000, combinations.loc[mask,metric], rtol=0, atol=1e-7)
    if mask[2] == '1':
        assert abs(h.Q_ground).max() == 0
        assert abs(h.Q_balance_residual).max() < 1e-6
for mask,h in all_hours.items():
    if mask[1] == '1': np.testing.assert_allclose(h.Q_internal_gains,all_hours['1111'].Q_internal_gains,rtol=0,atol=1e-9)
    if mask[3] == '1': np.testing.assert_allclose(h.H_ve,all_hours['1111'].H_ve,rtol=0,atol=1e-9)
for mask,case in [('0000','original'),('1111','repaired'),('1110','without_infiltration')]:
    h = pd.read_csv(ROOT/f'revision_results/hourly/{case}.csv.gz')
    np.testing.assert_allclose(all_hours[mask].Q_HC,h.Q_HC,rtol=0,atol=1e-6)
attribution = pd.read_csv(ROOT/'stage1_results/attribution.csv')
for i,factor in enumerate(['neighbours','gains','ground_perimeter','infiltration']):
    for metric in ['heating_kWh','cooling_kWh','total_kWh']:
        val = 0.
        for mask in all_hours:
            if mask[i] == '1': continue
            k=mask.count('1'); added=mask[:i]+'1'+mask[i+1:]
            val += math.factorial(k)*math.factorial(3-k)/24*(combinations.loc[added,metric]-combinations.loc[mask,metric])
        expected=attribution[(attribution.factor==factor)&(attribution.metric==metric)].order_averaged_change_kWh.iloc[0]
        np.testing.assert_allclose(val,expected,rtol=0,atol=1e-7)
report['stage1_combinations_recomputed_from_hourly'] = 16
report['stage1_endpoints_and_attribution'] = 'passed'
subprocess.run([sys.executable,str(ROOT/'audit_revision.py')],cwd=ROOT,check=True)
report['airflow_sql_and_input_audit'] = 'passed: 12 cases, 7 references'
subprocess.run([sys.executable,str(ROOT/'paper_values.py')],cwd=ROOT,check=True)
report['manuscript_values'] = 'passed: %d values' % json.loads((ROOT/'paper_values.json').read_text())['checked']
report['status'] = 'passed'
(ROOT/'release_verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
