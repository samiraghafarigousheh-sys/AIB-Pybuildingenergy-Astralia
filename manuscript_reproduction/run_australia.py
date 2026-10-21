"""Matched illustrative construction experiment. See AUSTRALIA_README.md."""
from pathlib import Path
import argparse, contextlib, copy, hashlib, json, re, subprocess, sys, time
ROOT = Path(__file__).resolve().parent
for folder in ('examples','pybuildingenergy/src','tools/diagnostics'):
    sys.path.insert(0,str(ROOT/folder))
import numpy as np
import pandas as pd
import run_controlled as control
from pybuildingenergy.source import utils as u
from pybuildingenergy.source.australian_envelope import layer_properties
from pybuildingenergy.source.check_input import sanitize_and_validate_BUI
from corrected_vs_energyplus import build_matched_idf, run_energyplus, read_sql

def material(name,d,k,rho,cp):
    return dict(name=name,thickness_m=d,conductivity_W_mK=k,density_kg_m3=rho,specific_heat_J_kgK=cp)
BRICK=material('brick',.11,.77,1700,840)
INSULATION=material('insulation',.06,.04,20,1030)
PLASTER=material('plasterboard',.013,.25,800,1090)
CONCRETE=material('concrete',.2,1.7,2300,880)
BLOCK=material('block',.09,.6,1400,840)

def scenario(name,mode='layers',variant='neither'):
    b=control.building_for_case(variant)
    if name=='diagnostic':
        return b
    b['building_parameters']['simulation_options']['preserve_construction_surfaces']=True
    ext=[BRICK,INSULATION,PLASTER] if name=='external_mass' else [PLASTER,INSULATION,BRICK]
    for s in b['building_surface']:
        if s['type']=='transparent':
            s['glazing_panes']=1
            continue
        layers=ext if s['type']=='opaque' else ([PLASTER,CONCRETE,PLASTER] if 'floor' in s['name'].lower() or 'ceiling' in s['name'].lower() else [PLASTER,BLOCK,PLASTER])
        rc=layer_properties(layers)
        u._apply_surface_heat_transfer_defaults(s)
        films=sum(1/(s['convective_heat_transfer_coefficient_'+side]+s['radiative_heat_transfer_coefficient_'+side]) for side in ('internal','external'))
        s['u_value']=1/(rc[:,0].sum()+films)
        s['thermal_capacity']=rc[:,1].sum()
        s['scenario_layers']=copy.deepcopy(layers)
        if mode=='layers':
            s['construction_layers']=copy.deepcopy(layers)
    return b

def reference_idf(b,timestep=6):
    factor,audit=u.resolve_local_wind_factor(b)
    ref={'gains_w':{'base_W':0.,'occupants_W':84.,'appliances_W':60.,'lighting_W':0.},
         'infiltration':{'q50':14.,'a_env':13.5,'volume':54.,'n50':3.5,'lbl_n':20.,'n_inf_mean':.175,'design_flow_m3_s':.002625},
         'neighbour_multiplier_present':False,'adjacent_zones':b['adjacent_zones'],
         'wind':{'factor':factor,'audit':audit}}
    idf=build_matched_idf(b,ref,inf_mode='constant',timestep=timestep)
    groups={}
    for s in b['building_surface']:
        if 'scenario_layers' not in s:
            continue
        name='Con_ExtWall' if s['type']=='opaque' else ('Con_IntSlab' if 'floor' in s['name'].lower() or 'ceiling' in s['name'].lower() else 'Con_IntWall')
        if name in groups:
            assert groups[name]==s['scenario_layers']
        groups[name]=s['scenario_layers']
    for name,layers in groups.items():
        names=[name+'_layer_'+str(i) for i in range(len(layers))]
        idf,n=re.subn(r'Construction,\s*'+name+r'\s*,[^;]*;', 'Construction, '+name+', '+', '.join(names)+';',idf,flags=re.I)
        assert n==1
        for lname,l in zip(names,layers):
            idf+='\nMaterial, '+lname+', MediumRough, '+', '.join(str(l[k]) for k in ('thickness_m','conductivity_W_mK','density_kg_m3','specific_heat_J_kgK'))+', 0.9, 0.75, 0.75;\n'
    # The fixed neighbouring temperature is separated from the surface by a
    # prescribed film. Use the same film per boundary in both input models.
    # EnergyPlus's room-side convection/radiation algorithms remain unchanged.
    if groups:
        from baseline_vs_energyplus import SURFACE_TO_OSC
        surfaces={s['name']:s for s in b['building_surface']}
        for ep_name,bui_name in SURFACE_TO_OSC.items():
            surf=surfaces[bui_name]
            h=surf['convective_heat_transfer_coefficient_external']+surf['radiative_heat_transfer_coefficient_external']
            osc='OSC_'+ep_name
            pattern=r'(BuildingSurface:Detailed,\s*'+ep_name+r',.*?OtherSideCoefficients,\s*)OSC_Adj'
            idf,n=re.subn(pattern,lambda m:m.group(1)+osc,idf,flags=re.S|re.I)
            assert n==1
            idf+='\nSurfaceProperty:OtherSideCoefficients, '+osc+', '+str(h)+', 20, 1, 0, 0, 0, 0;\n'
    return idf

