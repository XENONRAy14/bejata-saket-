"""Isolated main-route sector qualification using compiled, cached CC0 assets."""
import configparser
import hashlib
import json
from pathlib import Path
import shutil
import struct

import numpy as np
from scipy.spatial import cKDTree

from scenery_placement import edge_batches, load_zones, plan_sector
from scenery_kn5 import mesh, nodes, parse_tree, read, subset, validate_lock, write
from treefx_wire import vector_ac

ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='7cceb8c8aeb9ec72b9031d1356b5450b7e1e38c335748964591d84036d13c61f'


def tree_line(plant,models):
    x,y,z=plant['position']
    return (f"tree: {models[plant['model']]['file']}; pos={x:.9g}, {z:.9g}, {-y:.9g}; "
        f"angle={-np.degrees(plant['angle']):.9g}; size={plant['scale']:.9g}; width={plant['width']:.9g}; color=1, 1, 1")


def make_installable(output):
    (output/'models.ini').write_text('[MODEL_0]\nFILE=bejaia_saket.kn5\nPOSITION=0,0,0\nROTATION=0,0,0\n')
    path=output/'ui/ui_track.json';metadata=json.loads(path.read_text())
    metadata['name']='RN24 Béjaïa–Saket — Summit scenery qualification'
    metadata['description']='Separate summit scenery qualification build; not the main RN24 installation.'
    path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')


def station_selector(data,s0,s1):
    index=cKDTree(data['xy'])
    def select(ac_points):
        points=np.asarray(ac_points)
        distance,nearest=index.query(points[:,[0,2]]*[1,-1])
        return (data['s3'][nearest]>=s0)&(data['s3'][nearest]<s1)&(distance<=80+float(data['width'].max())/2)
    return select


def legacy_foliage(name):
    return name.startswith('DECOR_VEG_') or (name.startswith('DECOR_') and name.endswith(('_pine_foliage','_olive_foliage','_maquis')))


def import_materials(base,pilot,names):
    imported={}
    existing={texture['name']:texture['blob'] for texture in base['textures']}
    for name in names:
        material=next(mat for mat in pilot['materials'] if mat['name']==name)
        if any(mat['name']==name for mat in base['materials']):raise ValueError('Scenery material already present')
        for texture_name in material['textures'].values():
            texture=next(t for t in pilot['textures'] if t['name']==texture_name)
            if texture_name in existing:
                if existing[texture_name]!=texture['blob']:raise ValueError('Conflicting cached texture '+texture_name)
            else:base['textures'].append(texture);existing[texture_name]=texture['blob']
        imported[name]=len(base['materials']);base['materials'].append(material)
    return imported


