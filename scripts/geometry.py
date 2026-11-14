"""Metric geometry preparation; no Blender dependency."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import urllib.request

import numpy as np
import osqp
from PIL import Image
from pyproj import Transformer
import rasterio
from scipy.ndimage import gaussian_filter1d, median_filter, minimum_filter1d, map_coordinates
from scipy.spatial import cKDTree
from scipy.interpolate import BSpline, CubicSpline
from scipy import sparse

from shortening import derive_layout

ROOT = Path(__file__).resolve().parents[1]
FORWARD = Transformer.from_crs(4326, 32631, always_xy=True)
INVERSE = Transformer.from_crs(32631, 4326, always_xy=True)


def acquire_dem():
    folder = ROOT / 'data/dem'
    folder.mkdir(exist_ok=True)
    records = []
    for lon in (4, 5):
        name = f'Copernicus_DSM_COG_10_N36_00_E{lon:03d}_00_DEM'
        url = f'https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif'
        path = folder / f'N36E{lon:03d}.tif'
        if not path.exists():
            urllib.request.urlretrieve(url, path)
        with rasterio.open(path) as ds:
            assert ds.crs.to_epsg() == 4326 and ds.count == 1
            records.append(dict(url=url, file=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), shape=ds.shape, crs=str(ds.crs), nodata=ds.nodata))
    (folder / 'sources.json').write_text(json.dumps(records, indent=2)+'\n')
    print('DEM_OK tiles=2 CRS=EPSG:4326 bilinear_sampling=pixel_centers')


class DEM:
    def __init__(self, origin):
        self.origin = np.asarray(origin)
        self.tiles = []
        for path in sorted((ROOT / 'data/dem').glob('*.tif')):
            with rasterio.open(path) as ds:
                self.tiles.append((ds.read(1), ds.transform, ds.bounds, ds.nodata))
        if not self.tiles:
            raise ValueError('Run build.py dem first')

    def sample(self, xy):
        xy = np.asarray(xy)
        x,y = xy[...,0]+self.origin[0],xy[...,1]+self.origin[1]
        if x.size == 1:
            lon,lat = INVERSE.transform(x.item(),y.item())
            lon,lat = np.full(x.shape,lon),np.full(y.shape,lat)
        else:
            lon,lat = INVERSE.transform(x,y)
        result = np.full(lon.shape, np.nan)
        for data, transform, bounds, nodata in self.tiles:
            mask = (lon >= bounds.left) & (lon <= bounds.right) & (lat >= bounds.bottom) & (lat <= bounds.top)
            col, row = (~transform) * (lon[mask], lat[mask])
            values = map_coordinates(data, [row-.5, col-.5], order=1, mode='nearest')
            if nodata is not None:
                invalid = map_coordinates((data == nodata).astype(float), [row-.5,col-.5], order=1, mode='nearest')
                values = np.where(invalid > 0, np.nan, values)
            result[mask] = values
        if not np.isfinite(result).all():
            raise ValueError('DEM missing or nodata at requested coordinates')
        return result


def resample(points, spacing=2):
    points = np.asarray(points, dtype=float)
    if len(points) < 2 or points.ndim != 2 or not np.isfinite(points).all() or not np.isfinite(spacing) or spacing <= 0:
        raise ValueError('Need at least two finite points')
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    keep = np.r_[True, np.diff(s) > 1e-8]
    s, points = s[keep], points[keep]
    if len(s) < 2:
        raise ValueError('Route has zero length')
    target = np.linspace(0, s[-1], math.ceil(s[-1]/spacing)+1)
    return np.column_stack([np.interp(target, s, points[:, k]) for k in range(points.shape[1])]), target


def nearest_on_polyline(points, reference):
    reference = np.asarray(reference)
    _, nearest = cKDTree(reference).query(points,k=min(4,len(reference)))
    nearest = np.asarray(nearest).reshape(len(points),-1)
    indices = np.clip(np.concatenate([nearest,nearest-1],axis=1),0,len(reference)-2)
    a,b = reference[indices],reference[indices+1]
    ab = b-a
    t = np.clip(np.sum((points[:,None,:]-a)*ab,axis=2)/np.maximum(np.sum(ab*ab,axis=2),1e-12),0,1)
    projected = a+t[...,None]*ab
    best = np.argmin(np.sum((points[:,None,:]-projected)**2,axis=2),axis=1)
    return projected[np.arange(len(points)),best]


def smooth_xy(points, minimum_radius=12):
    base = np.asarray(points,dtype=float).copy()
    if base.ndim != 2 or base.shape[1] != 2 or len(base) < 2 or not np.isfinite(base).all() or not np.isfinite(minimum_radius) or minimum_radius <= 0:
        raise ValueError('Need finite points and positive minimum radius')
    if (np.linalg.norm(np.diff(base,axis=0),axis=1) <= 0).any():
        raise ValueError('Repeated centerline points')
    keep = {0,len(base)-1}
    stack = [(0,len(base)-1)]
    while stack:
        a,b = stack.pop()
        if b <= a+1:
            continue
        delta = base[b]-base[a]
        t = np.clip((base[a+1:b]-base[a])@delta/max(delta@delta,1e-12),0,1)
        distance = np.linalg.norm(base[a+1:b]-(base[a]+t[:,None]*delta),axis=1)
        i = int(np.argmax(distance))+a+1
        if distance.max() > 2:
            keep.add(i)
            stack.extend([(a,i),(i,b)])
    vertices = base[sorted(keep)]
    radius = minimum_radius*1.6
    while len(vertices) > 2:
        segments = np.diff(vertices,axis=0)
        lengths = np.linalg.norm(segments,axis=1)
        direction = segments/lengths[:,None]
        angle = np.r_[0,np.arctan2(direction[:-1,0]*direction[1:,1]-direction[:-1,1]*direction[1:,0],np.sum(direction[:-1]*direction[1:],axis=1)),0]
        distance = radius*np.tan(abs(angle)/2)
        conflicts = np.where(distance[:-1]+distance[1:] > lengths*.9)[0]
        if not len(conflicts):
            break
        i = int(conflicts[0])
        drop = i if i>0 and (i+1==len(vertices)-1 or abs(angle[i])<abs(angle[i+1])) else i+1
        vertices = np.delete(vertices,drop,axis=0)
    rounded = [vertices[0]]
    for i in range(1,len(vertices)-1):
        entry = vertices[i]-direction[i-1]*distance[i]
        center = entry+np.sign(angle[i])*radius*np.array([-direction[i-1,1],direction[i-1,0]])
        start = np.arctan2(*(entry-center)[::-1])
        theta = start+np.linspace(0,angle[i],max(2,math.ceil(abs(angle[i])*radius)+1))
        rounded.extend(center+radius*np.column_stack([np.cos(theta),np.sin(theta)]))
    rounded.append(vertices[-1])
    smooth,parameter = resample(rounded,1)
    for _ in range(60):
        smooth = gaussian_filter1d(smooth,4,axis=0,mode='nearest')
        smooth[[0, -1]] = base[[0, -1]]
        spline = CubicSpline(parameter,smooth,axis=0)
        probe = np.sort(np.r_[parameter,(parameter[:-1]+parameter[1:])/2])
        first,second = spline(probe,1),spline(probe,2)
        curvature = np.abs(first[:,0]*second[:,1]-first[:,1]*second[:,0])/np.maximum(np.linalg.norm(first,axis=1)**3,1e-12)
        if curvature.max() <= 1/(minimum_radius*1.12):
            return spline(parameter)
        smooth,parameter = resample(smooth,1)
    raise RuntimeError('Cannot meet minimum centerline radius')


def elevation_target(raw):
    return gaussian_filter1d(median_filter(raw,size=11,mode='nearest'),6,mode='nearest',truncate=2)


def smooth_elevation(raw, s):
    raw, s = np.asarray(raw), np.asarray(s)
    if len(raw) < 2 or raw.shape != s.shape or not np.isfinite(raw).all() or not np.isfinite(s).all():
        raise ValueError('Need finite elevations')
    ds = np.diff(s)
    if (ds <= 0).any():
        raise ValueError('Chainage must strictly increase')
    target = elevation_target(raw)
    knots = np.r_[np.repeat(s[0],4),np.arange(s[0]+10,s[-1],10),np.repeat(s[-1],4)]
    basis = BSpline.design_matrix(s,knots,3).tocsc()
    count = basis.shape[1]
    d1 = sparse.diags([-np.ones(count-1),np.ones(count-1)],[0,1],shape=(count-1,count),format='csc')
    d1 = sparse.diags(3/(knots[4:count+3]-knots[1:count])) @ d1
    d2 = sparse.diags([-np.ones(count-2),np.ones(count-2)],[0,1],shape=(count-2,count-1),format='csc')
    d2 = sparse.diags(2/(knots[4:count+2]-knots[2:count])) @ d2 @ d1
    constraint = sparse.csc_matrix(sparse.vstack([d1*10,d2*100],format='csc'))
    bound = np.r_[np.full(count-1,1.4),np.full(count-2,.1)]
    solver = osqp.OSQP()
    solver.setup(P=sparse.csc_matrix(2*basis.T@basis),q=-2*np.asarray(basis.T@target).ravel(),A=constraint,l=-bound,u=bound,eps_abs=1e-7,eps_rel=1e-7,max_iter=100000,polishing=True,verbose=False)
    result = solver.solve(raise_error=True)
    if result.info.status != 'solved':
        raise RuntimeError(f'Elevation fit: {result.info.status}')
    return basis @ result.x


def width_from_tags(tags):
    def number(value):
        match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(m)?\s*', str(value))
        return float(match[1]) if match else None
    width = number(tags.get('width'))
    if width and 2 <= width <= 30:
        return width
    lanes = number(tags.get('lanes'))
    if lanes and 1 <= lanes <= 8:
        return lanes*3.25
    return {'trunk': 7., 'primary': 7., 'secondary': 6.5}.get(tags.get('highway', '').split('_')[0], 6.)


def runs(mask, s, gap=12, minimum=30):
    mask = np.asarray(mask, dtype=bool).copy()
    def intervals(m):
        edges = np.diff(np.r_[False, m, False].astype(int))
        return zip(np.where(edges == 1)[0], np.where(edges == -1)[0]-1)
    for a, b in list(intervals(~mask)):
        if a > 0 and b < len(mask)-1 and s[b]-s[a] <= gap:
            mask[a:b+1] = True
    for a, b in list(intervals(mask)):
        if s[b]-s[a] < minimum:
            mask[a:b+1] = False
    return mask


def frames(xy, s):
    xy, s = np.asarray(xy,dtype=float), np.asarray(s,dtype=float)
    if xy.shape != (len(s),2) or len(s) < 2 or not np.isfinite(xy).all() or not np.isfinite(s).all() or (np.diff(s) <= 0).any():
        raise ValueError('Need finite planar points and increasing chainage')
    segment = np.diff(xy,axis=0)
    if (np.linalg.norm(segment,axis=1) < 1e-8).any():
        raise ValueError('Repeated centerline point')
    segment /= np.linalg.norm(segment,axis=1)[:,None]
    tangent = np.vstack([segment[0],segment[:-1]+segment[1:],segment[-1]])
    if (np.linalg.norm(tangent,axis=1) < 1e-8).any():
        raise ValueError('Centerline reverses direction')
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    normal = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    derivative = np.gradient(tangent, s, axis=0)
    curvature = tangent[:, 0]*derivative[:, 1]-tangent[:, 1]*derivative[:, 0]
    return tangent, normal, curvature


def section_offsets(width, budget):
    half = width/2
    kerb = np.full(len(width),.3)
    shoulder = np.full(len(width),1.5)
    inner = half+kerb+shoulder
    outer = np.maximum(budget,inner+.1)
    return np.column_stack([half,half+kerb,inner,*[inner+(outer-inner)*f for f in (.2,.4,.65,1.)]])


def safe_sections(xy, normal, width, budget, sign):
    if len(xy) < 2 or sign not in (-1,1) or not np.isfinite(budget).all() or (budget <= 0).any():
        raise ValueError('Need positive finite offset budgets and a side')
    budget = budget.copy()
    for _ in range(60):
        cols = section_offsets(width,budget)
        positions = xy[:,None,:]+sign*normal[:,None,:]*cols[...,None]
        a,b,c,d = positions[:-1,:-1],positions[1:,:-1],positions[1:,1:],positions[:-1,1:]
        cross = lambda u,v: u[...,0]*v[...,1]-u[...,1]*v[...,0]
        bad = np.where(np.any((cross(b-a,c-a)*sign <= 1e-9) | (cross(c-a,d-a)*sign <= 1e-9),axis=1))[0]
        if not len(bad):
            return cols, positions
        for k in (-2,-1,0,1,2,3):
            indices = np.unique(np.clip(bad+k,0,len(budget)-1))
            budget[indices] *= .8
    raise RuntimeError('Cannot construct non-folded cross sections')


def boundary_crossings(points):
    points = np.asarray(points)
    if not len(points):
        return np.empty((0,2),dtype=int)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all():
        raise ValueError('Need a finite polygon boundary')
    a,b = points,np.roll(points,-1,axis=0)
    pairs = cKDTree((a+b)/2).query_pairs(np.linalg.norm(b-a,axis=1).max(),output_type='ndarray')
    i,j = pairs.T
    cross = lambda u,v: u[:,0]*v[:,1]-u[:,1]*v[:,0]
    bad = (cross(b[i]-a[i],a[j]-a[i])*cross(b[i]-a[i],b[j]-a[i]) < -1e-9) & (cross(b[j]-a[j],a[i]-a[j])*cross(b[j]-a[j],b[i]-a[j]) < -1e-9)
    return pairs[bad]


def safe_ribbon(xy,normal,width,budget):
    budget = budget.copy()
    n = len(xy)
    sample_index = np.r_[np.arange(n),np.arange(n)[::-1]]
    for _ in range(60):
        sections = [safe_sections(xy,normal,width,budget[:,side],sign) for side,sign in enumerate((1,-1))]
        budget = np.column_stack([cols[:,-1] for cols,_ in sections])
        outline = np.concatenate([sections[0][1][:,-1],sections[1][1][::-1,-1]])
        crossings = boundary_crossings(outline)
        road = np.stack([sections[1][1][:,0],sections[0][1][:,0]],axis=1)
        a,b,c,d = road[:-1,0],road[1:,0],road[1:,1],road[:-1,1]
        cross = lambda u,v: u[:,0]*v[:,1]-u[:,1]*v[:,0]
        folded = np.where((cross(b-a,c-a) <= 1e-9) | (cross(c-a,d-a) <= 1e-9))[0]
        if not len(crossings) and not len(folded):
            return sections
        edges = crossings.ravel()
        bad = np.r_[sample_index[edges],sample_index[(edges+1)%(2*n)],folded,folded+1]
        for k in range(-4,5):
            budget[np.unique(np.clip(bad+k,0,n-1))] *= .85
    raise RuntimeError('Cannot construct a simple non-folded ribbon')


def centerline():
    route = json.loads((ROOT/'data/route.geojson').read_text())['features'][0]['geometry']['coordinates']
    xy = np.column_stack(FORWARD.transform(*np.asarray(route).T))
    origin = np.round(xy[0])
    (ROOT/'data/geo_origin.json').write_text(json.dumps(dict(crs='EPSG:32631', easting_m=origin[0], northing_m=origin[1], z_origin_m=0, convention='Blender X=east Y=north Z=elevation; round projected start to nearest meter'), indent=2)+'\n')
    source = xy-origin
    reference = np.concatenate([*[np.linspace(a,b,math.ceil(np.linalg.norm(b-a)/2)+1)[:-1] for a,b in zip(source,source[1:])],source[-1:]])
    base, original_s = resample(source)
    smooth = smooth_xy(base)
    xy,new_s = resample(smooth)
    nearest_index = cKDTree(base).query(xy)[1]
    original_s,base = original_s[nearest_index],base[nearest_index]
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    tangent, normal, curvature = frames(xy, s)
    dem = DEM(origin)
    raw = dem.sample(xy)
    z = smooth_elevation(raw, s)
    filtered = elevation_target(raw)
    info = json.loads((ROOT/'data/route_info.json').read_text())
    road_ends = np.cumsum([r['length_m'] for r in info['roads']])
    road_index = np.minimum(np.searchsorted(road_ends, original_s/original_s[-1]*road_ends[-1]), len(road_ends)-1)
    widths = np.array([width_from_tags(info['roads'][i]) for i in road_index])
    widths = gaussian_filter1d(widths, 7.5, mode='nearest', truncate=2)
    # Conservative inner-curve limits and non-local centerline proximity.
    radius = 1/np.maximum(np.abs(curvature), 1e-8)
    limits = np.full((len(s), 2), 60.)
    for side, sign in enumerate((1, -1)):
        inner = curvature*sign > 0
        limits[inner, side] = radius[inner]*.8
    tree = cKDTree(xy)
    for i, neighbors in enumerate(tree.query_ball_point(xy, 100)):
        neighbors = np.asarray(neighbors)
        neighbors = neighbors[np.abs(s[neighbors]-s[i]) > 120]
        if len(neighbors):
            delta = xy[neighbors]-xy[i]
            for side, sign in enumerate((1, -1)):
                same_side = delta @ normal[i]*sign > 0
                if same_side.any():
                    limits[i, side] = min(limits[i, side], np.linalg.norm(delta[same_side], axis=1).min()*.44)
    limits = minimum_filter1d(limits, size=7, axis=0, mode='nearest')
    # Contract cross sections before the curve's focal point.
    terrain_extent = np.minimum(widths[:, None]/2+41.8, limits)
    points, offsets = [], []
    sections = safe_ribbon(xy,normal,widths,terrain_extent)
    for side, (cols,positions) in enumerate(sections):
        terrain_extent[:,side] = cols[:,-1]
        sampled = gaussian_filter1d(dem.sample(positions), 3, axis=0, mode='nearest')
        heights = np.empty_like(cols)
        heights[:, 0] = z
        heights[:, 1] = z+.02
        heights[:, 2] = z-.08
        blend = np.array([.2, .4, .65, 1.])**1.5
        heights[:, 3:] = (z[:, None]-.08)*(1-blend) + sampled[:, 3:]*blend
        heights[:, 3] = np.minimum(heights[:, 3], z-.04)
        points.append(np.dstack([positions, heights]))
        offsets.append(cols)
    points = np.array(points)
    coast = []
    cache = json.loads((ROOT/'data/area_cache.json').read_text())
    for w in cache['ways']:
        if w['tags'].get('natural') == 'coastline':
            projected = np.column_stack(FORWARD.transform(*np.asarray(w['coords']).T))-origin
            dense, _ = resample(projected, 10)
            coast.extend(dense)
    coast = np.asarray(coast)
    coast_distance, coast_index = cKDTree(coast).query(xy)
    guard, cut = [], []
    for side, sign in enumerate((1, -1)):
        side_z = dem.sample(xy+normal*sign*15)
        sea = (coast_distance < 60) & (np.sum((coast[coast_index]-xy)*normal, axis=1)*sign > 0)
        guard.append(runs(sea | (side_z < z-4), s))
        cut.append(runs((side_z > z+4) & ~guard[-1], s))
    grade = np.diff(z)/np.diff(s)
    actual_width = offsets[0][:,0]+offsets[1][:,0]
    metrics = dict(length_m=float(s[-1]), length_3d_m=float(np.linalg.norm(np.diff(np.column_stack([xy,z]), axis=0), axis=1).sum()), samples=len(s), min_elevation_m=float(z.min()), max_elevation_m=float(z.max()), max_grade_percent=float(abs(grade).max()*100), total_climb_m=float(np.maximum(np.diff(z),0).sum()), min_radius_m=float(radius.min()), max_xy_deviation_m=float(np.linalg.norm(xy-nearest_on_polyline(xy,reference),axis=1).max()), max_sample_displacement_m=float(np.linalg.norm(xy-base,axis=1).max()), max_grade_change_per_m=float(np.max(abs(np.diff(grade))/((np.diff(s)[:-1]+np.diff(s)[1:])/2))), width_range_m=[float(widths.min()),float(widths.max())], actual_min_width_m=float(actual_width.min()), narrowed_length_m=float(np.diff(s)[actual_width[:-1]<widths[:-1]-.01].sum()), min_terrain_extent_m=float(terrain_extent.min()), ribbon_boundary_crossings=0, guardrail_m=[float(np.sum(np.diff(s)*a[:-1])) for a in guard], cut_m=[float(np.sum(np.diff(s)*a[:-1])) for a in cut])
    heading = np.unwrap(np.arctan2(np.diff(xy,axis=0)[:,1],np.diff(xy,axis=0)[:,0]))
    metrics.update(mean_abs_elevation_error_m=float(np.mean(abs(z-filtered))),max_abs_elevation_error_m=float(np.max(abs(z-filtered))),mean_signed_elevation_error_m=float(np.mean(z-filtered)),max_heading_change_rad_per_m=float(np.max(abs(np.diff(heading))/((np.diff(s)[:-1]+np.diff(s)[1:])/2))))
    median_dem = median_filter(raw,size=11,mode='nearest')
    interval = (s >= 11000)&(s <= 19000)
    metrics.update(mean_abs_median_dem_error_m=float(np.mean(abs(z-median_dem))),max_abs_median_dem_error_m=float(np.max(abs(z-median_dem))),mean_signed_elevation_error_11_19km_m=float(np.mean((z-filtered)[interval])),max_curvature_change_per_m2=float(np.max(abs(np.gradient(curvature,s)))))
    full=dict(xy=xy,z=z,s=s,raw=raw,filtered=filtered,width=widths,normal=normal,tangent=tangent,sides=np.array(points),offsets=np.array(offsets),guard=np.array(guard),cut=np.array(cut))
    active,metrics=derive_layout(full,metrics)
    xy,z,s,raw,filtered=(active[key] for key in ('xy','z','s','raw','filtered'))
    (ROOT/'data/geometry_info.json').write_text(json.dumps(metrics, indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(14,4))
    distance=active['s3'];spawn=float(np.interp(float(active['spawn_s']),s,distance))
    ax.plot((distance-spawn)/1000, raw, color='#a4a4a4', lw=.7, label='Raw bilinear DSM')
    ax.plot((distance-spawn)/1000,filtered,color='#4378a8',lw=.8,label='Median / Gaussian target')
    ax.plot((distance-spawn)/1000, z, color='#d44a2d', lw=1.4, label='Retained road (no new smoothing)')
    ax.axvline(0,color='#333333',lw=1,label='Vehicle spawn')
    ax.axvline(1,color='#4378a8',lw=1,ls='--',label='Main summit: 1.000 km from spawn')
    ax.set(xlabel='3D road distance from pole spawn (km)', ylabel='Elevation (m, DSM datum)', title='RN24 summit approach → Saket | shortened elevation profile (not surveyed)')
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(ROOT/'out/preview/elevation_profile.png', dpi=160)
    print('CENTERLINE_OK', json.dumps(metrics))


def textures():
    rng = np.random.default_rng(24024)
    folder = ROOT/'textures'
    folder.mkdir(exist_ok=True)
    palettes = dict(asphalt=(60,63,65), grass=(89,105,60), gravel=(153,143,119), rock=(139,128,108), metal=(157,164,167), kerb=(188,179,151))
    for name, color in palettes.items():
        noise = rng.normal(0, 8 if name != 'metal' else 2, (1024,1024,1))
        rgb = np.clip(np.array(color)+noise,0,255).astype('uint8')
        if name == 'asphalt':
            rgb[:, 24:38] = (224,221,202)
            rgb[:, 986:1000] = (224,221,202)
            rgb[:440, 506:518] = (229,223,193)
        Image.fromarray(rgb).save(folder/f'{name}.png')


def mesh(blender):
    if not (ROOT/'data/centerline.npz').exists():
        raise ValueError('Run build.py centerline first')
    textures()
    env = os.environ.copy()
    runtime = Path('/run/user')/str(os.getuid())
    if not env.get('XDG_RUNTIME_DIR') and runtime.is_dir() and runtime.stat().st_uid == os.getuid():
        env['XDG_RUNTIME_DIR'] = str(runtime)
    subprocess.run([blender, '-b', '--python-exit-code', '1', '-P', str(ROOT/'scripts/blender_mesh.py')], check=True, cwd=ROOT, env=env)