def run(args):
    ep=str(Path(args.energyplus).resolve())
    version=subprocess.check_output([ep,'--version'],text=True).strip()
    assert '24.1.0' in version, version
    out=Path(args.outdir).resolve();out.mkdir(parents=True,exist_ok=True)
    (out/'COMPLETE.json').unlink(missing_ok=True)
    for folder in ('inputs','hourly','logs'):
        (out/folder).mkdir(exist_ok=True)
    from weather_melbourne import CANONICAL_EPW
    epw=ROOT/'weather_cache'/CANONICAL_EPW
    rows=[]; monthly=[]; checks={}
    months=np.repeat(np.arange(1,13),np.array([31,28,31,30,31,30,31,31,30,31,30,31])*24)
    for name in args.scenarios:
        b=scenario(name)
        idf=reference_idf(b,args.timestep)
        print('EnergyPlus: '+name,flush=True)
        summary=run_energyplus(idf,epw,ep,out/'energyplus'/name,tag='reference')
        assert summary['n_hours']==8760
        sql=read_sql(out/'energyplus'/name/'referenceout.sql')
        eh=np.asarray(sql['heat_sens'])/3600;ec=np.asarray(sql['cool_sens'])/3600
        pd.DataFrame({'heating_W':eh,'cooling_W':ec}).to_csv(out/'hourly'/(name+'_energyplus.csv'),index=False)
        treatments=['class_neither'] if name=='diagnostic' else args.treatments
        for treatment in treatments:
            mode,variant=treatment.split('_')
            label=name+'_'+treatment
            b=scenario(name,mode,variant)
            control.write_json(out/'inputs'/(label+'.json'),b)
            clean,issues=sanitize_and_validate_BUI(copy.deepcopy(b),fix=True)
            assert not [i for i in issues if i['level']=='ERROR'],issues
            print('ISO: '+label,flush=True);start=time.time()
            with (out/'logs'/(label+'.log')).open('w') as log, contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
                h,annual=u.ISO52016.Temperature_and_Energy_needs_calculation(clean,weather_source='epw',path_weather_file=str(epw))[:2]
            assert len(h)==8760
            qh=np.maximum(h.Q_HC.to_numpy(),0);qc=np.maximum(-h.Q_HC.to_numpy(),0)
            residual=h.Q_balance_residual.to_numpy()
            assert np.isfinite(np.c_[qh,qc,residual]).all()
            assert abs(residual).max()<1e-6
            h.to_csv(out/'hourly'/(label+'.csv.gz'),index=False,compression='gzip')
            checks[label]={'runtime_seconds':time.time()-start,'max_balance_residual_W':float(abs(residual).max()),'idf_sha256':hashlib.sha256(idf.encode()).hexdigest()}
            for metric,v,e in [('Heating',qh,eh),('Cooling',qc,ec),('Total',qh+qc,eh+ec)]:
                a,z=v.sum()/1000,e.sum()/1000
                row=dict(scenario=name,treatment=treatment,metric=metric,iso_kWh=a,ep_kWh=z,difference_kWh=a-z,difference_pct=(100*(a-z)/z if z>=1 else None),hourly_RMSE_W=np.sqrt(np.mean((v-e)**2)))
                rows.append(row);print(row,flush=True)
                if metric!='Total':
                    for m in range(1,13):
                        monthly.append(dict(scenario=name,treatment=treatment,metric=metric,month=m,iso_kWh=v[months==m].sum()/1000,ep_kWh=e[months==m].sum()/1000))
            pd.DataFrame(rows).to_csv(out/'comparison.csv',index=False)
            pd.DataFrame(monthly).to_csv(out/'monthly.csv',index=False)
            control.write_json(out/'checks.json',checks)
            assert (out/'energyplus'/name/'reference.idf').read_text()==idf
    control.write_json(out/'COMPLETE.json',dict(energyplus_version=version,weather_sha256=control.digest(epw),timestep=args.timestep,scenarios=args.scenarios,treatments=args.treatments,sources={str(p.relative_to(ROOT)):control.digest(p) for p in [Path(__file__),ROOT/'pybuildingenergy/src/pybuildingenergy/source/utils.py',ROOT/'pybuildingenergy/src/pybuildingenergy/source/australian_envelope.py']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--energyplus',required=True)
    p.add_argument('--outdir',default='australia_results')
    p.add_argument('--scenarios',nargs='+',choices=['diagnostic','external_mass','internal_mass'],default=['diagnostic','external_mass','internal_mass'])
    p.add_argument('--treatments',nargs='+',choices=['class_neither','layers_neither','class_both','layers_both'],default=['class_neither','layers_neither','class_both','layers_both'])
    p.add_argument('--timestep',type=int,default=6)
    run(p.parse_args())
