import unittest
from collections import Counter

import numpy as np

from mesh_geometry import guardrail_wall


class GuardrailCollisionGeometryTests(unittest.TestCase):
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