def qualify(sector='summit',output=None):
    if sector!='summit':raise ValueError('Only summit is qualified in this step')
    source=ROOT/'out/bejaia_saket';baseline=source/'bejaia_saket.kn5'
    if hashlib.sha256(baseline.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Unexpected main KN5 baseline; requalification required')
    output=Path(output or ROOT/'out/scenery_qualification/summit').resolve()
    if output==source.resolve() or source.resolve() in output.parents:raise ValueError('Cannot overwrite main install')
    if output.exists():raise FileExistsError('Qualification output already exists: '+str(output))
    config=load_zones();spec=next(s for s in config['report_sectors'] if s['name']==sector)
    s0,s1=spec['start_m'],spec['end_m']
    with np.load(ROOT/'data/centerline.npz') as datafile:data=dict(datafile)
    models=json.loads((ROOT/'data/pilot300/treefx_models.json').read_text())
    layout=plan_sector(data,models,s0,s1,zones=config['main']);select=station_selector(data,s0,s1)
    base=read(baseline);pilot=read(ROOT/'out/bejaia_saket_pilot300/bejaia_saket_pilot300.kn5')
    original_nodes={node['name']:node['raw'] for node in nodes(base)}
    materials=import_materials(base,pilot,('forest_edge',))
    floor_triangles=legacy_triangles=0
    def modify(parent):
        nonlocal floor_triangles,legacy_triangles
        children=[]
        for node in parent['children']:
            if node['kind']==1:modify(node)
            if node['kind']!=2 or not (legacy_foliage(node['name']) or (node['name'].startswith('LAND_') and base['materials'][node['material']]['name']=='grass')):
                children.append(node);continue
            values=np.frombuffer(node['vertices'],dtype='<f4').reshape(-1,11)
            faces=np.frombuffer(node['indices'],dtype='<u2').reshape(-1,3)
            mask=select(values[faces,:3].mean(axis=1))
            if not legacy_foliage(node['name']):mask&=select(values[faces,:3].reshape(-1,3)).reshape(-1,3).all(axis=1)
            if not mask.any():children.append(node);continue
            kept=subset(node,~mask)
            if kept:children.append(kept)
            if legacy_foliage(node['name']):legacy_triangles+=int(mask.sum())
            else:
                if 'forest_floor' not in materials:materials.update(import_materials(base,pilot,('forest_floor',)))
                floor=subset(node,mask,name='SCENERY_FLOOR_'+node['name'],material=materials['forest_floor'],forest_uv=True)
                children.append(floor);floor_triangles+=int(mask.sum())
        parent['children']=children
    modify(base['root'])
    for distant in (False,True):
        for (chunk,side),(vertices,quads,uv,normals) in edge_batches(data,layout['edges'],distant=distant).items():
            values=np.zeros((len(vertices),11),dtype='<f4');values[:,:3]=vector_ac(vertices);values[:,3:6]=vector_ac(normals)
            values[:,6:8]=np.asarray(uv)*[1,-1]
            tangents=np.cross(values[:,3:6],[0,1,0]);tangents/=np.linalg.norm(tangents,axis=1)[:,None];values[:,8:11]=tangents
            faces=[triangle for a,b,c,d in quads for triangle in ((a,b,c),(a,c,d))]
            node=mesh(f"SCENERY_{'FAR' if distant else 'NEAR'}_EDGE_{chunk}_{side}",values,faces,materials['forest_edge'])
            tail=bytearray(node['tail'])
            struct.pack_into('<2f',tail,4,110 if distant else 0,350 if distant else 110)
            node=mesh(node['name'],values,faces,materials['forest_edge'],flags=bytes([not distant,True,False]),tail=bytes(tail))
            base['root']['children'].append(node)
    # Preserve every unrelated original record, not only the physical subset.
    current={node['name']:node['raw'] for node in nodes(base)}
    for name,raw in original_nodes.items():
        if name==base['root']['name'] or name.startswith('LAND_') or legacy_foliage(name):continue
        if current.get(name)!=raw:raise ValueError('Unrelated main node changed: '+name)
    old_lines=(source/'extension/trees/trees.txt').read_text().splitlines()
    kept=[];removed=0
    for line in old_lines:
        tree=parse_tree(line);ac=vector_ac([tree['position']])
        if select(ac)[0]:removed+=1
        else:kept.append(line)
    lines=kept+[tree_line(plant,models) for plant in layout['trees']]
    if len(lines)>8000:raise ValueError('Combined TreeFX count exceeds 8000')
    shutil.copytree(source,output)
    make_installable(output)
    (output/'PILOT_ASSET_CREDITS.md').write_text((ROOT/'out/bejaia_saket_pilot300/CREDITS.md').read_text())
    (output/'PILOT_ASSET_LICENSES.json').write_text((ROOT/'out/bejaia_saket_pilot300/LICENSES.json').read_text())
    write(output/'bejaia_saket.kn5',base)
    folder=output/'extension/trees';(folder/'trees.txt').write_text('\n'.join(lines)+'\n')
    for plant in layout['trees']:
        name=models[plant['model']]['file'];shutil.copyfile(ROOT/'out/bejaia_saket_pilot300/extension/trees'/name,folder/name)
    used={parse_tree(line)['model'] for line in lines}
    for archive in folder.glob('*.bin'):
        if archive.name not in used:archive.unlink()
    if floor_triangles:
        config_path=output/'extension/ext_config.ini';csp=configparser.ConfigParser(interpolation=None);csp.optionxform=str;csp.read(config_path)
        for section,key in (('GRASS_FX','GRASS_MATERIALS'),('RAIN_FX','ROUGH_MATERIALS')):
            csp[section][key]=csp[section][key]+', forest_floor'
        with config_path.open('w') as stream:csp.write(stream)
    physics=validate_lock(baseline,output/'bejaia_saket.kn5')
    added=[n for n in nodes(base) if n['name'].startswith('SCENERY_')]
    meshes=[n for n in nodes(base) if n['kind']==2]
    report=dict(sector=sector,placement=layout['report'],old_tree_instances_removed=removed,
        main_tree_instances_retained=len(kept),new_tree_instances=len(layout['trees']),total_tree_instances=len(lines),
        legacy_foliage_triangles_removed=legacy_triangles,forest_floor_triangles=floor_triangles,
        forest_floor_applied=bool(floor_triangles),qualification_complete=bool(floor_triangles),
        forest_floor_blocker=None if floor_triangles else 'No existing visual-only ground inside the 80m summit corridor; nearby ground is physical and locked',
        added_meshes=len(added),added_vertices=sum(len(n['vertices'])//44 for n in added),
        added_triangles=sum(len(n['indices'])//6 for n in added),total_meshes=len(meshes),
        total_vertices=sum(len(n['vertices'])//44 for n in meshes),total_triangles=sum(len(n['indices'])//6 for n in meshes),
        kn5_bytes=(output/'bejaia_saket.kn5').stat().st_size,physics_lock=physics,
        source_blender_assets_required=False,runtime_tested=False)
    (output/'scenery_report.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'scenery_placements.json').write_text(json.dumps(layout,indent=2)+'\n')
    print('PHYSICS_LOCK_OK',json.dumps(physics));print('SCENERY_QUALIFICATION_'+('OK' if floor_triangles else 'PARTIAL'),json.dumps(report))
    return output
