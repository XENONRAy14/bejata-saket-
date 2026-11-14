"""Clustered, terrain-snapped visual vegetation and the optional preview stage."""
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import shapely
from scipy.spatial import cKDTree

from geometry import ROOT
from check_kn5 import inspect_kn5
from foliage import SEED,SPECIES,prototype,generate_textures


class Terrain:
    def __init__(self,triangles):
        self.triangles=np.asarray(triangles,float)
        if self.triangles.ndim!=3 or self.triangles.shape[1:]!=(3,3) or not len(self.triangles):raise ValueError('Need terrain triangles')
        self.tree=shapely.STRtree(shapely.polygons(self.triangles[:,:,:2]))

    def sample(self,xy):
        xy=np.asarray(xy,float);height=np.full(len(xy),-np.inf);normal=np.zeros((len(xy),3))
        rows,ids=self.tree.query(shapely.points(xy),predicate='covered_by')
        t=self.triangles[ids];a=t[:,1]-t[:,0];b=t[:,2]-t[:,0];q=xy[rows]-t[:,0,:2]
        det=a[:,0]*b[:,1]-a[:,1]*b[:,0];safe=np.where(abs(det)>1e-9,det,1)
        u=(q[:,0]*b[:,1]-q[:,1]*b[:,0])/safe;v=(a[:,0]*q[:,1]-a[:,1]*q[:,0])/safe
        z=t[:,0,2]+u*a[:,2]+v*b[:,2];n=np.cross(a,b);n*=np.where(n[:,2:3]<0,-1,1);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
        for i in np.argsort(z):
            if abs(det[i])<1e-9:continue
            height[rows[i]]=z[i];normal[rows[i]]=n[i]
        return height,normal


def blender_triangles(node):
    p=node['positions'][node['indices']][:,:,[0,2,1]].astype(float);p[:,:,1]*=-1
    return p


def radius_and_cost():
    radii=np.zeros((7,3));cost=np.zeros((7,3),int)
    for kind in range(7):
        for variant in range(3):
            for lod in (0,1):
                groups=prototype(kind,variant,lod)
                cost[kind,variant]+=sum(len(m.faces) for m in groups.values())
                for mesh in groups.values():
                    if mesh.vertices:radii[kind,variant]=max(radii[kind,variant],np.linalg.norm(np.asarray(mesh.vertices)[:,:2],axis=1).max())
    return radii,cost


