"""Derive an active layout without resmoothing the canonical road."""
import json
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

ROOT=Path(__file__).resolve().parents[1]


def road_distance(data):
    return np.r_[0,np.cumsum(np.linalg.norm(np.diff(np.column_stack([data['xy'],data['z']]),axis=0),axis=1))]


def source_offset(data):
    return float(data['source_start_s']) if 'source_start_s' in data else 0.


def active_chainage(data,canonical_chainage):
    return canonical_chainage-source_offset(data)


def canonical_chainage(data,chainage):
    return chainage+source_offset(data)


def shorten(full,config):
    s=np.asarray(full['s']);z=np.asarray(full['z'])
    if len(s)<3 or not np.isfinite(s).all() or np.any(np.diff(s)<=0) or not np.isfinite(z).all():
        raise ValueError('Need a finite canonical centerline with increasing chainage')
    if any(not np.isfinite(v) or v<=0 for v in config.values()):raise ValueError('Layout distances must be positive and finite')
    d=road_distance(full)
    peaks,_=find_peaks(z,prominence=config['summit_prominence_m'])
    if not len(peaks):raise ValueError('No prominent summit in canonical profile')
    summit=int(peaks[np.argmax(z[peaks])])
    troughs,_=find_peaks(-z,prominence=10)
    following=troughs[troughs>summit]
    bottom=int(following[0]) if len(following) else len(s)-1
    if z[summit]-z[bottom]<config['minimum_main_descent_drop_m'] or d[bottom]-d[summit]<config['minimum_main_descent_length_m']:
        raise ValueError('Highest prominent summit does not begin the required main descent')
    spawn=d[summit]-config['spawn_before_summit_3d_m']
    cut=spawn-config['pad_before_spawn_3d_m'];gate=spawn+config['start_gate_ahead_3d_m']
    if cut<=0 or gate>=d[summit]:raise ValueError('Layout offsets do not fit before summit')
    cut_s,spawn_s,gate_s=np.interp([cut,spawn,gate],d,s)
    stations=np.unique(np.r_[cut_s,spawn_s,gate_s,s[s>cut_s]])
    result={}
    for key,value in full.items():
        value=np.asarray(value);axis=1 if key in ('sides','offsets','guard','cut') else 0
        moved=np.moveaxis(value,axis,0)
        if len(moved)!=len(s):raise ValueError(f'Unexpected canonical array {key}')
        if value.dtype==bool:
            sampled=moved[np.minimum(np.searchsorted(s,stations),len(s)-1)]
        else:
            sampled=np.column_stack([np.interp(stations,s,column) for column in moved.reshape(len(s),-1).T]).reshape((len(stations),*moved.shape[1:]))
        result[key]=np.moveaxis(sampled,0,axis)
    result.update(s=stations-cut_s,source_s=stations,source_start_s=np.array(cut_s),spawn_s=np.array(spawn_s-cut_s),start_gate_s=np.array(gate_s-cut_s))
    result['s3']=road_distance(result)
    info=dict(canonical_length_2d_m=float(s[-1]),canonical_length_3d_m=float(d[-1]),canonical_summit_index=summit,canonical_summit_2d_m=float(s[summit]),canonical_summit_3d_m=float(d[summit]),summit_elevation_m=float(z[summit]),canonical_cut_2d_m=float(cut_s),canonical_cut_3d_m=float(cut),canonical_spawn_2d_m=float(spawn_s),canonical_spawn_3d_m=float(spawn),spawn_s_m=float(spawn_s-cut_s),start_gate_s_m=float(gate_s-cut_s),spawn_before_summit_3d_m=float(d[summit]-spawn),pad_3d_m=float(spawn-cut),start_gate_ahead_3d_m=float(gate-spawn),length_2d_m=float(result['s'][-1]),length_3d_m=float(result['s3'][-1]),main_descent_drop_m=float(z[summit]-z[bottom]),main_descent_length_3d_m=float(d[bottom]-d[summit]),retained_original_samples=int(np.sum(s>=cut_s)))
    return result,info


def derive_layout(full,metrics,root=ROOT):
    root=Path(root);config=json.loads((root/'data/track_layout.json').read_text())
    np.savez_compressed(root/'data/full_centerline.npz',**full)
    (root/'data/full_geometry_info.json').write_text(json.dumps(metrics,indent=2)+'\n')
    active,info=shorten(full,config)
    from geometry import INVERSE
    origin=json.loads((root/'data/geo_origin.json').read_text())
    coordinates=np.column_stack(INVERSE.transform(active['xy'][:,0]+origin['easting_m'],active['xy'][:,1]+origin['northing_m']))
    pole=np.searchsorted(active['s'],float(active['spawn_s']))
    info['spawn_lon_lat']=coordinates[pole].tolist()
    info['spawn_elevation_m']=float(active['z'][pole])
    info['summit_active_s_m']=float(full['s'][info['canonical_summit_index']]-info['canonical_cut_2d_m'])
    feature=dict(type='FeatureCollection',features=[dict(type='Feature',properties=dict(name='RN24 summit approach to Saket',length_3d_m=info['length_3d_m']),geometry=dict(type='LineString',coordinates=np.column_stack([coordinates,active['z']]).tolist()))])
    (root/'data/active_route.geojson').write_text(json.dumps(feature)+'\n')
    import xml.etree.ElementTree as ET
    gpx=ET.Element('gpx',version='1.1',creator='bejaia_saket',xmlns='http://www.topografix.com/GPX/1/1')
    segment=ET.SubElement(ET.SubElement(gpx,'trk'),'trkseg')
    for (lon,lat),height in zip(coordinates,active['z']):
        point=ET.SubElement(segment,'trkpt',lat=str(lat),lon=str(lon));ET.SubElement(point,'ele').text=str(height)
    ET.ElementTree(gpx).write(root/'data/active_route.gpx',encoding='utf-8',xml_declaration=True)
    np.savez_compressed(root/'data/centerline.npz',**active)
    (root/'data/shortening_info.json').write_text(json.dumps(info,indent=2)+'\n')
    grade=np.diff(active['z'])/np.diff(active['s'])
    metrics.update(length_m=info['length_2d_m'],length_3d_m=info['length_3d_m'],samples=len(active['s']),min_elevation_m=float(active['z'].min()),max_elevation_m=float(active['z'].max()),max_grade_percent=float(abs(grade).max()*100),total_climb_m=float(np.maximum(np.diff(active['z']),0).sum()),canonical_cut_2d_m=info['canonical_cut_2d_m'],spawn_before_summit_3d_m=info['spawn_before_summit_3d_m'])
    ds=np.diff(active['s']);width=active['offsets'][:,:,0].sum(axis=0)
    metrics.update(guardrail_m=[float(np.sum(ds*a[:-1])) for a in active['guard']],cut_m=[float(np.sum(ds*a[:-1])) for a in active['cut']],width_range_m=[float(active['width'].min()),float(active['width'].max())],actual_min_width_m=float(width.min()),narrowed_length_m=float(ds[width[:-1]<active['width'][:-1]-.01].sum()),min_terrain_extent_m=float(active['offsets'][:,:,-1].min()),mean_abs_elevation_error_m=float(np.mean(abs(active['z']-active['filtered']))),max_abs_elevation_error_m=float(np.max(abs(active['z']-active['filtered']))),mean_signed_elevation_error_m=float(np.mean(active['z']-active['filtered'])))
    print('SHORTENING_OK '+json.dumps(info),flush=True)
    return active,metrics
