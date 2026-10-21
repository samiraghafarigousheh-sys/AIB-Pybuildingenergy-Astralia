"""Three-stage controlled comparison for the revised October methodology.

No fit to EnergyPlus; input-only construction adaptation retains class_i.
Run: python run_revision.py --energyplus /path/to/energyplus
ISO only, against archived references:
     python run_revision.py --reuse-energyplus revision_results --outdir new_results
"""
from pathlib import Path
import argparse, copy, json, hashlib, os, re, subprocess, sys
ROOT=Path(__file__).resolve().parent
for p in ['examples','pybuildingenergy/src','tools/diagnostics']:
    sys.path.insert(0,str(ROOT/p))
import numpy as np
import pandas as pd
import run_controlled as control
import run_australia as construction
from pybuildingenergy.source import utils as u
from corrected_vs_energyplus import build_matched_idf, run_energyplus, read_sql, _hourly_schedule
from weather_melbourne import CANONICAL_EPW

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x): control.write_json(p,x)

def configuration(q50=4., variant='neither', layers=False, flow='weather'):
    b=construction.scenario('external_mass','class',variant) if layers else control.building_for_case(variant)
    b['building']['construction_year']=2006
    # Preserve the same optical assumption across ALL treatments and stages.
    for s in b['building_surface']:
        if s['type']=='transparent': s['glazing_panes']=2
        assert 'construction_layers' not in s, 'Experimental layer mapping must be disabled'
    v=b['building_parameters']['ventilation']
    v['envelope_permeability_q50']=q50
    v['infiltration_modulation']='constant' if flow=='constant' else 'stack_wind'
    v['infiltration_reference_temperature_C']=20.
    v['infiltration_multiplier_decimals']=6
    return b

def airflow(b,epw):
    v=b['building_parameters']['ventilation']
    w=pd.read_csv(epw,skiprows=8,header=None)
    assert len(w)==8760
    if v['infiltration_modulation']=='constant': return np.ones(8760)
    return np.round(np.sqrt((u._INF_C_STACK*abs(20-w[6].to_numpy())+
            u._INF_C_WIND*w[21].to_numpy()**2)/(u._INF_C_STACK*10+u._INF_C_WIND*16)),6)

def reference(b,epw):
    q=b['building_parameters']['ventilation']['envelope_permeability_q50']
    factor,audit=u.resolve_local_wind_factor(b)
    spec={'gains_w':dict(base_W=0.,occupants_W=84.,appliances_W=60.,lighting_W=0.),
          'infiltration':dict(q50=q,a_env=13.5,volume=54.,n50=q*13.5/54,
                             lbl_n=20.,n_inf_mean=q*13.5/54/20,
                             design_flow_m3_s=q*13.5/20/3600),
          'neighbour_multiplier_present':False,'adjacent_zones':b['adjacent_zones'],
          'wind':dict(factor=factor,audit=audit),'f_mod':airflow(b,epw)}
    idf=build_matched_idf(b,spec,inf_mode='iso-schedule')
    idf=idf.replace('precomputed from the corrected ISO run','prescribed from weather and 20 C before either engine runs')
    # Reuse the previously audited material export and aligned shared-boundary
    # films, but replace its hard-coded q50=14 infiltration with this scenario.
    if any('scenario_layers' in s for s in b['building_surface']):
        layered=construction.reference_idf(b)
        pattern=r'ZoneInfiltration:DesignFlowRate,[^;]*;'
        obj=re.search(pattern,idf,re.S).group(0)
        layered,n=re.subn(pattern,lambda m:obj,layered,flags=re.S)
        assert n==1
        # Use exactly the same weather multiplier as the diagnostic reference.
        layered+='\n'+_hourly_schedule('Inf_Mod','Any Number',spec['f_mod'])
        idf=layered
    return idf, spec

