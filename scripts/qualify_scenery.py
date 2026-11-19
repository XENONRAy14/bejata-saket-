"""Isolated main-route sector qualification using compiled, cached CC0 assets."""
import configparser
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from scenery_placement import edge_batches, load_zones, plan_sector
from scenery_kn5 import assign_material, clone_material, mesh, nodes, parse_tree, read, string, subset, uint, validate_lock, write
from scenery_assets import dds_blob, edge_atlas, ground_mask, repair_pine_archive
from pilot_common import resize_channels
from treefx_wire import vector_ac

ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='7cceb8c8aeb9ec72b9031d1356b5450b7e1e38c335748964591d84036d13c61f'


def tree_line(plant,models):
    x,y,z=plant['position']
    color=', '.join(f'{v:.9g}' for v in plant.get('color',[1,1,1]))
    return (f"tree: {models[plant['model']]['file']}; pos={x:.9g}, {z:.9g}, {-y:.9g}; "
        f"angle={-np.degrees(plant['angle']):.9g}; size={plant['scale']:.9g}; width={plant['width']:.9g}; color={color}")


def make_installable(output):
    (output/'models.ini').write_text('[MODEL_0]\nFILE=bejaia_saket.kn5\nPOSITION=0,0,0\nROTATION=0,0,0\n')
    path=output/'ui/ui_track.json';metadata=json.loads(path.read_text(encoding='utf-8'))
    metadata['name']='RN24 Béjaïa–Saket — Summit scenery qualification'
    metadata['description']='Separate summit scenery qualification build; not the main RN24 installation.'
    path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


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


def add_texture(base,name,image,coverage=False,data=False):
    blob=dds_blob(image,coverage=coverage,data=data);base['textures'].append(dict(name=name,blob=blob,raw=uint(1)+string(name)+uint(len(blob))+blob))


