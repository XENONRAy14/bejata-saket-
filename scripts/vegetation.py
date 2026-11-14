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


def radius_and_cost(quality=False):
    radii=np.zeros((7,3));cost=np.zeros((7,3),int)
    for kind in range(7):
        for variant in range(3):
            for lod in (0,1):
                groups=prototype(kind,variant,lod,quality=quality)
                cost[kind,variant]+=sum(len(m.faces) for m in groups.values())
                for mesh in groups.values():
                    if mesh.vertices:radii[kind,variant]=max(radii[kind,variant],np.linalg.norm(np.asarray(mesh.vertices)[:,:2],axis=1).max())
    return radii,cost


def footprint(points,center,yaw,scale):
    points=np.asarray(points)
    if len(points)<3 or scale<=0:raise ValueError('Invalid canopy footprint')
    rotation=np.array([[np.cos(yaw),-np.sin(yaw)],[np.sin(yaw),np.cos(yaw)]])
    return shapely.Polygon(points*scale@rotation.T+center)


def corridor_candidates(data):
    if len(data['s'])<2:raise ValueError('Need centerline samples')
    rng=np.random.default_rng(SEED);points=[];kinds=[];angles=[];scales=[]
    for spacing,offset,layer in ((7,6.5,4),(8,12.5,0),(50,25,1),(7.4,6.5,5),(8,12.5,6)):
        chainage=np.arange(20+layer*1.7,data['s'][-1]-20,spacing)
        ids=np.searchsorted(data['s'],chainage);higher=np.argmax(data['sides'][:,ids,-1,2],axis=0)
        if layer in (5,6):higher=1-higher
        outward=data['sides'][higher,ids,2,:2]-data['xy'][ids];outward/=np.linalg.norm(outward,axis=1)[:,None]
        for j,i in enumerate(ids):
            s=data['s'][i];wave=np.sin(s/63)+.45*np.sin(s/19)
            if layer in (5,6) and np.sin(s/117)>.8:continue
            distance=offset+(wave*.3 if layer in (4,5) else wave*2)
            kind=4 if layer in (4,5) else (2 if s<2600 or s>22500 else (0 if rng.random()<.75 else 1))
            if layer==1 and (s<2600 or s>22500) and rng.random()<.17:kind=3
            points.append(data['xy'][i]+outward[j]*(data['width'][i]/2+distance)+data['tangent'][i]*(chainage[j]-s+rng.uniform(-.3,.3)))
            kinds.append(kind);angles.append(float(np.arctan2(data['tangent'][i,1],data['tangent'][i,0])+rng.uniform(-.12,.12)) if kind==4 else float(rng.uniform(0,2*np.pi)))
            scales.append(float(rng.uniform(1,1.1)) if layer==4 else float(rng.uniform(.83,1.08)) if layer!=5 else float(rng.uniform(.88,1.02)))
    order=rng.permutation(len(points))
    return np.asarray(points,dtype=float).reshape(-1,2)[order],np.asarray(kinds,dtype=int)[order],np.asarray(angles)[order],np.asarray(scales)[order]


