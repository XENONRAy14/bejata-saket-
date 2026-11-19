"""Project-level source-to-export check, supplementary to standalone validate.py."""
import json
from pathlib import Path

import numpy as np

from acdata import plan_empties
from check_kn5 import inspect_kn5
from shortening import road_distance
from validate_guardrail_collisions import validate_guardrails

ROOT=Path(__file__).resolve().parents[1]


def main():
    data=np.load(ROOT/'data/centerline.npz');full=np.load(ROOT/'data/full_centerline.npz')
    info=json.loads((ROOT/'data/shortening_info.json').read_text())
    original=np.flatnonzero(full['s']>info['canonical_cut_2d_m'])
    retained=np.searchsorted(data['source_s'],full['s'][original])
    for key in ('xy','z','width','raw','filtered','normal','tangent'):
        np.testing.assert_array_equal(data[key][retained],full[key][original])
    for key in ('sides','offsets','guard','cut'):
        np.testing.assert_array_equal(data[key][:,retained],full[key][:,original])
    d=road_distance(data)
    summit=np.searchsorted(data['source_s'],info['canonical_summit_2d_m'])
    spawn=np.searchsorted(data['s'],float(data['spawn_s']))
    distance=float(d[summit]-d[spawn])
    assert abs(distance-1000)<1e-6,(distance,'spawn to summit')
    assert abs(d[spawn]-30)<1e-6,'rear pad length'
    parsed=inspect_kn5(ROOT/'out/bejaia_saket/bejaia_saket.kn5',geometry='all')
    nodes={node['name']:node for node in parsed['nodes']}
    roads=[node for name,node in nodes.items() if name.startswith('1ROAD_')]
    actual=np.unique(np.concatenate([n['positions'] for n in roads]),axis=0)
    expected=data['sides'][:,:,0,:].reshape(-1,3)[:,[0,2,1]].astype('<f4');expected[:,2]*=-1
    np.testing.assert_array_equal(actual,np.unique(expected,axis=0),err_msg='Extra/missing/moved road vertices in KN5')
    assert '1WALL_START_END' in nodes and '1WALL_END' in nodes,'missing physical end closure'
    assert 'DECOR_START_LINE' in nodes,'missing visible timing line'
    guardrail_count = validate_guardrails(parsed, data)['guardrail_sections']
    plan=plan_empties(data)
    for entry in plan['empties']:
        node=nodes[entry['name']];matrix=np.array(node['matrix']).reshape(4,4)
        expected=np.array(entry['position_m'])[[0,2,1]];expected[2]*=-1
        np.testing.assert_allclose(matrix[3,:3],expected,atol=.002,rtol=0)
        yaw=np.radians(entry['yaw_deg'])
        np.testing.assert_allclose(matrix[2,:3],[np.sin(yaw),0,np.cos(yaw)],atol=1e-6)
    mesh=[n for n in nodes.values() if n['kind']==2]
    print('SHORTENED_EXPORT_PASS '+json.dumps(dict(spawn_to_summit_3d_m=distance,rear_pad_3d_m=float(d[spawn]),retained_original_samples=len(original),retained_arrays_identical=True,exported_road_vertices_match=True,physical_end_barriers=True,guardrail_colliders=guardrail_count,exported_spawn_gate_matrices_match=True,length_3d_m=float(d[-1]),kn5_bytes=parsed['bytes'],vertices=sum(n['vertices'] for n in mesh),triangles=sum(n['triangles'] for n in mesh))))


if __name__=='__main__':main()
