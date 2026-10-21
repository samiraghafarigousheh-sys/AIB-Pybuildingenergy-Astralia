"""Isolated annual simulation; original source receives calendar adaptation only."""
import sys, json, importlib.util
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent
engine, config, destination = sys.argv[1:]
src = ROOT / ('original/pybuildingenergy/src' if engine == 'original' else 'pybuildingenergy/src')
sys.path.insert(0, str(src))
if engine == 'original':
    import pybuildingenergy.source.generate_profile as gp
    spec = importlib.util.spec_from_file_location('pinned_profile', ROOT/'pybuildingenergy/src/pybuildingenergy/source/generate_profile.py')
    pinned = importlib.util.module_from_spec(spec); spec.loader.exec_module(pinned)
    class Calendar(pinned.HourlyProfileGenerator):
        def __init__(self, *a, **kw):
            kw.update(start_year=2025, use_holidays=False)
            super().__init__(*a, **kw)
    gp.HourlyProfileGenerator = Calendar
    gp.get_country_code_from_latlon = lambda *a, **kw: 'AU'
from pybuildingenergy.source import utils as u
from pybuildingenergy.source.check_input import sanitize_and_validate_BUI
b = json.loads(Path(config).read_text())
for zone in b.get('adjacent_zones',[]):
    for key in ['area_facade_elements','typology_elements','transmittance_U_elements','orientation_elements']:
        if key in zone: zone[key]=np.asarray(zone[key])
clean, issues = sanitize_and_validate_BUI(b, fix=True)
assert not [i for i in issues if i['level']=='ERROR'], issues
sys.path.insert(0, str(ROOT/'examples'))
from weather_melbourne import CANONICAL_EPW
h, annual = u.ISO52016.Temperature_and_Energy_needs_calculation(clean,
    weather_source='epw', path_weather_file=str(ROOT/'weather_cache'/CANONICAL_EPW))[:2]
assert len(h)==8760 and np.isfinite(h.Q_HC).all()
check={'engine':engine,'hours':len(h),'validation_issues':issues}
if engine!='original':
    residual=float(abs(h.Q_balance_residual).max())
    assert residual<1e-6, residual
    check['max_balance_residual_W']=residual
for col in ['Q_internal_gains','H_ve']:
    if col in h:
        check[col+'_sum']=float(h[col].sum())
h.to_csv(destination,index=False,compression='gzip')
Path(destination+'.json').write_text(json.dumps(check,indent=2))