def generate(root=ROOT):
    root=Path(root)
    parsed=inspect_kn5(root/'out/bejaia_saket/bejaia_saket.kn5',geometry='all')
    meshes=[n for n in parsed['nodes'] if n['kind']==2]
    terrain=Terrain(np.concatenate([blender_triangles(n) for n in meshes if n['name'].startswith(('1GRASS_','LAND_'))]))
    road=np.concatenate([blender_triangles(n) for n in meshes if n['name'].startswith('1ROAD_')])
    road_tree=shapely.STRtree(shapely.polygons(road[:,:,:2]))
    sea=shapely.union_all(shapely.polygons(np.concatenate([blender_triangles(n) for n in meshes if n['name']=='DECOR_SEA'])[:,:,:2]))
    beach=shapely.union_all(shapely.polygons(np.concatenate([blender_triangles(n) for n in meshes if n['name']=='DECOR_BEACH'])[:,:,:2]))
    exclusion=shapely.union_all([sea,beach]).buffer(7);shapely.prepare(exclusion)
    data=np.load(root/'data/centerline.npz');plan=np.load(root/'data/decor_plan.npz');houses=plan['placements'][plan['placements'][:,0]==5,2:4]
    road_index=cKDTree(data['xy']);buildings=cKDTree(houses)
    rng=np.random.default_rng(SEED);count=1600
    indices=rng.integers(0,len(data['xy']),count)
    side=np.where(rng.random(count)<.74,1,-1)
    centers=data['xy'][indices]+data['normal'][indices]*side[:,None]*rng.uniform(15,260,count)[:,None]
    centers=np.repeat(centers,14,axis=0);spread=np.repeat(rng.uniform(8,30,count),14)
    xy=centers+rng.normal(size=centers.shape)*spread[:,None]
    distance,nearest=road_index.query(xy);keep=(distance<300)&(rng.random(len(xy))<np.clip((300-distance)/90,0,1))
    xy=xy[keep];nearest=nearest[keep];distance=distance[keep]
    heights,normals=terrain.sample(xy);slope=np.degrees(np.arccos(np.clip(normals[:,2],0,1)))
    keep=np.isfinite(heights)&(heights>.4)&(slope<=35)&~shapely.covers(exclusion,shapely.points(xy))
    xy=xy[keep];nearest=nearest[keep];distance=distance[keep];heights=heights[keep];normals=normals[keep];slope=slope[keep]
    _,edge_distance=road_tree.query_nearest(shapely.points(xy),return_distance=True,all_matches=False)
    coast=shapely.STRtree(shapely.get_parts(sea.boundary))
    _,coast_distance=coast.query_nearest(shapely.points(xy),return_distance=True,all_matches=False)
    building_distance=buildings.query(xy)[0]
    radii,cost=radius_and_cost();plants=[];grid={};total_cost=0
    legacy=lambda n:n['name'].startswith('DECOR_') and n['name'].endswith(('_pine_foliage','_olive_foliage','_maquis','_bark'))
    baseline=sum(n['triangles'] for n in meshes if not n['name'].startswith('DECOR_VEG_') and not legacy(n))
    # Retained pole trunks and building joinery are rebuilt separately from old bark batches.
    reserve=6000;budget=1590000-baseline-reserve
    for i,point in enumerate(xy):
        s=data['s'][nearest[i]];near_building=building_distance[i]<50
        mountain=np.dot(point-data['xy'][nearest[i]],data['normal'][nearest[i]])>0
        r=rng.random()
        if r<.12:kind=6
        elif coast_distance[i]<65 and r<.42:kind=5
        elif near_building and r<.47:kind=3
        elif (s<2400 or s>22600 or not mountain) and slope[i]<21 and r<.69:kind=2
        elif r<.42:kind=4
        else:kind=0 if rng.random()<.7 else 1
        variant=int(rng.integers(3));scale=float(rng.uniform(.76,1.2));radius=radii[kind,variant]*scale
        if edge_distance[i]<radius+4 or building_distance[i]<radius+5:continue
        cell=tuple(np.floor(point/5).astype(int));valid=True
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for previous in grid.get((cell[0]+dx,cell[1]+dy),[]):
                    separation=4.5 if kind<4 and plants[previous][0]<4 else 2.
                    if np.linalg.norm(point-np.asarray(plants[previous][2:4]))<separation:valid=False
        if not valid or total_cost+cost[kind,variant]>budget:continue
        tint=int(rng.choice(3,p=(.25,.18,.57) if kind==2 else (.56,.32,.12)))
        entry=[kind,variant,*point,float(heights[i]),float(rng.uniform(0,2*np.pi)),scale,tint,int(s//400),*normals[i],float(edge_distance[i]),float(slope[i])]
        plants.append(entry);grid.setdefault(cell,[]).append(len(plants)-1);total_cost+=cost[kind,variant]
        if len(plants)>=5000:break
    if not plants:raise ValueError('No valid vegetation placements')
    plants=np.asarray(plants)
    np.savez_compressed(root/'data/vegetation.npz',plants=plants)
    info=dict(seed=SEED,species={name:int(np.sum(plants[:,0]==i)) for i,name in enumerate(SPECIES)},instances=len(plants),variants_per_species=3,
        maximum_root_road_distance_m=float(road_index.query(plants[:,2:4])[0].max()),minimum_canopy_road_clearance_m=float(min(p[12]-radii[int(p[0]),int(p[1])]*p[6] for p in plants)),
        maximum_slope_degrees=float(plants[:,13].max()),lod0_range_m=[0,150],lod1_range_m=[150,600],far_clumps='skipped beyond 300 m road distance',
        double_sided='explicit reversed faces, duplicated vertices; canopy-outward custom normals',before_triangles=json.loads((root/'data/landscape_info.json').read_text())['after_triangles'],estimated_plant_triangles=int(total_cost),wind='deferred: no verified merged-card wind weights',root_snap='highest actual exported terrain triangle; trunk base embedded')
    (root/'data/vegetation_info.json').write_text(json.dumps(info,indent=2)+'\n')
    print('VEGETATION_PLAN_OK '+json.dumps(info),flush=True)
    return info


def build(blender,kn5_fallback=False):
    generate_textures();generate()
    from treefx import generate as external
    if not kn5_fallback:external()
    else:
        (ROOT/'data/treefx_info.json').write_text(json.dumps(dict(mode='KN5 fallback'))+'\n')
        for path in (ROOT/'out/bejaia_saket/extension/trees').glob('*'):
            if path.is_file():path.unlink()
    subprocess.run([blender,'-b',str(ROOT/'blend/bejaia_saket.blend'),'--python-exit-code','1','-P',str(ROOT/'scripts/blender_vegetation.py')],check=True,cwd=ROOT,env=dict(os.environ,BS_KN5_VEGETATION='1' if kn5_fallback else '0'))
    from materials import export_report,package_output
    export_report();package_output()


def render(blender):
    folder=ROOT/'out/preview/v2_veg'
    preview=ROOT/'data/research_cache/vegetation_preview.blend'
    subprocess.run([blender,'-b',str(preview if preview.exists() else ROOT/'blend/bejaia_saket.blend'),'--python-exit-code','1','-P',str(ROOT/'scripts/blender_material_preview.py'),'--','after'],
        check=True,cwd=ROOT,env=dict(os.environ,BS_COMPARISON_DIR=str(folder),BS_VEGETATION_PREVIEW='1'))
    from PIL import Image,ImageDraw,ImageOps
    names=('road_10','road_40','road_70','road_95','decor_town','decor_saket','trees_closeup')
    canvas=Image.new('RGB',(1920,3*382),(25,25,25));draw=ImageDraw.Draw(canvas)
    for i,name in enumerate(names):
        x,y=(i%3)*640,(i//3)*382
        canvas.paste(ImageOps.fit(Image.open(folder/'after'/(name+'.png')).convert('RGB'),(640,360)),(x,y+22));draw.text((x+8,y+5),name+' (Cycles CPU)',fill='white')
    canvas.save(folder/'contact_sheet.jpg',quality=93)
