"""Seeded, testable placements on the actual triangular terrain ribbons."""
import json
import os
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy.spatial import cKDTree

from acdata import ROOT, write_files

SEED = 24024
COLORS = dict(bark=(91,74,48),pine_foliage=(49,81,39),olive_foliage=(109,124,84),maquis=(74,96,47),plaster=(229,223,201),sand=(208,190,139),water=(32,107,146),marker_red=(173,39,32))
KINDS = ('pine','olive','shrub','pole','marker','building')


class Terrain:
    def __init__(self,data):
        self.data = data
        grid = data['sides'][:,:,2:]
        a,b,c,d = grid[:,:-1,:-1],grid[:,1:,:-1],grid[:,1:,1:],grid[:,:-1,1:]
        self.triangles = np.concatenate([np.stack([a,b,c],axis=-2).reshape(-1,3,3),np.stack([a,c,d],axis=-2).reshape(-1,3,3)])
        self.tree = cKDTree(self.triangles[:,:,:2].mean(axis=1))
        self.road_tree = cKDTree(data['xy'])

    def height(self,xy):
        _,indices = self.tree.query(xy,k=min(24,len(self.triangles)))
        for triangle in self.triangles[np.atleast_1d(indices)]:
            matrix = (triangle[1:,:2]-triangle[0,:2]).T
            if abs(np.linalg.det(matrix)) < 1e-9:
                continue
            uv = np.linalg.solve(matrix,np.asarray(xy)-triangle[0,:2])
            if uv.min() >= -1e-6 and uv.sum() <= 1+1e-6:
                return float(triangle[0,2]+uv@(triangle[1:,2]-triangle[0,2]))
        return None

    def clearance(self,xy):
        data = self.data
        _,indices = self.road_tree.query(xy,k=min(12,len(data['s'])))
        indices = np.unique(np.clip(np.r_[indices,np.asarray(indices)-1],0,len(data['s'])-2))
        a,b = data['xy'][indices],data['xy'][indices+1]
        delta = b-a
        fraction = np.clip(np.sum((xy-a)*delta,axis=1)/np.sum(delta*delta,axis=1),0,1)
        distances = np.linalg.norm(xy-a-fraction[:,None]*delta,axis=1)
        return float(np.min(distances-np.maximum(data['width'][indices],data['width'][indices+1])/2))

    def sample(self,chainage,side,offset):
        data = self.data
        i = min(len(data['s'])-2,max(0,int(np.searchsorted(data['s'],chainage)-1)))
        t = (chainage-data['s'][i])/(data['s'][i+1]-data['s'][i])
        offsets = (1-t)*data['offsets'][side,i]+t*data['offsets'][side,i+1]
        if offset < offsets[2] or offset > offsets[-1]:
            return None
        j = min(5,max(2,int(np.searchsorted(offsets,offset)-1)))
        f = (offset-offsets[j])/(offsets[j+1]-offsets[j])
        grid = data['sides'][side]
        a,b,c,d = grid[i,j],grid[i+1,j],grid[i+1,j+1],grid[i,j+1]
        if f <= t:
            triangle,weights = np.array([a,b,c]),np.array([1-t,t-f,f])
        else:
            triangle,weights = np.array([a,c,d]),np.array([1-f,t,f-t])
        normal = np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0])
        slope = np.linalg.norm(normal[:2])/max(abs(normal[2]),1e-9)
        return weights@triangle,float(slope),i


