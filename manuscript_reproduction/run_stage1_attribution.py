"""Run all sixteen Stage 1 combinations and verify the saved endpoints.

Run with the requirements-revision.txt environment, from any directory.
"""
import concurrent.futures
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'stage1_results'
FACTORS = ['neighbours', 'gains', 'ground_perimeter', 'infiltration']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_one(mask):
    dest = OUT / 'hourly' / (mask + '.csv.gz')
    with (OUT / 'logs' / (mask + '.log')).open('w') as log:
        subprocess.run([sys.executable, str(ROOT / 'stage1_worker.py'), mask,
                        str(ROOT / 'revision_results/inputs/repaired.json'), str(dest)],
                       env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    print('Completed', mask, flush=True)


def main():
    sys.path.insert(0, str(ROOT / 'examples'))
    from weather_melbourne import CANONICAL_EPW
    weather_hash = sha(ROOT / 'weather_cache' / CANONICAL_EPW)
    assert weather_hash == json.loads((ROOT / 'revision_results/COMPLETE.json').read_text())['weather_sha256']
    for sub in ['hourly', 'logs']:
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    masks = [''.join(bits) for bits in itertools.product('01', repeat=4)]
    # Always run from source; do not treat a stale file as evidence of success.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(run_one, masks))
    ref = pd.read_csv(ROOT / 'revision_results/hourly/diagnostic_q4_energyplus.csv')
    rows = []
    hours = {}
    for mask in masks:
        h = pd.read_csv(OUT / 'hourly' / (mask + '.csv.gz'))
        hours[mask] = h
        a = h.Q_HC.to_numpy()
        heating = np.maximum(a, 0)
        cooling = np.maximum(-a, 0)
        total = heating + cooling
        e = total.sum() / 1000
        r = (ref.heating_W + ref.cooling_W).sum() / 1000
        row = {'mask': mask, **dict(zip(FACTORS, map(int, mask))),
               'heating_kWh': heating.sum() / 1000,
               'cooling_kWh': cooling.sum() / 1000, 'total_kWh': e,
               'bias_pct': 100 * (e - r) / r,
               'total_RMSE_W': np.sqrt(np.mean((total - ref.heating_W - ref.cooling_W)**2)),
               'gains_kWh': h.Q_internal_gains.sum() / 1000,
               'absolute_ground_diagnostic_kWh': abs(h.Q_ground).sum() / 1000,
               'max_balance_residual_W': abs(h.Q_balance_residual).max()}
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / 'combinations.csv', index=False, float_format='%.12g')
    checks = {}
    for mask, case in [('0000', 'original'), ('1111', 'repaired'), ('1110', 'without_infiltration')]:
        previous = pd.read_csv(ROOT / 'revision_results/hourly' / (case + '.csv.gz'))
        diff = float(abs(hours[mask].Q_HC - previous.Q_HC).max())
        assert diff < 1e-6, (mask, case, diff)
        checks[case] = {'mask': mask, 'max_hourly_load_difference_W': diff}
    # Gain repair must produce identical direct gains across every boundary treatment.
    for mask in masks:
        if mask[1] == '1':
            np.testing.assert_allclose(hours[mask].Q_internal_gains, hours['1111'].Q_internal_gains, rtol=0, atol=1e-9)
        if mask[3] == '1':
            np.testing.assert_allclose(hours[mask].H_ve, hours['1111'].H_ve, rtol=0, atol=1e-9)
        if mask[2] == '1':
            assert abs(hours[mask].Q_ground).max() == 0
            assert abs(hours[mask].Q_balance_residual).max() < 1e-6
    lookup = table.set_index('mask')
    metrics = ['heating_kWh', 'cooling_kWh', 'total_kWh']
    attribution = []
    for i, factor in enumerate(FACTORS):
        single = list('0000'); single[i] = '1'; single = ''.join(single)
        omitted = list('1111'); omitted[i] = '0'; omitted = ''.join(omitted)
        for metric in metrics:
            value = 0.
            for mask in masks:
                if mask[i] == '1':
                    continue
                k = mask.count('1')
                weight = math.factorial(k) * math.factorial(3-k) / math.factorial(4)
                added = list(mask); added[i] = '1'; added = ''.join(added)
                value += weight * (lookup.loc[added, metric] - lookup.loc[mask, metric])
            attribution.append({'factor': factor, 'metric': metric,
                                'single_repair_change_kWh': lookup.loc[single, metric] - lookup.loc['0000', metric],
                                'addition_to_other_three_change_kWh': lookup.loc['1111', metric] - lookup.loc[omitted, metric],
                                'order_averaged_change_kWh': value})
    attribution = pd.DataFrame(attribution)
    for metric in metrics:
        np.testing.assert_allclose(attribution.loc[attribution.metric == metric, 'order_averaged_change_kWh'].sum(),
                                   lookup.loc['1111', metric] - lookup.loc['0000', metric], rtol=0, atol=1e-8)
    attribution.to_csv(OUT / 'attribution.csv', index=False, float_format='%.12g')
    single_sum = attribution.loc[attribution.metric == 'total_kWh', 'single_repair_change_kWh'].sum()
    summary = {'factors': FACTORS, 'annual_runs': 16, 'hours_per_run': 8760,
               'mask_bit_order': FACTORS, 'endpoint_checks': checks,
               'total_package_change_kWh': float(lookup.loc['1111', 'total_kWh'] - lookup.loc['0000', 'total_kWh']),
               'nonadditivity_relative_to_original_kWh': float(lookup.loc['1111', 'total_kWh'] - lookup.loc['0000', 'total_kWh'] - single_sum),
               'max_residual_for_ground_repaired_states_W': float(table.loc[table.ground_perimeter == 1, 'max_balance_residual_W'].max()),
               'invariants': 'Direct repaired gains and enabled airflow identical; repaired ground flow zero; repaired-ground states close below 1e-6 W.',
               'ground_off_residual_note': 'Phantom ground diagnostic retained for comparison. It is not a solver pathway and must not be called a conditioning saving.',
               'sources_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [ROOT / 'stage1_worker.py', Path(__file__), ROOT / 'revision_results/inputs/repaired.json', ROOT / 'requirements-revision.txt'] + list((ROOT / 'pybuildingenergy/src').rglob('*.py')) + list((ROOT / 'original/pybuildingenergy/src').rglob('*.py'))},
               'weather_sha256': weather_hash,
               'reference_hourly_sha256': sha(ROOT / 'revision_results/hourly/diagnostic_q4_energyplus.csv')}
    (OUT / 'COMPLETE.json').write_text(json.dumps(summary, indent=2))
    print(table[['mask', 'heating_kWh', 'cooling_kWh', 'total_kWh']].to_string(index=False), flush=True)
    print(attribution.to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