def saved_reference(src,ref,out):
    """Copy an archived EnergyPlus reference instead of rerunning EnergyPlus."""
    import shutil
    shutil.copytree(src/'energyplus'/ref,out/'energyplus'/ref,dirs_exist_ok=True)
    saved=pd.read_csv(src/'hourly'/(ref+'_energyplus.csv'))
    saved.to_csv(out/'hourly'/(ref+'_energyplus.csv'),index=False)
    raw=read_sql(out/'energyplus'/ref/'referenceout.sql')
    eh=np.asarray(raw['heat_sens'])/3600;ec=np.asarray(raw['cool_sens'])/3600
    np.testing.assert_allclose(eh,saved.heating_W,rtol=0,atol=1e-9)
    np.testing.assert_allclose(ec,saved.cooling_W,rtol=0,atol=1e-9)
    return eh,ec

def run(args):
    out=Path(args.outdir).resolve()
    reuse=Path(args.reuse_energyplus).resolve() if args.reuse_energyplus else None
    if reuse:
        if reuse==out: raise SystemExit('--outdir must differ from the archived results directory')
        version=json.loads((reuse/'COMPLETE.json').read_text())['energyplus_version']
    else:
        if not args.energyplus: raise SystemExit('Supply --energyplus PATH or --reuse-energyplus DIR')
        ep=str(Path(args.energyplus).resolve())
        version=subprocess.check_output([ep,'--version'],text=True).strip()
    assert '24.1.0' in version
    for d in ['inputs','hourly','logs','energyplus']: (out/d).mkdir(parents=True,exist_ok=True)
    (out/'COMPLETE.json').unlink(missing_ok=True)
    epw=ROOT/'weather_cache'/CANONICAL_EPW
    # Stage 1/2 retain the historical low-leakage assumption (q50=4).
    # Stage 3 independently changes q50 to the 2006 default 11 and restores
    # construction R/C from the existing illustrative Australian assemblies.
    jobs=[('original','stage1',4.,'neither',False,'weather','original','diagnostic_q4'),
          ('repaired','stage1',4.,'neither',False,'weather','corrected','diagnostic_q4'),
          ('without_infiltration','stage1',0.,'neither',False,'weather','corrected','diagnostic_q4'),
          ('angular_only','stage2',4.,'angular_only',False,'weather','corrected','diagnostic_q4'),
          ('convection_only','stage2',4.,'convection_only',False,'weather','corrected','diagnostic_q4'),
          ('both','stage2',4.,'both',False,'weather','corrected','diagnostic_q4'),
          ('au_leakage_only','stage3',11.,'both',False,'weather','corrected','diagnostic_q11'),
          ('au_construction_only','stage3',4.,'both',True,'weather','corrected','layers_q4'),
          ('au_combined','stage3',11.,'both',True,'weather','corrected','layers_q11'),
          ('q14_sensitivity','sensitivity',14.,'both',False,'weather','corrected','diagnostic_q14'),
          ('q11_constant','sensitivity',11.,'both',False,'constant','corrected','diagnostic_q11_constant'),
          ('archive_reproduction','reproduction',14.,'neither',False,'constant','corrected','diagnostic_q14_constant')]
    dump(out/'design.json',{'jobs':jobs,'primary_q50':4,'AU_q50':11,
         'reference_construction':'Original diagnostic U values with zero opaque capacity',
         'AU_construction':'Existing illustrative layer inputs; ISO class_i retained; replaces both R and total C',
         'flow':'Weather multiplier prescribed at 20 C; six-decimal schedule shared between engines',
         'calendar':'December 2025 warmup, 2026 reporting; no holidays',
         'age_defaults':'Provisional scenario values, not measured calibration'})
    references={}; rows=[]; monthly=[]; checks={}
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    months=np.repeat(np.arange(1,13),np.array([31,28,31,30,31,30,31,31,30,31,30,31])*24)
    for name,stage,q,variant,layers,flow,engine,ref in jobs:
        b=configuration(q,variant,layers,flow)
        if ref not in references and reuse:
            print('REFERENCE (archived)',ref,flush=True)
            eh,ec=saved_reference(reuse,ref,out)
            references[ref]=(eh,ec,sha(out/'energyplus'/ref/'reference.idf'))
        if ref not in references:
            rb=configuration(4. if q==0 else q,'neither',layers,flow)
            idf,spec=reference(rb,epw)
            print('REFERENCE',ref,flush=True)
            summary=run_energyplus(idf,epw,ep,out/'energyplus'/ref,tag='reference')
            raw=read_sql(out/'energyplus'/ref/'referenceout.sql')
            eh=np.asarray(raw['heat_sens'])/3600;ec=np.asarray(raw['cool_sens'])/3600
            assert len(eh)==8760 and np.isfinite(np.c_[eh,ec]).all()
            references[ref]=(eh,ec,sha(out/'energyplus'/ref/'reference.idf'))
            pd.DataFrame({'heating_W':eh,'cooling_W':ec,'airflow_multiplier':spec['f_mod']}).to_csv(out/'hourly'/(ref+'_energyplus.csv'),index=False)
            dump(out/'energyplus'/ref/'specification.json',spec)
        eh,ec,refhash=references[ref]
        config=out/'inputs'/(name+'.json'); dump(config,b)
        dest=out/'hourly'/(name+'.csv.gz')
        print('ISO',name,flush=True)
        with (out/'logs'/(name+'.log')).open('w') as log:
            subprocess.run([sys.executable,str(ROOT/'revision_worker.py'),engine,str(config),str(dest)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        h=pd.read_csv(dest); a=h.Q_HC.to_numpy(); yh=np.maximum(a,0);yc=np.maximum(-a,0)
        checks[name]=json.loads(Path(str(dest)+'.json').read_text())
        for metric,y,z in [('Heating',yh,eh),('Cooling',yc,ec),('Total',yh+yc,eh+ec)]:
            e=float(y.sum()/1000);r=float(z.sum()/1000)
            rows.append(dict(case=name,stage=stage,reference=ref,metric=metric,iso_kWh=e,ep_kWh=r,
                difference_kWh=e-r,bias_pct=(100*(e-r)/r if r>1e-8 else None),
                RMSE_W=float(np.sqrt(np.mean((y-z)**2))),MAE_W=float(abs(y-z).mean())))
            for m in range(1,13):
                monthly.append(dict(case=name,metric=metric,month=m,iso_kWh=float(y[months==m].sum()/1000),ep_kWh=float(z[months==m].sum()/1000)))
        assert sha(out/'energyplus'/ref/'reference.idf')==refhash
        pd.DataFrame(rows).to_csv(out/'comparison.csv',index=False)
        pd.DataFrame(monthly).to_csv(out/'monthly.csv',index=False)
        dump(out/'checks.json',checks)
        print(rows[-1],flush=True)
    for name in ['angular_only','convection_only','both']:
        base=pd.read_csv(out/'hourly/repaired.csv.gz'); h=pd.read_csv(out/'hourly'/(name+'.csv.gz'))
        for col in ['H_ve','Q_internal_gains']: np.testing.assert_allclose(h[col],base[col],rtol=0,atol=1e-9)
    dump(out/'COMPLETE.json',{'status':'passed','energyplus_version':version,'ISO_runs':len(jobs),
         'EnergyPlus_runs':len(references),'weather_sha256':sha(epw),
         'energyplus_references':'archived, not rerun' if reuse else 'simulated',
         'original_commit':'2e6e910c1297ff3e88bad3184a4f1e74e1a93815',
         'sources':{str(p.relative_to(ROOT)):sha(p) for p in list((ROOT/'pybuildingenergy/src').rglob('*.py'))+[Path(__file__),ROOT/'revision_worker.py']}})

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--energyplus')
    p.add_argument('--reuse-energyplus',metavar='DIR',help='archived results directory whose EnergyPlus references are reused')
    p.add_argument('--outdir',default=str(ROOT/'revision_results'));run(p.parse_args())
