"""Staged route, DEM, centerline and headless Blender mesh build."""
import argparse
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import networkx as nx
import osmium

ROOT = Path(__file__).resolve().parents[1]
BBOX = (4.85, 36.68, 5.10, 36.85)
HIGHWAYS = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'unclassified', 'residential'}
HIGHWAYS |= {h + '_link' for h in list(HIGHWAYS) if h not in {'unclassified', 'residential'}}


def distance(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    x = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(x)))


def inside(p):
    return BBOX[0] <= p[0] <= BBOX[2] and BBOX[1] <= p[1] <= BBOX[3]


class Extract(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways, self.places = [], []

    def node(self, n):
        p = [n.location.lon, n.location.lat]
        if inside(p) and re.search(r'saket|ساكت', ' '.join(t.v for t in n.tags), re.I):
            self.places.append(dict(type='node', id=n.id, coords=p, tags=dict(n.tags)))

    def way(self, w):
        tags = dict(w.tags)
        if not (tags.get('highway') or tags.get('natural') in {'coastline', 'beach'} or re.search(r'saket|ساكت', ' '.join(tags.values()), re.I)):
            return
        coords = [[n.lon, n.lat] for n in w.nodes if n.location.valid()]
        if len(coords) != len(w.nodes) or not any(map(inside, coords)):
            return
        self.ways.append(dict(id=w.id, nodes=[n.ref for n in w.nodes], coords=coords, tags=tags))
        if re.search(r'saket|ساكت', ' '.join(tags.values()), re.I):
            self.places.append(dict(type='way', id=w.id, coords=[sum(p[i] for p in coords)/len(coords) for i in (0, 1)], tags=tags))


def load():
    cache = ROOT / 'data/area_cache.json'
    if cache.exists():
        cached = json.loads(cache.read_text())
        if cached['bbox'] == list(BBOX):
            return cached
    handler = Extract()
    handler.apply_file(str(ROOT / 'data/algeria-latest.osm.pbf'), locations=True, idx='flex_mem')
    data = dict(bbox=BBOX, ways=handler.ways, places=handler.places)
    cache.write_text(json.dumps(data, ensure_ascii=False))
    return data


def graph(ways):
    g = nx.DiGraph()
    for w in ways:
        t = w['tags']
        if t.get('highway') not in HIGHWAYS or t.get('area') == 'yes':
            continue
        if any(t.get(k) in {'no', 'private'} for k in ('access', 'vehicle', 'motor_vehicle', 'motorcar')):
            continue
        ref = re.sub(r'[^A-Z0-9]', '', t.get('ref', '').upper())
        penalty = 1 if ref in {'N24', 'RN24'} else (1.3 if t['highway'].split('_')[0] in {'trunk', 'primary'} else 3)
        oneway = t.get('oneway', 'yes' if t.get('junction') == 'roundabout' or t['highway'] == 'motorway' else 'no')
        for i, (a, b) in enumerate(zip(w['nodes'], w['nodes'][1:])):
            p, q = w['coords'][i:i+2]
            if not (inside(p) and inside(q)):
                continue
            g.add_node(a, coords=p)
            g.add_node(b, coords=q)
            length = distance(p, q)
            for u, v in ([(a, b)] if oneway in {'yes', '1', 'true'} else [(b, a)] if oneway == '-1' else [(a, b), (b, a)]):
                if not g.has_edge(u, v) or g[u][v]['weight'] > length * penalty:
                    g.add_edge(u, v, length=length, weight=length*penalty, way=w['id'], tags=t)
    return g


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['route', 'dem', 'centerline', 'mesh'])
    parser.add_argument('--blender', default=str(Path.home() / 'tools/blender-3.6.23-linux-x64/blender'))
    parser.add_argument('--list-places', action='store_true')
    args = parser.parse_args()
    if args.stage != 'route':
        from geometry import acquire_dem, centerline, mesh
        {'dem': acquire_dem, 'centerline': centerline, 'mesh': lambda: mesh(args.blender)}[args.stage]()
        return
    data = load()
    if args.list_places:
        print(json.dumps(data['places'], ensure_ascii=False, indent=2))
        return
    beaches = [p for p in data['places'] if p['tags'].get('natural') == 'beach']
    if not beaches:
        raise ValueError('No named Saket beach found')
    beach = sorted(beaches, key=lambda p: p['id'])[0]
    g = graph(data['ways'])
    main_nodes = {n for u, v, e in g.edges(data=True) if e['tags']['highway'] in {'primary', 'secondary', 'tertiary', 'trunk'} for n in (u, v)}
    nearest = lambda point, nodes: min(nodes, key=lambda n: distance(point, g.nodes[n]['coords']))
    start = nearest([5.087, 36.752], main_nodes)
    end = nearest(beach['coords'], main_nodes)
    path = nx.shortest_path(g, start, end, weight='weight')
    coords = [g.nodes[n]['coords'] for n in path]
    edges = [g[u][v] for u, v in zip(path, path[1:])]
    segments = []
    for e in edges:
        if not segments or segments[-1]['osm_way_id'] != e['way']:
            segments.append(dict(osm_way_id=e['way'], **{k:e['tags'].get(k) for k in ('name', 'ref', 'highway', 'lanes', 'width', 'oneway')}, length_m=0))
        segments[-1]['length_m'] += e['length']
    info = dict(length_km=sum(e['length'] for e in edges)/1000, start=dict(osm_node_id=start, coords=coords[0]), end=dict(osm_node_id=end, coords=coords[-1]), destination=beach, destination_snap_m=distance(beach['coords'], coords[-1]), node_count=len(path), bbox=BBOX, roads=segments, source='https://download.geofabrik.de/africa/algeria-latest.osm.pbf', routing='Directed weighted shortest path; N24/RN24=1, other trunk/primary=1.3, others=3; no/private motor access excluded. Turn restrictions not modelled.')
    (ROOT/'data/route_info.json').write_text(json.dumps(info, ensure_ascii=False, indent=2)+'\n')
    feature = dict(type='FeatureCollection', features=[dict(type='Feature', properties=dict(name='Béjaïa to Saket', length_km=info['length_km']), geometry=dict(type='LineString', coordinates=coords))])
    (ROOT/'data/route.geojson').write_text(json.dumps(feature, ensure_ascii=False)+'\n')
    gpx = ET.Element('gpx', version='1.1', creator='bejaia_saket', xmlns='http://www.topografix.com/GPX/1/1')
    track = ET.SubElement(ET.SubElement(gpx, 'trk'), 'trkseg')
    for lon, lat in coords:
        ET.SubElement(track, 'trkpt', lat=str(lat), lon=str(lon))
    ET.ElementTree(gpx).write(ROOT/'data/route.gpx', encoding='utf-8', xml_declaration=True)
    fig, ax = plt.subplots(figsize=(15, 9))
    ax.set_facecolor('#eef0e9')
    for kind, color, width in [('roads', '#a9adb0', .55), ('coast', '#1686a3', 1.8)]:
        lines = [w['coords'] for w in data['ways'] if (bool(w['tags'].get('highway')) if kind == 'roads' else w['tags'].get('natural') == 'coastline')]
        ax.add_collection(LineCollection(lines, colors=color, linewidths=width))
    ax.plot(*zip(*coords), color='#df432c', linewidth=2.6, label=f'Route: {info["length_km"]:.2f} km')
    for point, label in [(coords[0], 'Béjaïa start'), (coords[-1], 'Saket road finish'), (beach['coords'], 'Plage de Saket (OSM)')]:
        ax.scatter(*point, s=28, zorder=5)
        ax.annotate(label, point, xytext=(5, 9), textcoords='offset points', fontsize=9)
    ax.set(xlim=(min(p[0] for p in coords)-.012, max(p[0] for p in coords)+.012), ylim=(min(p[1] for p in coords)-.015, max(p[1] for p in coords)+.016), xlabel='Longitude (WGS84)', ylabel='Latitude (WGS84)', title='Béjaïa → Plage de Saket | coastal RN24 corridor')
    ax.set_aspect(1/math.cos(math.radians(36.75)))
    ax.legend(loc='lower left')
    fig.text(.12, .03, '© OpenStreetMap contributors · ODbL · Geofabrik Algeria extract | blue: coastline; grey: OSM roads | no elevation/geometry yet', fontsize=9)
    fig.savefig(ROOT/'out/preview/route_preview.png', dpi=160, bbox_inches='tight')
    print(f'ROUTE_OK length_km={info["length_km"]:.3f} nodes={len(path)} start={start} end={end}')
    print(json.dumps(beach, ensure_ascii=False))
    print('Roads:', sorted({(e['tags'].get('name', ''), e['tags'].get('ref', '')) for e in edges}))


if __name__ == '__main__':
    main()