def generate(root=ROOT,quality=True):
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
    rng=np.random.default_rng(SEED)
    if quality:
        xy,preferred,preferred_angle,preferred_scale=corridor_candidates(data)
    else:
        count=1600;indices=rng.integers(0,len(data['xy']),count);side=np.where(rng.random(count)<.74,1,-1)
        centers=data['xy'][indices]+data['normal'][indices]*side[:,None]*rng.uniform(12,260,count)[:,None]
        centers=np.repeat(centers,14,axis=0);spread=np.repeat(rng.uniform(5,30,count),14)
        xy=centers+rng.normal(size=centers.shape)*spread[:,None]
    distance,nearest=road_index.query(xy);keep=(distance<(83 if quality else 300))&(rng.random(len(xy))<np.clip(((90 if quality else 300)-distance)/(20 if quality else 90),0,1))
    if quality:preferred=preferred[keep];preferred_angle=preferred_angle[keep];preferred_scale=preferred_scale[keep]
    xy=xy[keep];nearest=nearest[keep];distance=distance[keep]
    heights,normals=terrain.sample(xy);slope=np.degrees(np.arccos(np.clip(normals[:,2],0,1)))
    keep=np.isfinite(heights)&(heights>.4)&(slope<=35)&~shapely.covers(exclusion,shapely.points(xy))
    if quality:preferred=preferred[keep];preferred_angle=preferred_angle[keep];preferred_scale=preferred_scale[keep]
    xy=xy[keep];nearest=nearest[keep];distance=distance[keep];heights=heights[keep];normals=normals[keep];slope=slope[keep]
    _,edge_distance=road_tree.query_nearest(shapely.points(xy),return_distance=True,all_matches=False)
    coast=shapely.STRtree(shapely.get_parts(sea.boundary))
    _,coast_distance=coast.query_nearest(shapely.points(xy),return_distance=True,all_matches=False)
    building_distance=buildings.query(xy)[0]
    radii,cost=radius_and_cost(quality=quality);plants=[];grid={};total_cost=0
    if quality:cost[6]=0
    legacy=lambda n:n['name'].startswith('DECOR_') and n['name'].endswith(('_pine_foliage','_olive_foliage','_maquis','_bark'))
    baseline=sum(n['triangles'] for n in meshes if not n['name'].startswith('DECOR_VEG_') and not legacy(n))
    # Retained pole trunks and building joinery are rebuilt separately from old bark batches.
    reserve=130000;budget=np.inf if quality else 1590000-baseline-reserve;clearances=[]
    outlines={}
    if quality:
        for variant in range(3):
            vertices=np.concatenate([mesh.vertices for lod in (0,1) for mesh in prototype(4,variant,lod,quality=True).values() if mesh.vertices])
            outlines[variant]=shapely.get_coordinates(shapely.convex_hull(shapely.multipoints(vertices[:,:2])))
    for i,point in enumerate(xy):
        s=data['s'][nearest[i]];near_building=building_distance[i]<50
        mountain=np.dot(point-data['xy'][nearest[i]],data['normal'][nearest[i]])>0
        r=rng.random()
        if quality and mountain and edge_distance[i]<18 and r<.8:kind=4
        elif r<.12:kind=6
        elif coast_distance[i]<65 and r<.42:kind=5
        elif near_building and r<.47:kind=3
        elif (s<2400 or s>22600 or not mountain) and slope[i]<21 and r<.69:kind=2
        elif r<(.66 if quality else .42):kind=4
        else:kind=0 if rng.random()<.7 else 1
        variant=int(rng.integers(3));scale=float(rng.uniform(.82,1.18))
        if quality:kind=int(preferred[i]);scale=float(preferred_scale[i])
        if quality and kind<3 and edge_distance[i]<22 and rng.random()<.18:variant=2;scale=1.38
        radius=radii[kind,variant]*scale
        if quality and edge_distance[i]>80:continue
        clearance=edge_distance[i]-radius
        if quality and kind==4:
            shape=footprint(outlines[variant],point,preferred_angle[i],scale)
            clearance=float(road_tree.query_nearest(shape,return_distance=True,all_matches=False)[1][0])
        if clearance<4 or building_distance[i]<radius+5:continue
        cell=tuple(np.floor(point/5).astype(int));valid=True
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for previous in grid.get((cell[0]+dx,cell[1]+dy),[]):
                    separation=4.5 if kind<4 and plants[previous][0]<4 else 1.6 if quality else 2.
                    if np.linalg.norm(point-np.asarray(plants[previous][2:4]))<separation:valid=False
        if not valid or total_cost+cost[kind,variant]>budget:continue
        tint=int(rng.choice(3,p=(.25,.18,.57) if kind==2 else (.56,.32,.12)))
        entry=[kind,variant,*point,float(heights[i]),float(preferred_angle[i]) if quality else float(rng.uniform(0,2*np.pi)),scale,tint,int(s//400),*normals[i],float(edge_distance[i]),float(slope[i])]
        plants.append(entry);clearances.append(clearance);grid.setdefault(cell,[]).append(len(plants)-1);total_cost+=cost[kind,variant]
        if len(plants)>=(8000 if quality else 5000):break
    if not plants:raise ValueError('No valid vegetation placements')
    plants=np.asarray(plants)
    np.savez_compressed(root/'data/vegetation.npz',plants=plants)
    info=dict(seed=SEED,species={name:int(np.sum(plants[:,0]==i)) for i,name in enumerate(SPECIES)},instances=len(plants),variants_per_species=3,
        maximum_root_road_distance_m=float(road_index.query(plants[:,2:4])[0].max()),minimum_canopy_road_clearance_m=float(min(clearances)),
        maximum_slope_degrees=float(plants[:,13].max()),lod0_range_m=[0,150],lod1_range_m=[150,600],far_clumps='none beyond 80m road edge' if quality else 'skipped beyond 300m',
        double_sided='explicit reversed faces, duplicated vertices; canopy-outward custom normals',before_triangles=json.loads((root/'data/landscape_info.json').read_text())['after_triangles'],estimated_plant_triangles=int(total_cost),wind='deferred: no verified merged-card wind weights',root_snap='highest actual exported terrain triangle; trunk base embedded')
    (root/'data/vegetation_info.json').write_text(json.dumps(info,indent=2)+'\n')
    print('VEGETATION_PLAN_OK '+json.dumps(info),flush=True)
    return info


def build(blender,kn5_fallback=False):
    generate_textures();generate(quality=not kn5_fallback)
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
