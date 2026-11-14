"""Conforming DEM TIN around the untouched road ribbons; all coordinates in metres."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import osmium
from scipy.spatial import Delaunay,cKDTree
import shapely
from shapely.geometry import LineString,Polygon,box
from shapely.ops import polygonize,unary_union

from geometry import DEM,FORWARD,ROOT


def cross2(a,b):
    return a[...,0]*b[...,1]-a[...,1]*b[...,0]


def footprint(data,outer=-1):
    polygon=Polygon(np.vstack([data['sides'][0,:,outer,:2],data['sides'][1,::-1,outer,:2]]))
    return shapely.make_valid(polygon)


def coastlines(root=ROOT):
    path=root/'data/coastline_cache.json'
    if not path.exists():
        class Coast(osmium.SimpleHandler):
            def __init__(self):super().__init__();self.lines=[]
            def way(self,w):
                if w.tags.get('natural')=='coastline':
                    self.lines.append([(n.lon,n.lat) for n in w.nodes])
        handler=Coast();handler.apply_file(str(root/'data/algeria-latest.osm.pbf'),locations=True,idx='flex_mem')
        path.write_text(json.dumps(handler.lines))
    return json.loads(path.read_text())


def shoreline(origin,bounds,dem,root=ROOT):
    region=box(*bounds)
    lines=[]
    for coords in coastlines(root):
        p=np.column_stack(FORWARD.transform(*np.asarray(coords).T))-origin
        line=LineString(p).intersection(region)
        if not line.is_empty:lines.append(line)
    if not lines:raise ValueError('Missing OSM coastline in landscape domain')
    coast=unary_union(lines)
    polygons=list(polygonize(unary_union([region.boundary,coast])))
    land=[]
    for polygon in polygons:
        point=polygon.representative_point()
        if dem.sample(np.array([[point.x,point.y]]))[0]>.5:land.append(polygon)
    land=unary_union(land)
    if land.is_empty:raise ValueError('Could not classify OSM mainland')
    return land,coast,region


def edges(data):
    rows=np.concatenate([data['sides'][0,:,-1],data['sides'][1,:,-1]])
    segments=np.concatenate([np.stack([data['sides'][s,:-1,-1],data['sides'][s,1:,-1]],axis=1) for s in (0,1)])
    for i in (0,-1):
        cap=np.vstack([data['sides'][0,i,::-1],data['sides'][1,i]])
        segments=np.concatenate([segments,np.stack([cap[:-1],cap[1:]],axis=1)])
    return rows,segments.astype('float32').astype(float)


def edge_height(points,segments):
    tree=shapely.STRtree(shapely.linestrings(segments[:,:,:2]))
    pair=tree.query_nearest(shapely.points(points),all_matches=False)
    ix=np.empty(len(points),dtype=int);ix[pair[0]]=pair[1]
    a=segments[ix,0];delta=segments[ix,1]-a
    t=np.clip(np.sum((points-a[:,:2])*delta[:,:2],axis=1)/np.maximum(np.sum(delta[:,:2]**2,axis=1),1e-12),0,1)
    q=a+t[:,None]*delta
    return np.linalg.norm(q[:,:2]-points,axis=1),q[:,2]


def height_field(points,data,dem,land,coast,segments):
    z=dem.sample(points)
    coast_segments=[]
    for line in shapely.get_parts(coast):
        if line.geom_type!='LineString':continue
        p=np.asarray(line.coords);coast_segments.append(np.stack([p[:-1],p[1:]],axis=1))
    coast_tree=shapely.STRtree(shapely.linestrings(np.concatenate(coast_segments)))
    _,coast_distance=coast_tree.query_nearest(shapely.points(points),return_distance=True,all_matches=False)
    shapely.prepare(land)
    onland=shapely.covers(land,shapely.points(points))
    z=np.where(onland,z*np.clip(coast_distance/10,0,1),-np.minimum(3,.2+coast_distance/6))
    road_distance=cKDTree(data['xy']).query(points)[0]
    noise=(np.sin(points[:,0]/17)*np.cos(points[:,1]/23)+.45*np.sin((points[:,0]+points[:,1])/9))
    z+=noise*np.clip((road_distance-100)/150,0,1)*np.clip(coast_distance/40,0,1)*onland
    d,edge_z=edge_height(points,segments)
    blend=np.clip(d/65,0,1);blend=blend*blend*(3-2*blend)
    z=(edge_z-.1)*(1-blend)+z*blend
    plan=np.load(ROOT/'data/decor_plan.npz')
    triangles=plan['beach'][plan['beach_faces']]
    if len(triangles):
        tree=shapely.STRtree(shapely.buffer(shapely.polygons(triangles[:,:,:2]),.002))
        rows,ids=tree.query(shapely.points(points),predicate='covered_by')
        tri=triangles[ids];ab=tri[:,1:,:2]-tri[:,0,None,:2]
        det=ab[:,0,0]*ab[:,1,1]-ab[:,0,1]*ab[:,1,0]
        q=points[rows]-tri[:,0,:2];safe=np.where(abs(det)>1e-9,det,1)
        u=(q[:,0]*ab[:,1,1]-q[:,1]*ab[:,1,0])/safe
        v=(ab[:,0,0]*q[:,1]-ab[:,0,1]*q[:,0])/safe
        beach_z=tri[:,0,2]+u*(tri[:,1,2]-tri[:,0,2])+v*(tri[:,2,2]-tri[:,0,2])
        target=np.full(len(points),np.inf)
        np.minimum.at(target,rows,beach_z-.1)
        inside=np.isfinite(target);z[inside]=target[inside]
        z[d<1.5]=np.minimum(z[d<1.5],edge_z[d<1.5]-.1)
    return z


def triangulate_domain(points,domain):
    if len(points)<3 or domain.is_empty:raise ValueError('Need points and a nonempty terrain domain')
    points=np.vstack([points,shapely.get_coordinates(domain.boundary)])
    points=np.unique(points,axis=0)
    triangles=points[Delaunay(points).simplices]
    polygons=shapely.polygons(triangles)
    shapely.prepare(domain)
    inside=shapely.covers(domain,polygons)
    result=[triangles[inside]]
    crossing=(~inside)&shapely.intersects(domain,polygons)
    clipped=shapely.intersection(polygons[crossing],domain)
    for polygon in clipped:
        parts=shapely.get_parts(polygon)
        for part in parts:
            if part.geom_type!='Polygon' or part.area<1e-6:continue
            faces=shapely.get_parts(shapely.constrained_delaunay_triangles(part))
            if len(faces):result.append(np.asarray([np.asarray(f.exterior.coords)[:3] for f in faces]))
    triangles=np.concatenate(result)
    area=cross2(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    triangles[area<0]=triangles[area<0,::-1]
    unique,inverse=np.unique(triangles.reshape(-1,2).astype('float32').astype(float),axis=0,return_inverse=True)
    faces=inverse.reshape(-1,3)
    area=cross2(unique[faces[:,1]]-unique[faces[:,0]],unique[faces[:,2]]-unique[faces[:,0]])
    return unique,faces[area>1e-5]


def generate(root=ROOT):
    data=np.load(root/'data/centerline.npz')
    origin_data=json.loads((root/'data/geo_origin.json').read_text())
    origin=np.array([origin_data['easting_m'],origin_data['northing_m']]);dem=DEM(origin)
    lower=np.floor((data['xy'].min(0)-15000)/250)*250
    upper=np.ceil((data['xy'].max(0)+15000)/250)*250
    land,coast,region=shoreline(origin,(*lower,*upper),dem,root)
    corridor=footprint(data)
    road=footprint(data,0)
    exclusion=corridor.buffer(-1).simplify(.05,preserve_topology=True).union(road.buffer(.02))
    domain=land.buffer(25).union(corridor.buffer(80)).intersection(region).difference(exclusion)
    shapely.prepare(domain)
    road_line=LineString(data['xy'][::4])
    tree=cKDTree(data['xy'])
    points=[];counts={}
    for spacing,near,far in ((11,0,400),(30,400,2500),(90,2500,8000),(250,8000,14000)):
        x=np.arange(lower[0],upper[0]+spacing,spacing);y=np.arange(lower[1],upper[1]+spacing,spacing)
        xx,yy=np.meshgrid(x,y);p=np.column_stack([xx.ravel(),yy.ravel()])
        distance=tree.query(p,workers=-1)[0]
        keep=(distance>=near)&(distance<far)
        p=p[keep];keep=shapely.covers(domain,shapely.points(p));p=p[keep]
        points.append(p);counts[str(spacing)]=len(p)
    outer,_=edges(data)
    points.append(outer[shapely.covers(domain,shapely.points(outer[:,:2])),:2])
    print('LANDSCAPE_POINTS '+json.dumps(counts),flush=True)
    # Dense inner boundary constraints keep transitions and switchbacks local.
    boundary=shapely.get_parts(exclusion.boundary)
    for line in boundary:
        p=shapely.get_coordinates(shapely.segmentize(line,4))
        points.append(p)
    for line in shapely.get_parts(coast):
        if line.geom_type!='LineString':continue
        p=shapely.get_coordinates(shapely.segmentize(line,15))
        tangent=np.gradient(p,axis=0);normal=np.column_stack([-tangent[:,1],tangent[:,0]])
        normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-9)
        for offset in (-15,0,10,30):
            q=p+normal*offset
            points.append(q[shapely.covers(domain,shapely.points(q))])
    points=np.concatenate(points)
    beach=np.load(root/'data/decor_plan.npz')['beach'][:,:2]
    points=np.vstack([points,beach[shapely.covers(domain,shapely.points(beach))]])
    xy,faces=triangulate_domain(points,domain)
    print(f'LANDSCAPE_TIN vertices={len(xy)} triangles={len(faces)}',flush=True)
    _,segments=edges(data)
    z=height_field(xy,data,dem,land,coast,segments)
    vertices=np.column_stack([xy,z]);triangles=vertices[faces]
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    slope=np.degrees(np.arctan2(np.linalg.norm(normals[:,:2],axis=1),normals[:,2]))
    physical_band=road_line.buffer(150);shapely.prepare(physical_band)
    physical=shapely.intersects(physical_band,shapely.polygons(xy[faces]))
    center=triangles.mean(1);distance=tree.query(center[:,:2])[0]
    size=np.where(physical,400,np.where(distance<2500,800,2000))
    tiles=np.floor(center[:,:2]/size[:,None]).astype(int)
    keys=np.column_stack([physical.astype(int),size.astype(int),tiles,(slope>35).astype(int)])
    sea=region.difference(land)
    sea_tri=[]
    for part in shapely.get_parts(sea):
        if part.geom_type=='Polygon':
            sea_tri.extend(np.asarray(p.exterior.coords)[:3] for p in shapely.get_parts(shapely.constrained_delaunay_triangles(part)))
    sea_tri=np.asarray(sea_tri)
    sea_xy,sea_indices=np.unique(sea_tri.reshape(-1,2).astype('float32').astype(float),axis=0,return_inverse=True)
    sea_faces=sea_indices.reshape(-1,3)
    sea_cross=cross2(sea_xy[sea_faces[:,1]]-sea_xy[sea_faces[:,0]],sea_xy[sea_faces[:,2]]-sea_xy[sea_faces[:,0]])
    sea_faces[sea_cross<0]=sea_faces[sea_cross<0,::-1]
    sea_faces=sea_faces[abs(sea_cross)>1e-4]
    if len(faces)>=600000:raise ValueError(f'Terrain budget exceeded: {len(faces)}')
    shapely.prepare(road);polygons=shapely.polygons(xy[faces])
    hit=shapely.intersects(road,polygons)
    overlap=shapely.area(shapely.intersection(polygons[hit],road)).sum()
    if overlap>.001:raise ValueError(f'Landscape overlaps road: {overlap} m2')
    d,edge_z=edge_height(xy,segments);join=d<1.5
    if np.any(z[join]>edge_z[join]-.09):raise ValueError('Landscape join above original ribbon')
    np.savez_compressed(root/'data/landscape.npz',vertices=vertices,faces=faces,keys=keys,
        sea_vertices=np.column_stack([sea_xy,np.zeros(len(sea_xy))]),sea_faces=sea_faces)
    info=dict(grid_points=counts,triangles_added=len(faces),vertices=len(vertices),physical_triangles=int(physical.sum()),
        visual_triangles=int((~physical).sum()),rock_triangles=int((slope>35).sum()),tiles=len(np.unique(keys,axis=0)),
        road_overlap_m2=float(overlap),join_vertices=int(join.sum()),join_clearance_m=[float((edge_z-z)[join].min()),float((edge_z-z)[join].max())],
        sea_triangles=len(sea_faces),sea_extent_m=np.ptp(sea_xy,axis=0).tolist(),backdrop_spacing_m=250,
        dem_source='Copernicus GLO-30, cached N36E004/N36E005; 11m near grid is interpolation, not 11m survey',
        noise_max_amplitude_m=1.45,noise_starts_road_distance_m=100,overlap_under_ribbon_m=1)
    (root/'data/landscape_info.json').write_text(json.dumps(info,indent=2)+'\n')
    print('LANDSCAPE_GRID_OK '+json.dumps(info),flush=True)
    return info


def build(blender):
    generate()
    subprocess.run([blender,'-b',str(ROOT/'blend/bejaia_saket.blend'),'--python-exit-code','1','-P',str(ROOT/'scripts/blender_landscape.py')],check=True,cwd=ROOT)
    from materials import export_report,package_output
    export_report();package_output()


def render(blender):
    subprocess.run([blender,'-b',str(ROOT/'blend/bejaia_saket.blend'),'--python-exit-code','1','-P',str(ROOT/'scripts/blender_material_preview.py'),'--','after'],
        check=True,cwd=ROOT,env=dict(os.environ,BS_COMPARISON_DIR=str(ROOT/'out/preview/v2_terrain'),BS_TERRAIN_PREVIEW='1'))
    from PIL import Image,ImageDraw,ImageOps
    names=('top','road_10','road_40','road_70','road_95','decor_town','decor_saket','elevated_boulimat','elevated_city')
    folder=ROOT/'out/preview/v2_terrain'
    canvas=Image.new('RGB',(1920,3*382),(25,25,25));draw=ImageDraw.Draw(canvas)
    for i,name in enumerate(names):
        image=Image.open(folder/'after'/(name+'.png')).convert('RGB')
        x,y=(i%3)*640,(i//3)*382
        canvas.paste(ImageOps.fit(image,(640,360)),(x,y+22));draw.text((x+8,y+5),name+' (Cycles CPU)',fill='white')
    canvas.save(folder/'contact_sheet.jpg',quality=93)
    ImageOps.fit(Image.open(folder/'after/road_70.png').convert('RGB'),(355,200),method=Image.Resampling.LANCZOS).save(ROOT/'out/bejaia_saket/ui/preview.png')
    from materials import package_output
    package_output()
