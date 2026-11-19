"""Pure station-based scenery planning; no Blender or generated-file dependencies."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point

from pilot_common import frame, ground

CONFIG = Path(__file__).resolve().parents[1]/'data/scenery_zones.json'


def load_zones(path=CONFIG):
    config=json.loads(Path(path).read_text())
    for profile in ('pilot','main'):
        for kind in ('vista_openings','exclusions'):
            for zone in config[profile][kind]:
                if not np.isfinite([zone['start_m'],zone['end_m']]).all() or zone['start_m']>=zone['end_m']:
                    raise ValueError('Invalid scenery zone interval')
                if zone.get('side','both') not in ('both','sea','mountain',0,1):raise ValueError('Invalid scenery zone side')
    return config


def sector_seed(start_m, seed=24024, layer='trees'):
    payload=f'{seed}:{round(float(start_m)*1000)}:{layer}'.encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8],'little')


def interval(data,s0,s1):
    stations=np.asarray(data['s3'])
    if len(stations)<2 or not np.isfinite(stations).all() or np.any(np.diff(stations)<=0):
        raise ValueError('Need finite increasing 3D stations')
    if not np.isfinite([s0,s1]).all() or s0<stations[0] or s1>stations[-1] or s0>=s1:
        raise ValueError('Sector must be a nonempty interval inside the route')


def sea_sides(data,smoothing_m=30):
    stations=np.asarray(data['s3']);interval(data,float(stations[0]),float(stations[-1]))
    if not np.isfinite(smoothing_m) or smoothing_m<=0:raise ValueError('Side smoothing must be positive')
    # Uniform station sampling keeps the filter independent of inserted cross-sections.
    sample=np.linspace(stations[0],stations[-1],max(2,int(np.ceil(np.ptp(stations)/2))+1))
    heights=np.asarray(data['sides'])[:,:,-1,2]
    difference=np.interp(sample,stations,heights[0]-heights[1])
    if not np.isfinite(difference).all():raise ValueError('Nonfinite terrain side elevations')
    smooth=gaussian_filter1d(difference,smoothing_m/(sample[1]-sample[0]),mode='nearest')
    return lambda station: int(np.interp(station,sample,smooth)>0)


def zone_contains(station,side,sea_side,zones,kind,layer,radius=0):
    for zone in zones.get(kind,[]):
        if layer not in zone.get('layers',[layer]):continue
        target=zone.get('side','both')
        if target=='sea':target=sea_side
        elif target=='mountain':target=1-sea_side
        if target not in ('both',side):continue
        if station+radius>zone['start_m'] and station-radius<zone['end_m']:return True
    return False


def vista_open(station,length,side,sea_side,*,zones=None,layer='edge'):
    zones=load_zones()['pilot'] if zones is None else zones
    return zone_contains(station,side,sea_side,zones,'vista_openings',layer)


def edge_layout(data,sea_side=None,*,s0=None,s1=None,zones=None,seed=None):
    pilot=s0 is None and s1 is None and sea_side is not None
    s0=float(data['s3'][0]) if s0 is None else float(s0)
    s1=float(data['s3'][-1]) if s1 is None else float(s1)
    interval(data,s0,s1)
    zones=load_zones()['pilot' if pilot else 'main'] if zones is None else zones
    rng=np.random.default_rng(24025 if pilot else sector_seed(s0,zones.get('seed',24024),'edges') if seed is None else seed)
    sea=(lambda station:sea_side) if sea_side is not None else sea_sides(data,zones.get('side_smoothing_m',30))
    result=[]
    for side in (0,1):
        for tier,spacing in enumerate(zones.get('edge_spacings_m',(2.8,4.2))):
            for station in np.arange(s0+3,s1-2,spacing):
                station=float(np.clip(station+rng.uniform(-.3,.3),s0+2,s1-2))
                if vista_open(station,s1-s0,side,sea(station),zones=zones):continue
                width=float(rng.uniform(*zones.get('edge_widths_m',((3.5,4.5),(4.8,6.0)))[tier]))
                height=float(rng.uniform(*zones.get('edge_heights_m',((1.4,1.9),(2.5,3.3)))[tier]))
                half_road=float(np.interp(station,data['s3'],data['width']))/2
                offset=half_road+((2.5 if pilot else zones.get('road_clearance_m',4)+.1),6.3)[tier]+width/2
                _,tangent,_=frame(data,station)
                result.append(dict(station=station,side=side,tier=tier,offset=offset,
                    position=ground(data,station,side,offset).tolist(),width=width,height=height,
                    angle=math.atan2(tangent[1],tangent[0])+float(rng.uniform(-.17,.17)),variant=int(rng.integers(4))))
    return [plant for plant in result if not zone_contains(plant['station'],plant['side'],sea(plant['station']),
            zones,'exclusions','edge',plant['width']/2)]


def edge_batches(data,layout,*,distant=False,chunk_m=40):
    if not np.isfinite(chunk_m) or chunk_m<=0:raise ValueError('Chunk length must be positive')
    groups={}
    for plant in layout:
        key=(int(plant['station']//chunk_m),plant['side'])
        vertices,faces,uvs,normals=groups.setdefault(key,([],[],[],[]))
        _,tangent,left=frame(data,plant['station']);outward=left*(1 if plant['side']==0 else -1)
        col,row=plant['variant']%2,plant['variant']//2
        tile_uv=[((col+u)/2,1-(row+v)/2) for u,v in ((.002,.998),(.998,.998),(.998,.002),(.002,.002))]
        for plane in range(1 if distant else 2):
            angle=plant['angle']+plane*math.pi/2;right=np.array([math.cos(angle),math.sin(angle),0.])
            endpoints=[]
            for sign in (-1,1):
                delta=right*plant['width']/2*sign
                station=float(np.clip(plant['station']+delta@tangent,data['s3'][0],data['s3'][-1]))
                point=ground(data,station,plant['side'],float(plant['offset']+delta@outward));point[2]-=.3
                endpoints.append(point)
            points=[endpoints[0],endpoints[1],endpoints[1]+[0,0,plant['height']],endpoints[0]+[0,0,plant['height']]]
            horizontal=np.cross(right,[0,0,1])
            for sign in (1,-1):
                offset=len(vertices);vertices.extend(points)
                faces.append(tuple(offset+i for i in ((0,1,2,3) if sign==1 else (3,2,1,0))))
                uvs.extend(tile_uv);normals.extend([horizontal*sign*.6+[0,0,.8]]*4)
    return groups


def pilot_tree_layout(data,models,sea_side,*,zones=None):
    zones=load_zones()['pilot'] if zones is None else zones
    rng=np.random.default_rng(24024);plants=[]
    kinds=[name for name in models if name.startswith('PH_pine_0')]
    for side in (0,1):
        for row,spacing in ((0,9.5),(1,16),(2,9.5)):
            for station in np.arange(8,295,spacing):
                station=float(np.clip(station+rng.uniform(-1.3,1.3),4,296))
                if vista_open(station,300,side,sea_side,zones=zones,layer='adult'):continue
                if row==2 and side==sea_side:continue
                width=float(np.interp(station,data['s3'],data['width']))
                offset=width/2+(5.3 if row==0 else 13 if row==1 else 27)+float(rng.uniform(0,2.5))
                point=ground(data,station,side,offset);point[2]-=.12
                species=kinds[int(rng.integers(len(kinds)))];scale=float(rng.uniform(.68,.96))
                broad=float(rng.uniform(1.35,1.6) if row==0 else rng.uniform(1.08,1.25))
                if row==0 and zones['hero_width_interval_m'][0]<station<zones['hero_width_interval_m'][1]:broad=1.5
                plants.append(dict(model=species,position=point.tolist(),angle=float(rng.uniform(0,2*np.pi)),scale=scale,width=broad,station=station,side=side,offset=offset))
        for station in np.arange(8,295,10.5):
            if vista_open(station,300,side,sea_side,zones=zones,layer='sapling'):continue
            width=float(np.interp(station,data['s3'],data['width']))
            offset=width/2+float(rng.uniform(3,6.5))
            point=ground(data,float(station),side,offset);point[2]-=.08
            plants.append(dict(model='PH_pine_sapling_small_a',position=point.tolist(),angle=float(rng.uniform(0,2*np.pi)),scale=float(rng.uniform(1.1,1.9)),width=1.2,station=float(station),side=side,offset=offset))
    middle=[name for name in models if name.startswith('PH_pine_mid_')]
    mountain=1-sea_side
    groups=((28,mountain),(50,mountain),(74,mountain),(89,sea_side),(103,mountain),(117,sea_side),(133,mountain),(149,sea_side),(163,mountain),(178,sea_side),(190,mountain),(257,mountain),(272,sea_side),(286,mountain))
    for station,side in groups:
        for delta in (-2.4,2.4):
            s=float(station+delta)
            if vista_open(s,300,side,sea_side,zones=zones,layer='midstory'):continue
            species=middle[int(rng.integers(len(middle)))]
            scale=float(rng.uniform(6,8))/models[species]['height']
            half=float(np.interp(s,data['s3'],data['width']))/2
            offset=half+float(rng.uniform(5.5,8.5))
            point=ground(data,s,side,offset);point[2]-=.12
            plants.append(dict(model=species,position=point.tolist(),angle=float(rng.uniform(0,2*np.pi)),scale=scale,width=1.35,station=s,side=side,offset=offset))
    backgrounds=[name for name in models if name.startswith('PH_pine_bg_')]
    for side in (0,1):
        for station in np.arange(5,297,7):
            if vista_open(station,300,side,sea_side,zones=zones,layer='background'):continue
            species=backgrounds[int(rng.integers(len(backgrounds)))];scale=float(rng.uniform(.72,1.0))
            half=float(np.interp(station,data['s3'],data['width']))/2
            offset=half+float(rng.uniform(34,38))
            point=ground(data,float(station),side,offset);point[2]-=.15
            plants.append(dict(model=species,position=point.tolist(),angle=float(rng.uniform(0,2*np.pi)),scale=scale,width=1.15,station=float(station),side=side,offset=offset))
    shrubs=[name for name in models if name.startswith('PH_shrub_')]
    for side in (0,1):
        for station in np.arange(6,296,11):
            if vista_open(station,300,side,sea_side,zones=zones,layer='shrub'):continue
            species=shrubs[int(rng.integers(len(shrubs)))];scale=float(rng.uniform(1.15,1.55));broad=float(rng.uniform(1.05,1.3))
            half=float(np.interp(station,data['s3'],data['width']))/2
            radius=models[species]['width']/2*math.sqrt(2)*scale*broad
            offset=half+2.5+radius
            point=ground(data,float(station),side,offset);point[2]-=.05
            plants.append(dict(model=species,position=point.tolist(),angle=float(rng.uniform(0,2*np.pi)),scale=scale,width=broad,station=float(station),side=side,offset=offset))
    def excluded(plant):
        layer='sapling' if 'sapling' in plant['model'] else models[plant['model']]['kind']
        if layer=='pine':layer='adult'
        return zone_contains(plant['station'],plant['side'],sea_side,zones,'exclusions',layer,tree_radius(plant,models))
    return [plant for plant in plants if not excluded(plant)]


class RoadClearance:
    def __init__(self,data):
        self.xy=np.asarray(data['xy']);self.width=np.asarray(data['width'])
        if not np.isfinite(self.xy).all() or not np.isfinite(self.width).all() or np.any(self.width<=0):
            raise ValueError('Invalid road geometry')
        self.index=cKDTree(self.xy)
        self.road=LineString(self.xy).buffer(float(self.width.max())/2)

    def clearance(self,point,radius):
        return float(self.road.distance(Point(point[:2]))-radius)

    def allows(self,point,radius,minimum):
        neighbours=self.index.query_ball_point(point[:2],radius+minimum+self.width.max()/2)
        if neighbours:
            distance=np.linalg.norm(self.xy[neighbours]-np.asarray(point[:2]),axis=1)-self.width[neighbours]/2-radius
            if np.any(distance<minimum):return False
        return self.clearance(point,radius)>=minimum


def tree_radius(plant,models):
    return models[plant['model']]['width']/2*math.sqrt(2)*plant['scale']*plant['width']


def main_tree_layout(data,models,s0,s1,zones):
    interval(data,s0,s1)
    kinds={kind:[name for name,spec in models.items() if spec['kind']==kind and 'sapling' not in name]
           for kind in ('pine','midstory','background','shrub')}
    if any(not names for names in kinds.values()):raise ValueError('Need pine, midstory, background and shrub models')
    rng=np.random.default_rng(sector_seed(s0,zones.get('seed',24024)))
    sea=sea_sides(data,zones.get('side_smoothing_m',30));plants=[]
    layers=zones.get('tree_layers',[
        dict(kind='pine',spacing=21,offset=[12,15]),dict(kind='midstory',spacing=35,offset=[18,24]),
        dict(kind='background',spacing=16,offset=[34,38]),dict(kind='shrub',spacing=24,offset=[6,9])])
    for side in (0,1):
        for layer in layers:
            kind=layer['kind'];spacing=layer['spacing'];offset_range=layer['offset']
            for station in np.arange(s0+8,s1-5,spacing):
                station=float(station+rng.uniform(-1.3,1.3))
                if vista_open(station,s1-s0,side,sea(station),zones=zones,layer=kind):continue
                species=kinds[kind][int(rng.integers(len(kinds[kind])))];scale=float(rng.uniform(*layer.get('scale',[.68,.96])))
                broad=float(rng.uniform(*layer.get('width',[1.08,1.35])))
                half=float(np.interp(station,data['s3'],data['width']))/2
                offset=half+float(rng.uniform(*offset_range))
                point=ground(data,station,side,offset);point[2]-=.12
                if layer.get('bury_fraction'):point[2]-=float(models[species]['height'])*scale*layer['bury_fraction']
                plants.append(dict(model=species,position=point.tolist(),angle=float(rng.uniform(0,2*np.pi)),
                    scale=scale,width=broad,station=station,side=side,offset=offset))
    return plants


def plan_sector(data,models,s0,s1,*,zones=None):
    s0,s1=float(s0),float(s1);interval(data,s0,s1)
    zones=load_zones()['main'] if zones is None else zones
    clearance=float(zones.get('road_clearance_m',4))
    density=float(zones.get('max_tree_instances_per_100m',51));total_limit=int(zones.get('max_tree_instances_total',8000))
    if not np.isfinite([clearance,density]).all() or clearance<0 or not 0<density<=51 or not 0<total_limit<=8000:
        raise ValueError('Invalid clearance or tree budget')
    length=float(data['s3'][-1]-data['s3'][0]);density=min(density,total_limit*100/length)
    limit=int(math.floor((s1-s0)*density/100))
    road=RoadClearance(data);sea=sea_sides(data,zones.get('side_smoothing_m',30))
    def allowed(plant,radius,layer):
        return (not zone_contains(plant['station'],plant['side'],sea(plant['station']),zones,'exclusions',layer,radius)
                and road.allows(plant['position'],radius,clearance))
    candidates=main_tree_layout(data,models,s0,s1,zones)
    trees=[p for p in candidates if allowed(p,tree_radius(p,models),models[p['model']]['kind'])]
    if len(trees)>limit:
        rng=np.random.default_rng(sector_seed(s0,zones.get('seed',24024),'budget'))
        trees=[trees[i] for i in sorted(rng.choice(len(trees),limit,replace=False))]
    edges=[p for p in edge_layout(data,s0=s0,s1=s1,zones=zones) if allowed(p,p['width']/2,'edge')]
    per100=[]
    for start in np.arange(s0,s1,100):
        end=min(float(start+100),s1);count=int(sum(start<=p['station']<end for p in trees))
        per100.append(dict(start_m=float(start),end_m=end,tree_instances=count,instances_per_100m=count*100/(end-start)))
    minimum=min([road.clearance(p['position'],tree_radius(p,models)) for p in trees]+[road.clearance(p['position'],p['width']/2) for p in edges],default=None)
    report=dict(start_m=s0,end_m=s1,seed=sector_seed(s0,zones.get('seed',24024)),tree_instances=len(trees),
        edge_clumps=len(edges),tree_instances_per_100m=len(trees)*100/(s1-s0),sector_tree_limit=limit,
        full_route_budget_ceiling=int(math.floor(length*density/100)),total_tree_limit=total_limit,
        minimum_all_road_leg_clearance_m=minimum,per_100m=per100,budget_passed=len(trees)<=limit)
    return dict(trees=trees,edges=edges,report=report)


def plan_sectors(data,models,sectors,*,zones=None):
    ordered=sorted(sectors,key=lambda sector:sector['start_m'])
    if any(a['end_m']>b['start_m'] for a,b in zip(ordered,ordered[1:])):raise ValueError('Sector intervals overlap')
    return {sector['name']:plan_sector(data,models,sector['start_m'],sector['end_m'],zones=zones) for sector in ordered}
