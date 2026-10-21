"""Independent checks of saved hourly results and EnergyPlus schedule delivery."""
from pathlib import Path
import json, sys, sqlite3, re
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/diagnostics'))
from audit_energyplus_airflow import audit_airflow, _hourly
out=ROOT/'revision_results'
assert json.loads((out/'COMPLETE.json').read_text())['status']=='passed'
design=json.loads((out/'design.json').read_text())
records={}; refs={}
for name,stage,q,variant,layers,flow,engine,ref in design['jobs']:
    h=pd.read_csv(out/'hourly'/(name+'.csv.gz'))
    b=json.loads((out/'inputs'/(name+'.json')).read_text())
    assert len(h)==8760 and np.isfinite(h.Q_HC).all()
    entry={'hours':len(h),'internal_gains_kWh':float(h.Q_internal_gains.sum()/1000),
           'ground_flow_absolute_kWh':float(abs(h.Q_ground).sum()/1000)}
    if engine!='original':
        # Continuous prescribed ventilation = rho cp 0.040 = 48.44896 W/K.
        mult=pd.read_csv(out/'hourly'/(ref+'_energyplus.csv')).airflow_multiplier.to_numpy()
        expected=1.204*1006*.040+.33*q*13.5/20*mult
        np.testing.assert_allclose(h.H_ve,expected,atol=1e-8,rtol=0)
        entry['max_airflow_conductance_error_W_K']=float(abs(h.H_ve-expected).max())
        entry['max_balance_residual_W']=float(abs(h.Q_balance_residual).max())
        assert entry['max_balance_residual_W']<1e-6
        assert entry['ground_flow_absolute_kWh']==0
        surface_count=len([c for c in h if c.startswith('Q_tr_surface_')])
        assert surface_count==(8 if layers else 7)
        entry['transmission_surface_entries']=surface_count
    if ref not in refs:
        sql=out/'energyplus'/ref/'referenceout.sql'
        audit=audit_airflow(sql); assert audit['continuous_ventilation_verified']
        audit['sql']=str(sql.relative_to(ROOT))
        with sqlite3.connect(sql) as con:
            schedule=_hourly(con.cursor(),'Schedule Value','Inf_Mod')
        if schedule is not None:
            expected=pd.read_csv(out/'hourly'/(ref+'_energyplus.csv')).airflow_multiplier.to_numpy()
            np.testing.assert_allclose(schedule,expected,atol=1e-9,rtol=0)
            audit['infiltration_schedule_max_error']=float(abs(np.array(schedule)-expected).max())
        # Inspect the actual input design flow, independently of saved spec.
        idf=(out/'energyplus'/ref/'reference.idf').read_text()
        compact=re.search(r'Schedule:Compact,\s*Inf_Mod,([^;]+);',idf,re.S).group(1)
        values=np.array([float(x) for x in re.findall(r'Until:\s*\d+:\d+,\s*([0-9.eE+-]+)',compact)])
        expected=pd.read_csv(out/'hourly'/(ref+'_energyplus.csv')).airflow_multiplier.to_numpy()
        assert len(values)==8760
        np.testing.assert_allclose(values,expected,atol=1e-9,rtol=0)
        audit['infiltration_input_schedule_max_error']=float(abs(values-expected).max())
        audit['infiltration_output_schedule_available']=schedule is not None
        fields=re.search(r'ZoneInfiltration:DesignFlowRate,([^;]+);',idf,re.S).group(1).split(',')
        flowrate=float(fields[4]); rq=4 if q==0 else q
        assert abs(flowrate-rq*13.5/20/3600)<5.1e-9
        refs[ref]=audit
    records[name]=entry
# Historical run is a reproduction check, not part of the new main comparison.
data=pd.read_csv(out/'comparison.csv')
repro=data[data['case']=='archive_reproduction'].set_index('metric')
assert abs(repro.loc['Heating','iso_kWh']-124.46)<.01
assert abs(repro.loc['Cooling','iso_kWh']-19.30)<.01
assert abs(repro.loc['Total','ep_kWh']-171.4743)<.001
result={'status':'passed','cases':records,'references':refs,
        'historical_reproduction':'Original and corrected historical totals reproduced within reporting precision'}
(out/'audit_revision.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'status':'passed','cases':len(records),'references':len(refs)},indent=2))
