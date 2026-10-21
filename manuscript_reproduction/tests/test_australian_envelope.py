import copy
import numpy as np
import pytest
from pybuildingenergy.source.australian_envelope import layer_properties,layer_network,POSITIONS
from pybuildingenergy.source.utils import ISO52016

LAYERS=[dict(resistance_m2K_W=.15,capacity_J_m2K=150000),dict(resistance_m2K_W=1.5,capacity_J_m2K=1000),dict(resistance_m2K_W=.05,capacity_J_m2K=12000)]

def test_conserves_resistance_capacity_and_first_moment():
    rc=layer_properties(LAYERS);g,c=layer_network(LAYERS)
    edges=np.r_[0,np.cumsum(rc[:,0])/sum(rc[:,0])]
    assert np.isclose(sum(1/g),sum(rc[:,0]))
    assert np.isclose(sum(c),sum(rc[:,1]))
    assert np.isclose(c@POSITIONS,rc[:,1]@((edges[:-1]+edges[1:])/2))
    assert np.all(c>=0)

def test_reversing_layers_reverses_capacity():
    assert np.allclose(layer_network(LAYERS)[1],layer_network(LAYERS[::-1])[1][::-1])

@pytest.mark.parametrize('layers', [[],[dict(resistance_m2K_W=-1)],[dict(resistance_m2K_W=1,capacity_J_m2K=-1)],[dict(resistance_m2K_W=float('nan'))]])
def test_invalid_layers_rejected(layers):
    with pytest.raises(ValueError):layer_network(layers)

def test_metadata_survives_aggregation():
    b={'building_surface':[{'construction_layers':LAYERS}], 'building_parameters':{}}
    assert ISO52016._aggregate_surfaces_by_direction(b)==b

def test_solver_uses_layer_properties():
    s=dict(ISO52016_type_string='OP',u_value=.5,thermal_capacity=1,construction_layers=LAYERS,
           convective_heat_transfer_coefficient_internal=2.5,radiative_heat_transfer_coefficient_internal=5,
           convective_heat_transfer_coefficient_external=20,radiative_heat_transfer_coefficient_external=4)
    b={'building':{'construction_class':'class_i'},'building_surface':[s]}
    g=ISO52016.Conductance_node_of_element(copy.deepcopy(b)).h_pli_eli[:,0]
    c=ISO52016.Areal_heat_capacity_of_element(copy.deepcopy(b)).kappa_pli_eli[:,0]
    assert np.allclose(g,layer_network(LAYERS)[0])
    assert np.allclose(c,layer_network(LAYERS)[1])

def test_reference_prescribed_films_match_each_neighbour():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import run_australia as run
    from baseline_vs_energyplus import SURFACE_TO_OSC
    b=run.scenario('external_mass')
    idf=run.reference_idf(b)
    surfaces={s['name']:s for s in b['building_surface']}
    for ep,name in SURFACE_TO_OSC.items():
        s=surfaces[name]
        h=s['convective_heat_transfer_coefficient_external']+s['radiative_heat_transfer_coefficient_external']
        assert 'SurfaceProperty:OtherSideCoefficients, OSC_'+ep+', '+str(h)+', 20, 1, 0, 0, 0, 0;' in idf
    assert run.reference_idf(run.scenario('external_mass','class'))==idf
