"""Static KN5 validation for continuous full-route guardrail collision meshes."""
import configparser
import json
from pathlib import Path

import numpy as np

from check_kn5 import inspect_kn5
from mesh_geometry import guardrail_wall, rail_stations

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = np.load(ROOT / 'data/centerline.npz')
    parsed = inspect_kn5(ROOT / 'out/bejaia_saket/bejaia_saket.kn5', geometry='all')
    nodes = {node['name']: node for node in parsed['nodes']}
    meshes = [node for node in parsed['nodes'] if node['kind'] == 2]
    colliders = {
        name: node for name, node in nodes.items()
        if name.startswith('1WALL_COLLIDER_GUARD_')
    }
    visuals = {
        name: node for name, node in nodes.items()
        if name.startswith('DETAIL_GUARD_')
    }
    assert colliders and len(colliders) == len(visuals)
    assert set(colliders) == {
        name.replace('DETAIL_GUARD_', '1WALL_COLLIDER_GUARD_', 1)
        for name in visuals
    }
    assert all(
        node['visible'] and not node['renderable'] and not node['castShadows']
        for node in colliders.values()
    )
    assert all(node['visible'] and node['renderable'] for node in visuals.values())
    assert all(node['tangent_stats']['finite'] for node in colliders.values())

    ends = np.unique(np.r_[
        0, np.searchsorted(source['s'], np.arange(400, source['s'][-1], 400)),
        len(source['s']) - 1,
    ])
    expected_names = set()
    total_triangles = 0
    min_triangle_area = float('inf')
    for chunk, (a, b) in enumerate(zip(ends, ends[1:])):
        for side, letter in enumerate(('L', 'R')):
            active = np.flatnonzero(
                rail_stations(source, side)[a:b] & rail_stations(source, side)[a + 1:b + 1]
            )
            if not len(active):
                continue
            name = f'1WALL_COLLIDER_GUARD_{chunk:03d}_{letter}'
            expected_names.add(name)
            groups = np.split(active, np.flatnonzero(np.diff(active) > 1) + 1)
            expected_vertices = []
            for edges in groups:
                indices = a + np.r_[edges[:1], edges + 1]
                vertices, _ = guardrail_wall(
                    source['sides'][side, indices, 2], source['normal'][indices],
                    .18, -.08, .95,
                )
                expected_vertices.extend(vertices)
            expected = np.asarray(expected_vertices, dtype='<f4')[:, [0, 2, 1]]
            expected[:, 2] *= -1
            node = colliders[name]
            actual = np.unique(node['positions'], axis=0)
            np.testing.assert_array_equal(
                actual, np.unique(expected, axis=0),
                err_msg=f'Incomplete or extra collision geometry: {name}',
            )
            triangles = node['positions'][node['indices']]
            areas = np.linalg.norm(
                np.cross(
                    triangles[:, 1] - triangles[:, 0],
                    triangles[:, 2] - triangles[:, 0],
                ),
                axis=1,
            )
            assert np.isfinite(areas).all() and np.all(areas > 1e-8), name
            min_triangle_area = min(min_triangle_area, float(areas.min()))
            total_triangles += node['triangles']

    assert set(colliders) == expected_names
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.read(ROOT / 'out/bejaia_saket/data/surfaces.ini', encoding='utf-8')
    import re
    physical_keys = {
        match[1] for node in meshes
        if (match := re.match(r'^\d+([A-Z]+)', node['name']))
    }
    surface_keys = {config[section]['KEY'] for section in config.sections()}
    assert physical_keys == surface_keys, (sorted(physical_keys), sorted(surface_keys))

    result = {
        'kn5_bytes': parsed['bytes'],
        'vertices': sum(node['vertices'] for node in meshes),
        'triangles': sum(node['triangles'] for node in meshes),
        'guardrail_sections': len(colliders),
        'visible_guardrail_sections': len(visuals),
        'collision_triangles': total_triangles,
        'minimum_collision_triangle_area_m2': min_triangle_area,
        'collision_nodes_visible_but_nonrenderable': True,
        'all_collision_geometry_matches_source': True,
    }
    print('GUARDRAIL_KN5_VALIDATION_PASS ' + json.dumps(result))


if __name__ == '__main__':
    main()