def forest_ground(base,pilot,select):
    count=0;materials=[]
    for node in list(nodes(base)):
        if node['kind']!=2 or not node['name'].startswith('1GRASS'):continue
        old=base['materials'][node['material']]
        if old['name'] not in ('grass','grass_mountain'):continue
        vertices=np.frombuffer(node['vertices'],'<f4').reshape(-1,11);faces=np.frombuffer(node['indices'],'<u2').reshape(-1,3)
        selected=select(vertices[faces,:3].mean(1))
        if not selected.any():continue
        mask=ground_mask(node,select)
        if not mask.any():continue
        if old['textures']['txDetailB']!=old['textures']['txDetailR'] or old['textures']['txNormalB']!=old['textures']['txNormalR']:
            raise ValueError('Forest floor needs duplicate original grass channels')
        if not any(m['name']=='forest_floor' for m in base['materials']):import_materials(base,pilot,('forest_floor',))
        floor=next(m for m in base['materials'] if m['name']=='forest_floor')
        blob=next(t['blob'] for t in base['textures'] if t['name']==old['textures']['txMask'])
        weights=np.array(resize_channels(Image.open(io.BytesIO(blob)).convert('RGBA'),(mask.shape[1],mask.shape[0]),Image.Resampling.BICUBIC),dtype=np.uint16)
        weights[:,:,0]+=weights[:,:,2];weights[:,:,2]=0
        if weights.max()>255:raise ValueError('Unnormalised original terrain mask')
        weights[mask]=[0,0,255,0]
        name='FOREST_FLOOR_'+node['name'];texture=name+'_mask.dds';add_texture(base,texture,Image.fromarray(weights.astype('uint8')),data=True)
        material=clone_material(old,name,dict(txMask=texture,txDetailB=floor['textures']['txDiffuse'],txNormalB=floor['textures']['txNormal']))
        assign_material(node,len(base['materials']));base['materials'].append(material)
        materials.append(dict(mesh=node['name'],material=name,mask_pixels=int(mask.sum())));count+=int(selected.sum())
    return count,materials


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
    zones=dict(config['main'],edge_spacings_m=[3.6,5],edge_offsets_m=[16,21],edge_widths_m=[[2.5,3.5],[3,4]],edge_heights_m=[[1.4,2],[1.8,2.5]],tree_layers=[
        dict(kind='shrub',spacing=6.8,offset=[9.5,10.5],height_m=[2.8,3.5],width_m=[6.4,6.8],color=[.55,.70,.50]),
        dict(kind='midstory',spacing=15,offset=[16.8,18.3],height_m=[32,36],width_m=[14,16],bury_fraction=.48),
        dict(kind='background',spacing=23.5,offset=[45,52],height_m=[30,36],width_m=[29,33],bury_fraction=.48)])
    dense_models={name:spec for name,spec in models.items() if name!='PH_shrub_02'}
    layout=plan_sector(data,dense_models,s0,s1,zones=zones);select=station_selector(data,s0,s1)
    base=read(baseline);pilot=read(ROOT/'out/bejaia_saket_pilot300/bejaia_saket_pilot300.kn5')
    original_nodes={node['name']:node['raw'] for node in nodes(base)}
    materials=import_materials(base,pilot,('forest_edge',))
    if layout['edges']:
        image=edge_atlas(ROOT/'out/bejaia_saket_pilot300/extension/trees/ph_pine_01.bin',pilot)
        pixels=np.asarray(image).copy();pixels[:,:,:3]=np.uint8(np.clip(pixels[:,:,:3].astype(float)*[.43,.55,.37],0,255))
        add_texture(base,'SUMMIT_forest_edge.dds',Image.fromarray(pixels),coverage=True)
        index=materials['forest_edge'];base['materials'][index]=clone_material(base['materials'][index],'forest_edge',dict(txDiffuse='SUMMIT_forest_edge.dds'))
    floor_triangles,floor_materials=forest_ground(base,pilot,select);legacy_triangles=0
    def modify(parent):
        nonlocal legacy_triangles
        children=[]
        for node in parent['children']:
            if node['kind']==1:modify(node)
            if node['kind']!=2 or not legacy_foliage(node['name']):
                children.append(node);continue
            values=np.frombuffer(node['vertices'],dtype='<f4').reshape(-1,11)
            faces=np.frombuffer(node['indices'],dtype='<u2').reshape(-1,3)
            mask=select(values[faces,:3].mean(axis=1))
            if not mask.any():children.append(node);continue
            kept=subset(node,~mask)
            if kept:children.append(kept)
            legacy_triangles+=int(mask.sum())
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
        if name==base['root']['name'] or name.startswith('1GRASS') or legacy_foliage(name):continue
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
    repaired={}
    for name in sorted({models[plant['model']]['file'] for plant in layout['trees']}):
        repaired[name]=repair_pine_archive(ROOT/'out/bejaia_saket_pilot300/extension/trees'/name,folder/name)
    used={parse_tree(line)['model'] for line in lines}
    for archive in folder.glob('*.bin'):
        if archive.name not in used:archive.unlink()
    if floor_triangles:
        config_path=output/'extension/ext_config.ini';csp=configparser.ConfigParser(interpolation=None);csp.optionxform=str;csp.read(config_path)
        for section,key in (('GRASS_FX','GRASS_MATERIALS'),('RAIN_FX','ROUGH_MATERIALS')):
            csp[section][key]=csp[section][key]+', '+', '.join(m['material'] for m in floor_materials)
        stream=io.StringIO();csp.write(stream);config_path.write_text(stream.getvalue().rstrip()+'\n')
    physics=validate_lock(baseline,output/'bejaia_saket.kn5')
    added=[n for n in nodes(base) if n['name'].startswith('SCENERY_')]
    meshes=[n for n in nodes(base) if n['kind']==2]
    report=dict(sector=sector,placement=layout['report'],old_tree_instances_removed=removed,
        tree_layer_counts={kind:sum(models[p['model']]['kind']==kind for p in layout['trees']) for kind in ('shrub','midstory','background','pine')},
        main_tree_instances_retained=len(kept),new_tree_instances=len(layout['trees']),total_tree_instances=len(lines),
        legacy_foliage_triangles_removed=legacy_triangles,forest_floor_triangles=floor_triangles,
        forest_floor_materials=floor_materials,repaired_medium_lods=repaired,
        forest_floor_applied=bool(floor_triangles),qualification_complete=False,visual_review_required=True,
        forest_floor_blocker=None if floor_triangles else 'No eligible existing grass in the sector',
        added_meshes=len(added),added_vertices=sum(len(n['vertices'])//44 for n in added),
        added_triangles=sum(len(n['indices'])//6 for n in added),total_meshes=len(meshes),
        total_vertices=sum(len(n['vertices'])//44 for n in meshes),total_triangles=sum(len(n['indices'])//6 for n in meshes),
        kn5_bytes=(output/'bejaia_saket.kn5').stat().st_size,physics_lock=physics,
        source_blender_assets_required=False,runtime_tested=False)
    (output/'scenery_report.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'scenery_placements.json').write_text(json.dumps(layout,indent=2)+'\n')
    print('PHYSICS_LOCK_OK',json.dumps(physics));print('SCENERY_QUALIFICATION_PARTIAL',json.dumps(report))
    return output
