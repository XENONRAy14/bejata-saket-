import unittest
from collections import Counter

import numpy as np

from mesh_geometry import guardrail_wall, rail_collision_section, rail_stations, w_beam
from validate_guardrail_collisions import validate_faces


class GuardrailCollisionGeometryTests(unittest.TestCase):
    def plane_fixture(self):
        sides = np.zeros((2, 5, 3, 3))
        sides[:, :, 2, 0] = np.arange(5)
        sides[:, :, 2, 1] = np.array([[3], [-3]])
        sides[:, :, 2, 2] = np.arange(5) * .2
        return dict(s=np.arange(5), z=np.zeros(5), sides=sides,
                    normal=np.tile([0., 1.], (5, 1)),
                    guard=np.tile([True, True, False, True, True], (2, 1)))

    def test_planes_face_road_on_both_sides_and_do_not_bridge_gaps(self):
        for side, sign in enumerate((-1, 1)):
            vertices, faces = rail_collision_section(self.plane_fixture(), 0, 4, side)
            self.assertEqual(len(faces), 2)
            self.assertEqual(len(vertices), 8)
            for face in faces:
                polygon = np.asarray(vertices)[list(face)]
                self.assertAlmostEqual(float(np.ptp(polygon[:, 0])), 1.)
                normal = np.cross(polygon[1] - polygon[0], polygon[2] - polygon[0])
                np.testing.assert_allclose(normal, [0, sign*1.03, 0])

    def test_validate_planes_rejects_flipped_and_overlapping_triangles(self):
        vertices, faces = rail_collision_section(self.plane_fixture(), 0, 1, 0)
        x, y, z, w = faces[0]
        positions = np.asarray(vertices, dtype='<f4')[:, [0, 2, 1]]
        positions[:, 2] *= -1
        node = dict(name='test', positions=positions, indices=[[x, y, z], [x, z, w]])
        self.assertGreater(validate_faces(node, vertices, faces), 0)
        for bad in ([[z, y, x], [x, z, w]], [[x, y, z], [x, y, w]]):
            with self.assertRaises(AssertionError):
                validate_faces(dict(node, indices=bad), vertices, faces)

    def test_w_beam_is_a_closed_profile_with_finite_faces(self):
        points = np.array([[0, 0, 2], [4, 0, 2]], dtype=float)
        vertices, faces = w_beam(points, [[0, 1], [0, 1]])
        geometry = np.asarray(vertices)
        self.assertEqual(geometry.shape, (28, 3))
        self.assertTrue(np.isfinite(geometry).all())
        self.assertEqual(len(faces), 26)
        for face in faces:
            polygon = geometry[list(face)]
            for index in range(1, len(face) - 1):
                area = np.linalg.norm(
                    np.cross(polygon[index] - polygon[0], polygon[index + 1] - polygon[0])
                )
                self.assertGreater(float(area), 1e-10)

    def test_rail_selection_includes_drop_sections_and_protects_route_ends(self):
        data = {
            's': np.array([0, 10, 20, 30, 40, 50, 60], dtype=float),
            'z': np.zeros(7),
            'guard': np.array([[0, 1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 1, 0]], dtype=bool),
            'sides': np.zeros((2, 7, 3, 3), dtype=float),
        }
        data['sides'][:, :, -1, 2] = -7
        expected = np.array([
            [False, True, True, True, True, False, False],
            [False, False, True, True, True, True, False],
        ])
        for side in (0, 1):
            np.testing.assert_array_equal(rail_stations(data, side), expected[side])

    def test_wall_is_closed_and_all_faces_point_outward(self):
        vertices, faces = guardrail_wall(
            [[0, 0, 2], [4, 0, 2]],
            [[0, 1], [0, 1]],
            width=.18,
            low=-.08,
            high=.95,
        )
        points = np.asarray(vertices)
        self.assertEqual(points.shape, (8, 3))
        self.assertEqual(len(faces), 6)
        self.assertAlmostEqual(float(points[:, 2].max() - points[:, 2].min()), 1.03)

        edge_uses = Counter(
            tuple(sorted((face[i], face[(i + 1) % len(face)])))
            for face in faces
            for i in range(len(face))
        )
        self.assertEqual(set(edge_uses.values()), {2})

        center = points.mean(axis=0)
        for face in faces:
            polygon = points[list(face)]
            normal = np.cross(polygon[1] - polygon[0], polygon[2] - polygon[0])
            self.assertGreater(float(normal @ (polygon.mean(axis=0) - center)), 0)

    def test_curved_sloped_wall_has_no_degenerate_faces(self):
        points = np.array([[0, 0, 0], [2, 0, .2], [3.5, 1, .5]], dtype=float)
        delta = np.diff(points[:, :2], axis=0)
        tangent = np.vstack((delta[0], delta.mean(axis=0), delta[-1]))
        normals = np.column_stack((-tangent[:, 1], tangent[:, 0]))
        vertices, faces = guardrail_wall(points, normals, .2, -.1, .9)
        geometry = np.asarray(vertices)
        self.assertEqual(len(faces), 10)
        for face in faces:
            polygon = geometry[list(face)]
            area_vector = np.cross(polygon[1] - polygon[0], polygon[2] - polygon[0])
            self.assertGreater(float(np.linalg.norm(area_vector)), 1e-8)

    def test_invalid_barrier_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            guardrail_wall([[0, 0, 0]], [[0, 1]], .2, -.1, .9)
        with self.assertRaises(ValueError):
            guardrail_wall([[0, 0, 0], [1, 0, 0]], [[0, 0], [0, 1]], .2, -.1, .9)
        with self.assertRaises(ValueError):
            guardrail_wall([[0, 0, 0], [1, 0, 0]], [[0, 1], [0, 1]], .2, .9, -.1)


if __name__ == "__main__":
    unittest.main()