def scatter(data,seed=SEED,vegetation_count=1400):
    if len(data['s']) < 2 or data['sides'].shape[:2] != (2,len(data['s'])):
        raise ValueError('Need nonempty terrain ribbons')
    rng = np.random.default_rng(seed)
    terrain = Terrain(data)
    entries = []
    def place(kind,chainage,side,offset,scale=1.,variant=0):
        radius = (3.,2.5,1.25,1.2,.45,5.)[kind]*scale
        sampled = terrain.sample(chainage,side,offset)
        if sampled is None:
            return False
        point,slope,i = sampled
        if slope > (.18 if kind==5 else .55) or data['cut'][side,i] or data['cut'][side,i+1]:
            return False
        required = 8 if kind==5 else (4 if kind<4 else 2)
        clearance = terrain.clearance(point[:2])-radius
        if clearance < required:
            return False
        corners = point[:2]+np.array([[1,1],[1,-1],[-1,1],[-1,-1]])*radius
        heights = [terrain.height(corner) for corner in corners]
        if any(h is None for h in heights):
            return False
        entries.append([kind,variant,*point,float(rng.uniform(-np.pi,np.pi)),scale,radius,chainage,side,slope,min(heights),clearance])
        return True
    for _ in range(30000):
        if len(entries) >= vegetation_count:
            break
        chainage = float(rng.uniform(0,data['s'][-1]))
        if (chainage < 2000 or chainage > 23300) and rng.random() > .2:
            continue
        kind = int(rng.choice(3,p=[.3,.25,.45]))
        scale = float(rng.uniform(.75,1.25))
        side = int(rng.integers(2))
        i = int(np.searchsorted(data['s'],chainage))
        lower = data['width'][i]/2+4+(3,2.5,1.25)[kind]*scale
        upper = data['offsets'][side,i,-1]-(3,2.5,1.25)[kind]*scale
        if upper > lower:
            place(kind,chainage,side,float(rng.uniform(lower,upper)),scale,int(rng.integers(3)))
    for chainage in np.arange(25,data['s'][-1]-10,50):
        if chainage < 2000 or 18000 < chainage < 20500 or chainage > 23100:
            for offset in (10,14,20):
                if place(3,float(chainage),1,offset,1,int(rng.integers(2))):
                    break
    for chainage in np.arange(1000,data['s'][-1],1000):
        placed = False
        for shift in (0,-4,4,-8,8):
            for side in (1,0):
                for offset in (7,10,14,20):
                    if place(4,float(chainage+shift),side,offset):
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break
        if not placed:
            raise ValueError(f'No terrain site for kilometre marker {chainage}')
    for lower,upper,target in ((60,2000,28),(23200,float(data['s'][-1]-20),12)):
        upper = min(upper,float(data['s'][-1]-20))
        if upper <= lower:
            continue
        count = 0
        for _ in range(3000):
            if count == target:
                break
            chainage = float(rng.uniform(lower,upper))
            side = int(rng.integers(2))
            scale = float(rng.uniform(.8,1.25))
            i = int(np.searchsorted(data['s'],chainage))
            minimum = data['width'][i]/2+8+5*scale
            maximum = data['offsets'][side,i,-1]-5*scale
            if maximum > minimum and place(5,chainage,side,float(rng.uniform(minimum,maximum)),scale,int(rng.integers(3))):
                count += 1
    return np.asarray(entries,dtype=float).reshape(-1,13)


def coast_chain(cache,origin,data):
    ways = [w for w in cache['ways'] if w['tags'].get('natural')=='coastline']
    if not ways:
        raise ValueError('OSM coastline required for coastal decor')
    starts = {w['nodes'][0]:w for w in ways}
    ends = {w['nodes'][-1] for w in ways}
    ordered = [w for w in ways if w['nodes'][0] not in ends]+ways
    used,chains = set(),[]
    transform = Transformer.from_crs(4326,32631,always_xy=True)
    for way in ordered:
        if way['id'] in used:
            continue
        points = list(way['coords'])
        used.add(way['id'])
        end = way['nodes'][-1]
        while end in starts and starts[end]['id'] not in used:
            way = starts[end]
            points.extend(way['coords'][1:])
            used.add(way['id'])
            end = way['nodes'][-1]
        projected = np.column_stack(transform.transform(*np.asarray(points).T))-origin
        chains.append(projected)
    chain = min(chains,key=lambda p: np.linalg.norm(p-data['xy'][-1],axis=1).min())
    along = np.r_[0,np.cumsum(np.linalg.norm(np.diff(chain,axis=0),axis=1))]
    near_finish = int(np.argmin(np.linalg.norm(chain-data['xy'][-1],axis=1)))
    near_boulimat = int(np.argmin(np.linalg.norm(chain-data['xy'][np.searchsorted(data['s'],18500)],axis=1)))
    low,high = sorted((along[near_finish],along[near_boulimat]))
    selected = chain[(along>=low-1200)&(along<=high+1200)]
    a,b = sorted((int(np.argmin(selected[:,0])),int(np.argmax(selected[:,0]))))
    selected = selected[a:b+1]
    if len(selected) < 3:
        raise ValueError('Coastline does not span coastal section')
    return selected


