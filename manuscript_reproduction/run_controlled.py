"""Reproduce the fixed-reference apartment experiment; see CONTROLLED_README.md."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent
EP_URL = ('https://github.com/NREL/EnergyPlus/releases/download/v24.1.0/'
          'EnergyPlus-24.1.0-9d7789a3ac-Linux-Ubuntu22.04-x86_64.tar.gz')
# A/B separate optical transmission from convection on windows AND opaque walls.
# The archived unmodified implementation used Fw=1.0, not ISO's fixed 0.9.
CASES = {
    'neither': ('none', 'table'),
    'angular_only': ('karlsson_roos', 'table'),
    'convection_only': ('none', 'simplecombined'),
    'both': ('karlsson_roos', 'simplecombined'),
    'fixed09': ('constant', 'table'),
    'fixed09_convection': ('constant', 'simplecombined'),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False,
        default=lambda a: a.tolist()), encoding='utf-8')


def building_for_case(name):
    from apt305_building import build_bui
    b = build_bui()
    b['building']['construction_class'] = 'class_i'
    b['building_parameters']['ventilation']['infiltration_modulation'] = 'constant'
    angular, convection = CASES[name]
    b['building_parameters'].setdefault('simulation_options', {}).update({
        'profile_start_year': 2025,  # Dec 2025 warm-up, Jan-Dec 2026 reporting
        'profile_use_holidays': False,  # same weekday/weekend calendar as IDF
        'dynamic_window_properties': True,
        'dynamic_surface_heat_transfer': True,
        'window_angular_solar_model': angular,
        'window_convection_model': convection,
        'external_convection_model': convection,
    })
    return b


def run(args):
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from pybuildingenergy.source import utils as u
    from pybuildingenergy.source.check_input import sanitize_and_validate_BUI
    from pybuildingenergy.source.ventilation import VentilationInternalGains
    from corrected_vs_energyplus import build_matched_idf, run_energyplus, read_sql
    from audit_energyplus_airflow import audit_airflow
    from weather_melbourne import CANONICAL_EPW

    ep = args.energyplus or shutil.which('energyplus')
    if not ep:
        candidate = ROOT / '.runtime' / 'energyplus' / 'energyplus'
        if candidate.exists():
            ep = str(candidate)
    if not ep:
        raise SystemExit('Install EnergyPlus 24.1.0 and supply --energyplus PATH, '
                         'or use --download-energyplus on Linux x86_64.')
    ep = str(Path(ep).resolve())
    version = subprocess.check_output([ep, '--version'], text=True).strip()
    if '24.1.0' not in version:
        raise SystemExit('This experiment requires EnergyPlus 24.1.0: ' + version)
    out = Path(args.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'COMPLETE.json').unlink(missing_ok=True)
    for directory in ('inputs', 'hourly', 'figures', 'logs'):
        (out / directory).mkdir(exist_ok=True)
    epw = ROOT / 'weather_cache' / CANONICAL_EPW
    b = building_for_case('neither')

    # Reference specification is defined BEFORE any ISO simulation; it is never
    # inferred from a case's heating, cooling, zone temperatures or airflow.
    gains = {'base_W': 0., 'occupants_W': 84., 'appliances_W': 60., 'lighting_W': 0.}
    factor, wind_audit = u.resolve_local_wind_factor(b)
    inf = {'q50': 14., 'a_env': 13.5, 'volume': 54., 'n50': 3.5,
           'lbl_n': 20., 'n_inf_mean': .175, 'design_flow_m3_s': .002625}
    reference = {'gains_w': gains, 'infiltration': inf,
                 'neighbour_multiplier_present': False,
                 'calendar': {'report_year':2026, 'holidays':False, 'daylight_saving':False},
                 'adjacent_zones': b['adjacent_zones'],
                 'wind': {'factor': factor, 'audit': wind_audit}}
    # Check the corrected gains calculation against the prescribed watts.
    ig = VentilationInternalGains(b)
    for key, occup, app, light in [('occupants_W',1,0,0),('appliances_W',0,1,0),
                                    ('lighting_W',0,0,1)]:
        actual = ig.internal_gains(h_occup=occup, h_app=app, h_light=light,
            building_type_class=b['building']['building_type_class'], a_use=20.,
            unconditioned_zones_nearby=False)
        assert np.isclose(actual, gains[key]), (key, actual)
    assert np.isclose(u._envelope_area_m2(b), 13.5)
    assert np.isclose(u._zone_volume_m3(b), 54.)
    prescribed_h_inf = u._RHO_CP_AIR_WH_M3K * 54 * .175
    assert np.isclose(u._infiltration_h_ve_inf_w_k(b, 20, 0, 5), prescribed_h_inf)
    idf = build_matched_idf(b, reference, inf_mode='constant')
    write_json(out / 'inputs' / 'reference_specification.json', reference)
    print('Running ONE fixed EnergyPlus reference...', flush=True)
    ep_result = run_energyplus(idf, epw, ep, out / 'energyplus', tag='fixed_reference')
    assert ep_result['n_hours'] == 8760
    idf_path = out / 'energyplus' / 'fixed_reference.idf'
    fixed_idf_sha = digest(idf_path)
    write_json(out / 'energyplus_summary.json', ep_result)
    sql_path = out / 'energyplus' / 'fixed_referenceout.sql'
    audit = audit_airflow(sql_path)
    assert audit['continuous_ventilation_verified']
    write_json(out / 'airflow_audit.json', audit)
    sql = read_sql(sql_path)
    ep_hourly = pd.DataFrame({'heating_W': np.asarray(sql['heat_sens']) / 3600,
                             'cooling_W': np.asarray(sql['cool_sens']) / 3600})
    ep_hourly.to_csv(out / 'hourly' / 'energyplus.csv', index=False)
    months = np.repeat(np.arange(1,13), np.array([31,28,31,30,31,30,31,31,30,31,30,31])*24)
    rows, monthly, records = [], [], {}
    common = None
    for name, (angular, convection) in CASES.items():
        raw = building_for_case(name)
        import copy
        physical = copy.deepcopy(raw)
        physical['building_parameters'].pop('simulation_options', None)
        physical_json = json.dumps(physical, sort_keys=True, default=lambda a:a.tolist())
        if common is None:
            common = physical_json
        assert physical_json == common, 'Physical inputs changed across treatments'
        write_json(out / 'inputs' / (name + '.json'), raw)
        assert u._resolve_window_angular_model(raw) == angular
        assert u._resolve_window_convection_model(raw) == convection
        assert u._resolve_opaque_convection_model(raw) == convection
        clean, issues = sanitize_and_validate_BUI(raw, fix=True)
        assert not [i for i in issues if i['level'] == 'ERROR'], issues
        assert clean['building']['exposed_perimeter'] == 0
        print('Running ISO: ' + name, flush=True)
        with (out / 'logs' / (name + '.log')).open('w') as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                h, annual = u.ISO52016.Temperature_and_Energy_needs_calculation(
                    clean, weather_source='epw', path_weather_file=str(epw))[:2]
        assert len(h) == 8760
        qh = np.maximum(h['Q_HC'].to_numpy(), 0)
        qc = np.maximum(-h['Q_HC'].to_numpy(), 0)
        residual = h['Q_balance_residual'].to_numpy()
        assert np.isfinite(np.column_stack([qh,qc,residual])).all()
        assert np.max(np.abs(residual)) < 1e-6, name
        for vals, col in [(qh,'Q_H_sensible_kWh'),(qc,'Q_C_sensible_kWh')]:
            assert np.isclose(vals.sum()/1000, float(annual[col].iloc[0]), atol=1e-6)
        h.to_csv(out / 'hourly' / (name + '.csv.gz'), index=False, compression='gzip')
        records[name] = {'max_hourly_balance_residual_W': float(np.max(np.abs(residual))),
                         'latent_estimate_kWh': float(annual['Q_C_latent_kWh'].iloc[0])}
        for metric, vals, ep_vals in [('Heating', qh, ep_hourly.heating_W.to_numpy()),
                                      ('Cooling', qc, ep_hourly.cooling_W.to_numpy()),
                                      ('Total', qh+qc, ep_hourly.sum(axis=1).to_numpy())]:
            iso_kwh, ep_kwh = vals.sum()/1000, ep_vals.sum()/1000
            rows.append({'case':name, 'metric':metric, 'iso_kWh':iso_kwh,
                         'ep_kWh':ep_kwh, 'difference_kWh':iso_kwh-ep_kwh,
                         'difference_pct':100*(iso_kwh-ep_kwh)/ep_kwh,
                         'hourly_MAE_W':float(np.abs(vals-ep_vals).mean()),
                         'hourly_RMSE_W':float(np.sqrt(np.mean((vals-ep_vals)**2)))})
            if metric != 'Total':
                for m in range(1,13):
                    monthly.append({'case':name,'metric':metric,'month':m,
                        'iso_kWh':vals[months==m].sum()/1000,
                        'ep_kWh':ep_vals[months==m].sum()/1000})
        assert digest(idf_path) == fixed_idf_sha
    table = pd.DataFrame(rows)
    table.to_csv(out / 'comparison.csv', index=False)
    pd.DataFrame(monthly).to_csv(out / 'monthly.csv', index=False)
    effects = []
    for metric in ['Heating','Cooling','Total']:
        values = table[table.metric==metric].set_index('case').iso_kWh
        effects.append({'metric':metric,
            'angular_at_fixed_convection_kWh':values.angular_only-values.neither,
            'convection_at_fixed_optics_kWh':values.convection_only-values.neither,
            'interaction_kWh':values.both-values.angular_only-values.convection_only+values.neither})
    pd.DataFrame(effects).to_csv(out / 'factorial_effects.csv', index=False)
    write_json(out / 'balance_checks.json', records)
    plt.rcParams.update({'font.size':10, 'svg.fonttype':'none'})
    labels = ['Neither\nFw=1','Angular\nonly','Convection\nonly','Both',
              'Fixed\nFw=0.9','Fw=0.9 +\nconvection']
    fig, axes = plt.subplots(1,2,figsize=(12,4.8))
    for ax, metric in zip(axes,['Heating','Cooling']):
        data = table[table.metric==metric]
        ax.bar(np.arange(6),data.iso_kWh,color=['#68788d','#20878b','#ba7c22','#365bb5','#aaa','#888'])
        ax.axhline(data.ep_kWh.iloc[0],color='#a33131',ls='--',label='Fixed EnergyPlus')
        ax.set(xticks=np.arange(6),xticklabels=labels,ylabel='Sensible demand (kWh/year)',title=metric)
        ax.set_ylim(0, max(data.iso_kWh.max(), data.ep_kWh.iloc[0])*1.22)
        ax.legend(frameon=False, loc='upper right')
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Controlled apartment comparison — identical physical inputs')
    fig.tight_layout()
    for ext in ['png','svg']:
        fig.savefig(out/'figures'/('annual_demand.'+ext),dpi=300)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9,4.5))
    for j, metric in enumerate(['Heating','Cooling','Total']):
        ax.bar(np.arange(6)+(j-1)*.24,table[table.metric==metric].difference_pct,
               width=.24,label=metric)
    ax.axhline(0,color='black',lw=.7)
    ax.set(xticks=np.arange(6),xticklabels=labels,ylabel='Difference from EnergyPlus (%)',
           title='Signed annual disagreement with the same reference')
    ax.legend(frameon=False,ncol=3)
    ax.spines[['top','right']].set_visible(False)
    fig.tight_layout()
    for ext in ['png','svg']:
        fig.savefig(out/'figures'/('annual_disagreement.'+ext),dpi=300)
    plt.close(fig)
    lines = ['# Controlled comparison results','',
        'Verified fixes retained. One EnergyPlus 24.1.0 model was run once and used for all cases.',
        'Infiltration is prescribed at constant 0.175 ACH (0.002625 m3/s). This is a controlled scenario, not a replication of the earlier variable-infiltration headline.',
        'Angular transmission and convection are separate factors. Convection changes both windows and exposed opaque surfaces; window U responds through its exterior film.',
        'Neither uses the historical implementation Fw=1. The two Fw=0.9 cases check the standard fixed-factor alternative. Neither is NOT the original buggy engine.',
        '', '| Case | Heating kWh | Cooling kWh | Total difference % |', '|---|---:|---:|---:|']
    for name in CASES:
        d=table[table.case==name].set_index('metric')
        lines.append(f"| {name} | {d.loc['Heating','iso_kWh']:.3f} | {d.loc['Cooling','iso_kWh']:.3f} | {d.loc['Total','difference_pct']:+.3f} |")
    lines += ['',f"EnergyPlus: heating {ep_result['heating_kWh']:.3f}, cooling {ep_result['cooling_kWh']:.3f} kWh/year.", '',
              '## Interpretation by metric']
    for metric in ['Heating','Cooling','Total']:
        d=table[table.metric==metric].set_index('case')
        old=abs(d.loc['neither','difference_pct']); new=abs(d.loc['both','difference_pct'])
        verdict='narrows' if new<old else 'widens'
        lines.append(f'- {metric}: enabling both {verdict} the absolute percentage gap from {old:.3f}% to {new:.3f}%.')
    lines += ['', 'Annual agreement alone is insufficient: comparison.csv also reports hourly MAE and RMSE; monthly.csv preserves seasonal results.',
        'This is one zero-envelope-capacity apartment with assumed 20 C neighbours. It does not validate real housing, realistic construction storage, or infiltration prediction.',
        'EnergyPlus retains its own surface and solar algorithms. No parameters were fitted to improve agreement.',
        'The existing builder represents ISO internal capacitance through an EnergyPlus InternalMass object; matching nominal capacity does not make the thermal networks identical.',
        'Small annual net residuals are not used as proof of accuracy. Every ISO run must pass the independent hourly balance gate of 1e-6 W.', '']
    (out/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    sources = [ROOT/'run_controlled.py', ROOT/'examples'/'apt305_building.py',
               ROOT/'examples'/'baseline_vs_energyplus.py',ROOT/'examples'/'corrected_vs_energyplus.py']
    sources += sorted((ROOT/'pybuildingenergy'/'src').rglob('*.py'))
    write_json(out/'manifest.json', {'energyplus_version':version,'python':sys.version,
        'numpy':np.__version__,'pandas':pd.__version__, 'weather_sha256':digest(epw),
        'fixed_idf_sha256':fixed_idf_sha,'reference_run_count':1,'hours_per_case':8760,
        'cases':CASES,'sources':{str(p.relative_to(ROOT)):digest(p) for p in sources}})
    write_json(out/'COMPLETE.json',{'status':'passed','cases':len(CASES),
        'files':{str(p.relative_to(out)):digest(p) for p in sorted(out.rglob('*')) if p.is_file()}})
    print(table.to_string(index=False), flush=True)
    print('COMPLETE: '+str(out), flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--energyplus', help='Path to EnergyPlus 24.1.0 executable')
    parser.add_argument('--outdir',default=str(ROOT/'controlled_results'))
    parser.add_argument('--setup',action='store_true',help='Install pinned Python dependencies')
    parser.add_argument('--download-energyplus',action='store_true',help='Download Linux x86_64 EnergyPlus 24.1.0')
    args=parser.parse_args()
    if args.setup:
        subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/'pybuildingenergy'/'requirements.txt')],check=True)
    if args.download_energyplus:
        import platform
        if platform.system()!='Linux' or platform.machine() not in ['x86_64','AMD64']:
            raise SystemExit('Automatic EnergyPlus download supports Linux x86_64 only; install EnergyPlus 24.1.0 for your OS and use --energyplus.')
        dest=ROOT/'.runtime'/'energyplus'
        if not (dest/'energyplus').exists():
            dest.mkdir(parents=True,exist_ok=True)
            archive=dest.parent/'energyplus.tar.gz'
            urllib.request.urlretrieve(EP_URL,archive)
            with tarfile.open(archive) as tf:
                for member in tf.getmembers():
                    parts=Path(member.name).parts
                    if len(parts)<2: continue
                    member.name=str(Path(*parts[1:]))
                    tf.extract(member,dest,filter='data')
    for path in ['examples','pybuildingenergy/src','tools/diagnostics']:
        sys.path.insert(0,str(ROOT/path))
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
        os.environ.setdefault(name,'1')
    run(args)


if __name__=='__main__':
    main()
