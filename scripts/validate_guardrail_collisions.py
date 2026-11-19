"""Static KN5 validation for continuous full-route guardrail collision meshes."""
import configparser
from itertools import combinations
import json
from pathlib import Path
import re

import numpy as np

from check_kn5 import inspect_kn5
from mesh_geometry import rail_collision_section

ROOT = Path(__file__).resolve().parents[1]


def validate_faces(node, vertices, faces):
    name = node['name']
    expected = np.asarray(vertices, dtype='<f4')[:, [0, 2, 1]]
    expected[:, 2] *= -1
    actual = np.unique(node['positions'], axis=0)
    np.testing.assert_array_equal(actual, np.unique(expected, axis=0),
                                  err_msg=f'Incomplete or extra collision vertices: {name}')
    face_by_triangle, normals, exported = {}, [], [[] for _ in faces]
    for i, face in enumerate(faces):
        polygon = expected[list(face)]
        points = [tuple(p) for p in polygon]
        normals.append(np.cross(polygon[1] - polygon[0], polygon[2] - polygon[0]))
        for candidate in combinations(points, 3):
            face_by_triangle[frozenset(candidate)] = i
    triangles = node['positions'][node['indices']]
    vectors = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    areas = np.linalg.norm(vectors, axis=1) / 2
    assert np.isfinite(areas).all() and np.all(areas > 1e-8), name
    for triangle, normal in zip(triangles, vectors):
        corners = frozenset(map(tuple, triangle))
        i = face_by_triangle.get(corners)
        assert i is not None and np.dot(normal, normals[i]) > 0, (name, 'Invalid face or winding')
        exported[i].append(corners)
    for face, pair in zip(faces, exported):
        assert len(pair) == 2 and len(pair[0] | pair[1]) == 4, (name, 'Rail face is incomplete')
        polygon = expected[list(face)]
        assert pair[0] & pair[1] in (
            {tuple(polygon[0]), tuple(polygon[2])},
            {tuple(polygon[1]), tuple(polygon[3])},
        ), (name, 'Rail face has overlapping triangles')
    return float(areas.min())


def validate_guardrails(parsed, source):
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
        node['active'] and node['visible'] and not node['renderable'] and not node['castShadows']
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
            vertices, faces = rail_collision_section(source, a, b, side)
            if not faces:
                continue
            name = f'1WALL_COLLIDER_GUARD_{chunk:03d}_{letter}'
            expected_names.add(name)
            node = colliders[name]
            min_triangle_area = min(min_triangle_area, validate_faces(node, vertices, faces))
            total_triangles += node['triangles']

    assert set(colliders) == expected_names
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.read(ROOT / 'out/bejaia_saket/data/surfaces.ini', encoding='utf-8')
    physical_keys = {
        match[1] for node in meshes
        if (match := re.match(r'^\d+([A-Z]+)', node['name']))
    }
    surface_keys = {config[section]['KEY'] for section in config.sections()}
    assert 'WALL' not in surface_keys, 'WALL is a built-in collision type'
    assert physical_keys - {'WALL'} == surface_keys, (sorted(physical_keys), sorted(surface_keys))

    return {
        'kn5_bytes': parsed['bytes'],
        'vertices': sum(node['vertices'] for node in meshes),
        'triangles': sum(node['triangles'] for node in meshes),
        'guardrail_sections': len(colliders),
        'visible_guardrail_sections': len(visuals),
        'collision_triangles': total_triangles,
        'minimum_collision_triangle_area_m2': min_triangle_area,
        'collision_nodes_visible_but_nonrenderable': True,
        'all_collision_geometry_matches_source': True,
        'all_collision_faces_oriented_to_road': True,
    }


def main():
    source = np.load(ROOT / 'data/centerline.npz')
    parsed = inspect_kn5(ROOT / 'out/bejaia_saket/bejaia_saket.kn5', geometry='all')
    result = validate_guardrails(parsed, source)
    print('GUARDRAIL_KN5_VALIDATION_PASS ' + json.dumps(result))


if __name__ == '__main__':
    main()
