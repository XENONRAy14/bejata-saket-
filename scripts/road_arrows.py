"""Choose a few OSM junction approaches for unique road-chunk atlases."""
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
from geometry import FORWARD


def select_junctions(data,ways,origin):
    if len(data['xy'])<2:raise ValueError('Need centerline points')
    neighbors=defaultdict(set);coordinates={}
    for way in ways:
        if way['tags'].get('highway') not in ('primary','secondary','tertiary','residential','unclassified','trunk'):continue
        for node,point in zip(way['nodes'],way['coords']):coordinates[node]=point
        for a,b in zip(way['nodes'],way['nodes'][1:]):neighbors[a].add(b);neighbors[b].add(a)
    points=[coordinates[n] for n,v in neighbors.items() if len(v)>=3]
    if not points:return []
    xy=np.column_stack(FORWARD.transform(*np.asarray(points).T))-origin
    distance,nearest=cKDTree(data['xy']).query(xy);result=[]
    for i in nearest[distance<18]:
        chainage=float(data['s'][i]-25)
        if not 100<chainage<data['s'][-1]-50:continue
        chunk=int(chainage//400)
        if any(r['chunk']==chunk or abs(r['chainage_m']-chainage)<300 for r in result):continue
        result.append(dict(chunk=chunk,chainage_m=chainage))
        if len(result)>=3:break
    return result
