"""Controlled repair switches; experimental monkeypatches never edit either engine.

Bits (0/1): neighbours, gains, ground/perimeter, infiltration.
The corrected reporting code is retained in every run. Original methods are
compiled directly from the archived source, rather than reimplemented.
"""
import ast
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'pybuildingenergy/src'))
from pybuildingenergy.source import utils as u, ventilation as v
from pybuildingenergy.source.check_input import sanitize_and_validate_BUI


def archived(relative, name, namespace, parent=None):
    path = ROOT / 'original/pybuildingenergy/src/pybuildingenergy/source' / relative
    tree = ast.parse(path.read_text())
    nodes = tree.body
    if parent:
        nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == parent).body
    node = next(n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    node.decorator_list = []
    scope = dict(namespace)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope[name]


def main():
    mask, config, destination = sys.argv[1:]
    assert len(mask) == 4 and set(mask) <= {'0', '1'}
    neighbours, gains, ground, infiltration = map(int, mask)
    b = json.loads(Path(config).read_text())
    for zone in b.get('adjacent_zones', []):
        for key in ['area_facade_elements', 'typology_elements', 'transmittance_U_elements', 'orientation_elements']:
            if key in zone:
                zone[key] = np.asarray(zone[key])
    clean, issues = sanitize_and_validate_BUI(b, fix=True)
    assert not [i for i in issues if i['level'] == 'ERROR'], issues
    if not neighbours:
        for zone in clean['adjacent_zones']:
            zone['conditioned'] = False
        last_b = u.ISO52016.transmission_heat_transfer_coefficient_ISO13789(clean['adjacent_zones'][-1])[1]
        current_theta = u._theta_ztu_unconditioned
        def legacy_theta(theta_int_prev, t_ext, b_ztu, phi_gn_dir_ztu, H_ztu, c_ztu_h_max=1.):
            return current_theta(theta_int_prev, t_ext, last_b, phi_gn_dir_ztu, H_ztu, c_ztu_h_max)
        u._theta_ztu_unconditioned = legacy_theta
        u.ISO52016._aggregate_surfaces_by_direction = classmethod(archived('utils.py', '_aggregate_surfaces_by_direction', vars(u), 'ISO52016'))
    if not gains:
        v.VentilationInternalGains.internal_gains = archived('ventilation.py', 'internal_gains', vars(v), 'VentilationInternalGains')
    if not ground:
        clean['building']['exposed_perimeter'] = 1.0
        # The archived method refers to the archived area resolver through its globals.
        scope = dict(vars(u))
        scope['_ground_contact_area'] = archived('utils.py', '_ground_contact_area', vars(u))
        u.ISO52016.Temp_calculation_of_ground = classmethod(archived('utils.py', 'Temp_calculation_of_ground', scope, 'ISO52016'))
    if not infiltration:
        u._infiltration_h_ve_inf_w_k = lambda *args, **kwargs: 0.0
    sys.path.insert(0, str(ROOT / 'examples'))
    from weather_melbourne import CANONICAL_EPW
    h, _ = u.ISO52016.Temperature_and_Energy_needs_calculation(clean, weather_source='epw', path_weather_file=str(ROOT / 'weather_cache' / CANONICAL_EPW))[:2]
    assert len(h) == 8760 and np.isfinite(h.Q_HC).all()
    metadata = {'mask': mask, 'hours': len(h), 'validation_issues': issues,
                'max_balance_residual_W': float(abs(h.Q_balance_residual).max()),
                'note': 'Legacy ground-off diagnostics retain phantom ground accounting; residual is not a physical closure check in those states.'}
    if ground:
        assert metadata['max_balance_residual_W'] < 1e-6
    h.to_csv(destination, index=False, compression='gzip')
    Path(destination + '.json').write_text(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