def coastal_meshes(data,coast):
    # North is offshore here; close the actual coastal chain 1.5 km to the north.
    sea = np.vstack([coast,[coast[-1,0],coast[:,1].max()+1500],[coast[0,0],coast[:,1].max()+1500]])
    sea = np.column_stack([sea,np.zeros(len(sea))])
    minimum = float(min(data['z'].min(),data['sides'][...,2].min()))
    if minimum <= 0:
        raise ValueError('Sea at datum zero would cover existing terrain: clipping required')
    terrain = Terrain(data)
    chainages = np.arange(data['s'][-1]-550,data['s'][-1]-5,12)
    road_indices = np.searchsorted(data['s'],chainages)
    coast_index = cKDTree(coast).query(data['xy'][road_indices])[1]
    cumulative = np.r_[0,np.cumsum(np.linalg.norm(np.diff(coast,axis=0),axis=1))]
    distances = np.linspace(cumulative[coast_index[0]],cumulative[coast_index[-1]],len(chainages))
    shore = np.column_stack([np.interp(distances,cumulative,coast[:,j]) for j in range(2)])
    rows = []
    for i,point in zip(road_indices,shore):
        side = 0 if np.dot(point-data['xy'][i],data['normal'][i])>0 else 1
        inner = data['sides'][side,i,-1].copy()
        inner[2] += .015
        outer = np.r_[point,.12]
        rows.append([inner,(inner+outer)/2,outer])
    vertices = np.asarray(rows).reshape(-1,3)
    faces = []
    for i in range(len(rows)-1):
        for j in range(2):
            a,b = i*3+j,(i+1)*3+j
            for face in ((a,b,b+1),(a,b+1,a+1)):
                triangle = vertices[list(face)]
                # Reject any sand triangle whose XY footprint contains road-edge samples.
                matrix = (triangle[1:,:2]-triangle[0,:2]).T
                if abs(np.linalg.det(matrix)) < 1e-6:
                    continue
                road = np.concatenate([data['xy'],data['sides'][0,:,1,:2],data['sides'][1,:,1,:2]])
                uv = (road-triangle[0,:2])@np.linalg.inv(matrix).T
                if ((uv.min(axis=1)>=0)&(uv.sum(axis=1)<=1)).any():
                    continue
                if min(terrain.clearance(p) for p in triangle[:,:2])<2:
                    continue
                if np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0])[2] < 0:
                    face = tuple(reversed(face))
                faces.append(face)
    return sea,vertices,np.asarray(faces,dtype=int),minimum


def textures():
    rng = np.random.default_rng(SEED)
    for name,color in COLORS.items():
        noise = rng.normal(0,4,(512,512,1))
        if name=='bark':
            noise += np.sin(np.arange(512)[None,:,None]/3)*9
        if name=='water':
            noise += np.sin(np.arange(512)[:,None,None]/4)*2
        image = np.clip(np.asarray(color)[None,None,:]+noise,0,255).astype(np.uint8)
        Image.fromarray(image).save(ROOT/'textures'/f'{name}.png')


def build(blender):
    data = np.load(ROOT/'data/centerline.npz')
    cache = json.loads((ROOT/'data/area_cache.json').read_text())
    origin = json.loads((ROOT/'data/geo_origin.json').read_text())
    coast = coast_chain(cache,[origin['easting_m'],origin['northing_m']],data)
    placements = scatter(data)
    sea,beach,beach_faces,minimum = coastal_meshes(data,coast)
    textures()
    np.savez_compressed(ROOT/'data/decor_plan.npz',placements=placements,sea=sea,beach=beach,beach_faces=beach_faces,coast=coast)
    info = dict(seed=SEED,placements={kind:int(np.sum(placements[:,0]==i)) for i,kind in enumerate(KINDS)},minimum_terrain_above_sea_m=minimum,sea_elevation_m=0,offshore_extension_m=1500,beach_physical=False)
    (ROOT/'data/decor_info.json').write_text(json.dumps(info,indent=2)+'\n')
    plan = write_files(data)
    (ROOT/'data/acdata_info.json').write_text(json.dumps(plan,indent=2)+'\n')
    subprocess.run([blender,'-b',str(ROOT/'blend/bejaia_saket.blend'),'--python-exit-code','1','-P',str(ROOT/'scripts/blender_decor.py')],check=True,cwd=ROOT,env=os.environ.copy())
    write_files(data)
    print('DECOR_OK', (ROOT/'data/decor_info.json').read_text().strip())
