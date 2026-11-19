"""Keep the accepted summit hedge while replacing its rear walls with pine volumes."""
import copy
import hashlib
import json
import math

import numpy as np

from pilot_common import ground
from scenery_placement import RoadClearance, sector_seed, sea_sides, tree_footprints, tree_radius, vista_open, zone_contains


def hedge_signature(layout):
    shrubs=[p for p in layout['trees'] if p['model'].startswith('PH_shrub')]
    filler=[p for p in layout['edges'] if p['tier']<2]
    digest=lambda items:hashlib.sha256(json.dumps(items,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(shrubs=len(shrubs),filler_clumps=len(filler),shrubs_sha256=digest(shrubs),filler_sha256=digest(filler))


def natural_summit(data,models,accepted,zones):
    if not accepted['trees'] and not accepted['edges']:return copy.deepcopy(accepted)
    s0=accepted['report']['start_m'];s1=accepted['report']['end_m']
    shrubs=[copy.deepcopy(p) for p in accepted['trees'] if models[p['model']]['kind']=='shrub']
    edges=[copy.deepcopy(p) for p in accepted['edges'] if p['tier']<2]
    kinds={kind:[name for name,spec in models.items() if spec['kind']==kind and 'sapling' not in name] for kind in ('pine','midstory')}
    if not all(kinds.values()):raise ValueError('Natural summit needs adult and midstory pine models')
    rng=np.random.default_rng(sector_seed(s0,zones.get('seed',24024),'natural-pines'))
    sea=sea_sides(data,zones.get('side_smoothing_m',30));road=RoadClearance(data);candidates=[]
    for side in (0,1):
        station=s0+float(rng.uniform(5,9))
        while station<s1-6:
            for member in range(2 if rng.random()<.5 else 1):
                s=min(s1-3,station+(float(rng.uniform(1.5,4.5)) if member else 0))
                kind='midstory' if rng.random()<.45 else 'pine'
                if vista_open(s,s1-s0,side,sea(s),zones=zones,layer=kind):continue
                species=kinds[kind][int(rng.integers(len(kinds[kind])))];model=models[species]
                height=float(rng.uniform(16,27));scale=height/model['height'];broad=float(rng.uniform(1.5,1.85))
                p=dict(model=species,scale=scale,width=broad,angle=float(rng.uniform(0,2*np.pi)),station=float(s),side=side)
                radius=tree_radius(p,models);half=float(np.interp(s,data['s3'],data['width']))/2
                offset=half+radius+float(rng.uniform(4.7,7.7))+(float(rng.uniform(4,9)) if member else 0)
                point=ground(data,s,side,offset);edge=ground(data,s,side,half)
                anchor=height*float(rng.uniform(.10,.28)) if member else -height*float(rng.uniform(.14,.24))
                point[2]=min(point[2],edge[2]+anchor)
                p.update(position=point.tolist(),offset=offset)
                if zone_contains(s,side,sea(s),zones,'exclusions',kind,radius) or not road.allows(point,radius,4):continue
                candidates.append(p)
            station+=float(rng.uniform(6,11))
    pines=[];bins=[]
    for start in np.arange(s0,s1,100):
        end=min(float(start+100),s1);cap=int(math.floor((end-start)*.60))
        front=int(sum(start<=p['station']<end for p in shrubs))
        if front>cap:raise ValueError('Accepted hedge exceeds local 60/100 m budget')
        choices=[i for i,p in enumerate(candidates) if start<=p['station']<end]
        scores={i:float(rng.random())**(1/(2.5 if candidates[i]['side']!=sea(candidates[i]['station']) else 1)) for i in choices}
        chosen=sorted(sorted(choices,key=lambda i:scores[i],reverse=True)[:cap-front])
        pines.extend(candidates[i] for i in chosen)
        bins.append(dict(start_m=float(start),end_m=end,tree_instances=front+len(chosen),instances_per_100m=(front+len(chosen))*100/(end-start)))
    trees=shrubs+pines
    minimum=min([road.clearance(point,radius) for p in trees for point,radius in tree_footprints(p,models)]+[road.clearance(p['position'],p['width']/2) for p in edges],default=None)
    report=dict(accepted['report'],tree_instances=len(trees),edge_clumps=len(edges),tree_instances_per_100m=len(trees)*100/(s1-s0),
        sector_tree_limit=int(math.floor((s1-s0)*.60)),per_100m=bins,minimum_all_road_leg_clearance_m=minimum,
        budget_passed=all(b['instances_per_100m']<=60 for b in bins),hedge_preserved=hedge_signature(accepted)==hedge_signature(dict(trees=trees,edges=edges)))
    return dict(trees=trees,edges=edges,report=report)
