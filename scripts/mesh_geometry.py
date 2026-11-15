"""Pure geometry for watertight, simple Assetto Corsa barrier collision meshes."""
import numpy as np


def guardrail_wall(points, normals, width, low, high):
    """Create a closed, continuous rectangular wall following a 3D rail centerline."""
    points = np.asarray(points, dtype=np.float64)
    normals = np.asarray(normals, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 2:
        raise ValueError("A barrier needs at least two 3D centerline points")
    if normals.shape != (len(points), 2):
        raise ValueError("Barrier normals must contain one horizontal vector per point")
    if not np.isfinite(points).all() or not np.isfinite(normals).all():
        raise ValueError("Barrier geometry must be finite")
    if not np.isfinite([width, low, high]).all() or width <= 0 or high <= low:
        raise ValueError("Barrier dimensions must be finite and positive")
    lengths = np.linalg.norm(normals, axis=1)
    if np.any(lengths <= 1e-12):
        raise ValueError("Barrier normals must be nonzero")
    normals = normals / lengths[:, None]

    vertices = []
    for point, normal in zip(points, normals):
        lateral = normal * (width / 2)
        minus, plus = point[:2] - lateral, point[:2] + lateral
        vertices.extend((
            [minus[0], minus[1], point[2] + low],
            [plus[0], plus[1], point[2] + low],
            [minus[0], minus[1], point[2] + high],
            [plus[0], plus[1], point[2] + high],
        ))

    faces = []
    for station in range(len(points) - 1):
        a, b = station * 4, (station + 1) * 4
        faces.extend((
            (a + 1, b + 1, b, a),
            (a, b, b + 2, a + 2),
            (b + 1, a + 1, a + 3, b + 3),
            (a + 2, b + 2, b + 3, a + 3),
        ))
    last = (len(points) - 1) * 4
    faces.extend(((1, 0, 2, 3), (last, last + 1, last + 3, last + 2)))
    return vertices, faces
