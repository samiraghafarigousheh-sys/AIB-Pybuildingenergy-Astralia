import sys
from pathlib import Path
import copy
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_revision as r
from pybuildingenergy.source import utils as u

@pytest.mark.parametrize('year,expected',[(2006,11.),('2006',11.),('2006.0',11.),(2005,14.),('2006-today',11.),(1975,20.)])
def test_numeric_year_uses_age_band(year,expected):
    assert u._q50_for_construction_age({'building':{'construction_year':year}})==expected

def test_input_only_construction_keeps_capacity_class():
    b=r.configuration(11,'both',True)
    assert b['building']['construction_class']=='class_i'
    opaque=[s for s in b['building_surface'] if s['type']!='transparent']
    assert all('construction_layers' not in s for s in opaque)
    assert all(s['thermal_capacity']>0 for s in opaque)
    expected=.11*1700*840+.06*20*1030+.013*800*1090
    assert opaque[0]['thermal_capacity']==pytest.approx(expected)

def test_weather_flow_matches_independent_formula():
    b=r.configuration(11)
    h=u._infiltration_h_ve_inf_w_k(b,35,10,4)
    expected=.33*11*13.5/20
    assert h==pytest.approx(expected)
    # Fixed driver deliberately removes solver-temperature feedback.
    assert h==u._infiltration_h_ve_inf_w_k(b,5,10,4)
    b['building_parameters']['ventilation'].pop('infiltration_reference_temperature_C')
    assert u._infiltration_h_ve_inf_w_k(b,35,10,4)!=h

def test_leakage_and_construction_factor_independence():
    a=r.configuration(4,'both',True);b=r.configuration(11,'both',True)
    a['building_parameters']['ventilation']['envelope_permeability_q50']=11
    assert r.json.dumps(a,default=lambda x:x.tolist(),sort_keys=True)==r.json.dumps(b,default=lambda x:x.tolist(),sort_keys=True)
    b=r.configuration(11,'both',False)
    assert all(s.get('thermal_capacity',0)==0 for s in b['building_surface'])
