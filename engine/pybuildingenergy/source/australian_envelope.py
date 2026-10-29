"""Experimental per-surface layer mapping; inputs are outside-to-inside.

This is a five-node approximation, not a calibrated Australian archetype model.
Resistance excludes surface films. Capacity is in J/(m2 K).
"""
import numpy as np
POSITIONS = np.array([0., 1/6, 1/2, 5/6, 1.])
CLASS_WEIGHTS = {'class_i':[0,0,0,0,1], 'class_e':[1,0,0,0,0],
                 'class_ie':[.5,0,0,0,.5], 'class_d':[.125,.25,.25,.25,.125],
                 'class_m':[0,0,1,0,0]}

def layer_properties(layers):
    if not layers:
        raise ValueError('At least one construction layer is required')
    values = []
    for layer in layers:
        if 'resistance_m2K_W' in layer:
            r = float(layer['resistance_m2K_W'])
            c = float(layer.get('capacity_J_m2K', 0))
        else:
            d,k,rho,cp = [float(layer[key]) for key in
                ('thickness_m','conductivity_W_mK','density_kg_m3','specific_heat_J_kgK')]
            if not np.isfinite([d,k,rho,cp]).all() or min(d,k,rho,cp) <= 0:
                raise ValueError('Material properties must be finite and positive')
            r,c = d/k,d*rho*cp
        if not np.isfinite([r,c]).all() or r <= 0 or c < 0:
            raise ValueError('Layer resistance must be positive and capacity nonnegative')
        values.append((r,c))
    return np.array(values)

def layer_network(layers):
    rc = layer_properties(layers)
    edges = np.r_[0., np.cumsum(rc[:,0])/rc[:,0].sum()]
    capacity = np.zeros(5)
    for (lo,hi),(_,c) in zip(zip(edges[:-1],edges[1:]),rc):
        for j,(left,right) in enumerate(zip(POSITIONS[:-1],POSITIONS[1:])):
            a,b = max(lo,left),min(hi,right)
            if b > a:
                wr = ((a+b)/2-left)/(right-left)
                amount = c*(b-a)/(hi-lo)
                capacity[j] += amount*(1-wr)
                capacity[j+1] += amount*wr
    return 1/(np.diff(POSITIONS)*rc[:,0].sum()),capacity

def apply_overrides(building, array, capacity=False):
    for i,surface in enumerate(building['building_surface']):
        layers = surface.get('construction_layers')
        cls = surface.get('construction_class')
        if layers is None and cls is None:
            continue
        if surface['ISO52016_type_string'] not in ('OP','ADJ'):
            raise ValueError('Construction overrides support OP and ADJ surfaces only')
        if layers is not None:
            array[:,i] = layer_network(layers)[int(capacity)]
        elif capacity:
            if cls not in CLASS_WEIGHTS:
                raise ValueError('Unknown construction class: '+str(cls))
            c = float(surface['thermal_capacity'])
            if not np.isfinite(c) or c < 0:
                raise ValueError('Invalid surface capacity')
            array[:,i] = c*np.array(CLASS_WEIGHTS[cls])
    return array
