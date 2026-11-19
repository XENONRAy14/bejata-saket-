"""Pure geometry for watertight, simple Assetto Corsa barrier collision meshes."""
import numpy as np


def rail_stations(data, side):
    """One selection for physics and art, including the old roadside drop criterion."""
    drop = data['sides'][side, :, -1, 2] - data['z']
    return data['guard'][side] | ((drop < -6) & (data['s'] >= 20) & (data['s'] <= data['s'][-1]-20))


def w_beam(points, outward):
    """Sweep a two-rib steel sheet, with a return at each lip and a closed back."""
    points = np.asarray(points, dtype=np.float64)
    outward = np.asarray(outward, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 2:
        raise ValueError("A W-beam needs at least two 3D centerline points")
    if outward.shape != (len(points), 2):
        raise ValueError("W-beam normals must contain one horizontal vector per point")
    if not np.isfinite(points).all() or not np.isfinite(outward).all():
        raise ValueError("W-beam geometry must be finite")
    lengths = np.linalg.norm(outward, axis=1)
    if np.any(lengths <= 1e-12):
        raise ValueError("W-beam normals must be nonzero")
    outward = outward / lengths[:, None]
    skin = [(.035,.54),(-.013,.55),(-.075,.615),(.0,.69),
            (-.075,.765),(-.013,.83),(.035,.84)]
    ring = skin + [(x+.004,z) for x,z in reversed(skin)]
    k = len(ring)
    vertices = [[*(p[:2]+n*x), p[2]+z] for p,n in zip(points,outward) for x,z in ring]
    faces = [(i*k+j, (i+1)*k+j, (i+1)*k+(j+1)%k, i*k+(j+1)%k)
             for i in range(len(points)-1) for j in range(k)]
    for j in range(len(skin)-1):
        cap = (j,j+1,k-2-j,k-1-j)
        faces.extend([tuple(reversed(cap)), tuple((len(points)-1)*k+i for i in cap)])
    if np.cross(np.r_[points[1][:2]-points[0][:2],0], np.r_[outward[0],0])[2] < 0:
        faces = [f[::-1] for f in faces]
    return vertices, faces


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
