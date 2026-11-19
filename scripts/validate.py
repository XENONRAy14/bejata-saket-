"""Standalone exported-package checks, not a substitute for AC driving tests."""
import argparse
import configparser
import json
from pathlib import Path
import re

import numpy as np
import shapely
from PIL import Image
from scipy.spatial import cKDTree

from check_kn5 import inspect_kn5, mask_mip_error
from csp import config_materials
from vegetation import footprint

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('README.md','CREDITS.md','data/surfaces.ini','data/map.ini','ui/ui_track.json',
            'ui/preview.png','ui/outline.png','map.png','ai/README.txt','extension/ext_config.ini')
UI_KEYS = {'name','description','tags','geotags','country','city','length','width','pitboxes','run','author','version','year'}
EMPTIES = {f'AC_PIT_{i}' for i in range(4)} | {'AC_START_0','AC_START_1','AC_HOTLAP_START_0'}
EMPTIES |= {f'AC_{gate}_{side}' for gate in ('AB_START','AB_FINISH','TIME_0','TIME_1') for side in ('L','R')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(folder):
    folder = Path(folder)
    results = []
    def check(name, action):
        try:
            detail = action()
            results.append(True)
            print(f'PASS {name}: {detail}')
        except Exception as exc:
            results.append(False)
            print(f'FAIL {name}: {exc}')
    def folder_name():
        require(re.fullmatch('[a-z0-9_]+',folder.name), 'expected lowercase [a-z0-9_] folder name')
        return folder.name
    check('folder_name', folder_name)
    def files():
        missing = [p for p in (*REQUIRED,folder.name+'.kn5') if not (folder/p).is_file()]
        require(not missing, f'missing {missing}')
        allowed = set(REQUIRED) | {folder.name+'.kn5'}
        extra = {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()}-allowed
        extra={p for p in extra if not (p.startswith('extension/trees/') and len(Path(p).parts)==3 and Path(p).suffix in ('.bin','.txt','.dds'))}
        require(not extra, f'unexpected install files {sorted(extra)}')
        return f'{len(allowed)} install files'
    check('required_files', files)
    parsed = {}
    def readback():
        parsed.update(inspect_kn5(folder/(folder.name+'.kn5'), geometry='all', texture_data=True))
        return f"v5, {parsed['bytes']} bytes"
    check('kn5_readback', readback)
    nodes = parsed.get('nodes',[])
    meshes = [n for n in nodes if n['kind']==2]
    logical = [n for n in nodes if n['kind']==1 and n['name'].lower().startswith('ac_')]
    def ui():
        data = json.loads((folder/'ui/ui_track.json').read_text(encoding='utf-8'))
        require(UI_KEYS <= data.keys(), f'missing UI keys {sorted(UI_KEYS-data.keys())}')
        count = sum(bool(re.fullmatch(r'AC_PIT_\d+',n['name'])) for n in logical)
        require(count>0 and int(data['pitboxes'])==count, f'pitboxes does not match {count} pits')
        require(len(data['geotags'])==2 and all(np.isfinite(float(v)) for v in data['geotags']), 'invalid geotags')
        return f'UTF-8 JSON, required keys present, pitboxes={count}'
    check('ui_metadata', ui)
    physical = []
    def surfaces():
        ini = configparser.ConfigParser();ini.read(folder/'data/surfaces.ini')
        keys = {s['KEY'] for s in ini.values() if 'KEY' in s}
        require('WALL' not in keys, 'WALL is a built-in collision type, not a declared driving surface')
        require(meshes, 'no meshes')
        for mesh in meshes:
            match = re.fullmatch(r'[1-9][0-9]*([A-Z]+)(?:_.*)?',mesh['name'])
            if match:
                require(match[1]=='WALL' or match[1] in keys, f"undefined surface {match[1]} for {mesh['name']}")
                physical.append(mesh)
            else:
                require(mesh['name'].startswith(('DECOR_','LAND_','DETAIL_')), f"invalid physical/visual mesh name {mesh['name']}")
        require(physical, 'no physical meshes')
        return 'physical keys '+','.join(sorted(keys))
    check('mesh_names_and_surfaces', surfaces)
    def empties():
        names = [n['name'] for n in logical]
        require(set(names)>=EMPTIES, f'missing {sorted(EMPTIES-set(names))}')
        require(len(names)==len(set(names)) and all(n==n.upper() for n in names), 'duplicate or lowercase empties')
        for n in logical:
            matrix = np.asarray(n['matrix']).reshape(4,4)
            require(np.allclose(matrix[:3,:3]@matrix[:3,:3].T,np.eye(3),atol=1e-4), 'non-unit logical transform')
        return f'{len(logical)} uppercase, required gates/spawns, unit transforms'
    check('required_empties', empties)
    roads = [n for n in meshes if n['name'].startswith('1ROAD_') and 'positions' in n]
    triangles = np.concatenate([n['positions'][n['indices']] for n in roads]) if roads else np.empty((0,3,3))
    def heights():
        require(len(triangles)>0 and logical, 'missing road triangles or empties')
        horizontal = triangles[:,:,[0,2]].astype(float)
        tree = cKDTree(horizontal.mean(axis=1))
        offsets = []
        for n in logical:
            point = np.asarray(n['matrix']).reshape(4,4)[3,:3]
            found = []
            for i in np.atleast_1d(tree.query(point[[0,2]],k=min(32,len(triangles)))[1]):
                triangle = horizontal[i]
                matrix = (triangle[1:]-triangle[0]).T
                if abs(np.linalg.det(matrix))<1e-8:
                    continue
                u,v = np.linalg.solve(matrix,point[[0,2]]-triangle[0])
                if min(u,v,1-u-v)>=-.002:
                    found.append(triangles[i,0,1]+u*(triangles[i,1,1]-triangles[i,0,1])+v*(triangles[i,2,1]-triangles[i,0,1]))
            require(found, f"no road triangle beneath {n['name']}")
            delta = point[1]-max(found)
            require(.5<=delta<=2.5, f"{n['name']} is {delta:.3f}m above road")
            offsets.append(delta)
        return f'road-triangle raycast offsets {min(offsets):.3f}..{max(offsets):.3f} m'
    check('empty_road_clearance', heights)
    def units():
        require(physical and len(triangles)>0, 'missing physical geometry')
        bounds = np.array([n['bounds'] for n in physical if not n['name'].startswith('1GRASS_LAND_')])
        extents = bounds[:,1].max(axis=0)-bounds[:,0].min(axis=0)
        require(np.isfinite(extents).all() and 6000<extents[0]<15000 and 2000<extents[2]<10000 and 280<extents[1]<450, f'implausible RN24 full/short physical bbox {extents}')
        sample = triangles[::max(1,len(triangles)//1000)]
        lengths = np.stack([np.linalg.norm((sample[:,a]-sample[:,b])[:,[0,2]],axis=1) for a,b in ((0,1),(1,2),(2,0))],axis=1)
        widths = np.sort(lengths,axis=1)[:,1]
        require(np.isfinite(widths).all() and widths.min()>=6 and widths.max()<=8, f'road widths {widths.min():.3f}..{widths.max():.3f}')
        return f'physical AC XYZ bbox {extents.round(2).tolist()} m; {len(widths)} road widths {widths.min():.3f}..{widths.max():.3f} m'
    check('units_scale_and_road_width', units)
    def limits():
        require(meshes and all(0<n['vertices']<=65536 for n in meshes), 'mesh vertex limit exceeded/empty')
        return f"{len(meshes)} meshes, max {max(n['vertices'] for n in meshes)} vertices"
    check('vertex_limits', limits)
    def textures():
        names = parsed.get('textures',[])
        require(0<len(names)<=64 and len(set(names))==len(names), 'missing/duplicate/excessive textures')
        for name,format_ in parsed['texture_formats'].items():
            require(format_ in ('PNG','DDS') and Path(name).suffix.lower()=='.'+format_.lower(), f'unsupported texture {name}: {format_}')
        return f'{len(names)} embedded PNG/DDS textures, signatures and references valid'
    check('textures', textures)
    def materials():
        entries=parsed.get('materials',[])
        require(entries,'no materials')
        slots={'ksPerPixel':['txDiffuse'],
               'ksPerPixelAT':['txDiffuse'],
               'ksPerPixelMultiMap':['txDiffuse','txNormal','txMaps','txDetail'],
               'ksMultilayer_fresnel_nm4':['txDiffuse','txMask']+[f'txDetail{c}' for c in 'RGBA']+[f'txNormal{c}' for c in 'RGBA']}
        for mat in entries:
            require(mat['shader'] in slots,f'unsupported/unreviewed shader {mat["shader"]}')
            expected=slots[mat['shader']]
            require(list(mat['textures'])==expected,f'incorrect named texture slots for {mat["name"]}')
            require(mat['texture_slots']=={k:i for i,k in enumerate(expected)},f'incorrect numeric slots for {mat["name"]}')
            flags=(2,True,0) if mat['shader']=='ksPerPixelAT' else (0,False,0)
            require((mat['blend'],mat['alpha_tested'],mat['depth'])==flags,f'unexpected transparency/depth for {mat["name"]}')
            require(mat['properties'] and all(np.isfinite(list(mat['properties'].values()))),f'invalid shader properties for {mat["name"]}')
        for mesh in meshes:
            if entries[mesh['material']]['shader']=='ksPerPixel':continue
            stats=mesh['tangent_stats']
            require(stats['finite'] and max(stats['normal_length_error'],stats['tangent_length_error'],stats['max_normal_dot_tangent'])<.001,f'invalid normal/tangent basis: {mesh["name"]}')
        ui_data=json.loads((folder/'ui/ui_track.json').read_text())
        if ui_data.get('version') in ('0.2','0.3','0.4'):
            recipe=json.loads((ROOT/'data/materials_info.json').read_text())
            actual={m['name']:m for m in entries}
            for name,spec in recipe['materials'].items():
                require(name in actual,f'missing material {name}')
                mat=actual[name]
                require(mat['shader']==spec['shaderName'] and mat['textures']=={k:v['textureName'] for k,v in spec['textures'].items()},f'material differs from recipe: {name}')
                require(mat['properties'].keys()==spec['properties'].keys(),f'property set differs from recipe: {name}')
                require(all(np.isclose(mat['properties'][k],v['valueA']) for k,v in spec['properties'].items()),f'property values differ from recipe: {name}')
            for name,expected in recipe['textures'].items():
                require(parsed['texture_info'].get(name,{}).get('sha256')==expected['sha256'],f'embedded DDS differs from generated recipe: {name}')
        return f'{len(entries)} materials; shader, ordered slots, properties and reviewed blend/depth flags valid'
    check('materials_and_shaders',materials)
    def dds_headers():
        info=parsed.get('texture_info',{})
        dds=[v for k,v in info.items() if parsed['texture_formats'][k]=='DDS']
        require(parsed.get('textures'),'missing textures')
        require(all(v['mips']==max(v['width'],v['height']).bit_length() for v in dds),'missing DDS mip levels')
        masks={m['textures']['txMask'] for m in parsed.get('materials',[]) if 'txMask' in m['textures']}
        for name in masks:
            require(mask_mip_error(parsed['texture_blobs'][name])<.15,f'blend weights lost in mip chain: {name}')
        return f'{len(dds)} DXT1/DXT5 headers/payloads and {len(masks)} mask mip weight means verified; compressed DDS bytes={sum(v["gpu_bytes"] for v in dds)}'
    check('dds_headers',dds_headers)
    def csp_config():
        config,references=config_materials((folder/'extension/ext_config.ini').read_text(encoding='utf-8'))
        names={m['name'] for m in parsed.get('materials',[])}
        require(references and references<=names,f'CSP references missing materials: {sorted(references-names)}')
        require({'GRASS_FX','RAIN_FX','INCLUDE: common/materials_track.ini','Material_Water'}<=set(config.sections()),'missing CSP sections/include')
        grass={n.strip() for n in config['GRASS_FX']['GRASS_MATERIALS'].split(',')}
        require(grass<=set(('grass','grass_mountain')),'GrassFX on non-terrain materials')
        require(config['Material_Water']['Type']=='SEA','unexpected water type')
        return f'{len(references)} exact KN5 material references; GrassFX/RainFX/water sections present'
    check('csp_config',csp_config)
    def sea_surface():
        entries=parsed.get('materials',[])
        water=[n for n in meshes if entries[n['material']]['name']=='water']
        require(water,'missing sea mesh/material')
        for mesh in water:
            p=mesh['positions'];tri=p[mesh['indices']]
            require(np.allclose(p[:,1],0,atol=.001),'sea not flat at datum zero')
            require(np.all(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])[:,1]>0),'sea winding not upward')
            require(mesh['uv_stats']['finite'] and min(mesh['uv_stats']['extent'])>0,'invalid sea UVs')
            extent=np.ptp(p,axis=0)
            require(1000<min(extent[[0,2]]) and max(extent)<60000,'unexpected sea dimensions')
        return f'{len(water)} flat upward sea mesh, finite nondegenerate UVs, coastal dimensions'
    check('sea_surface',sea_surface)
    def landscape():
        from landscape import edge_height
        land=[n for n in meshes if n['name'].startswith(('1GRASS_LAND_','LAND_'))]
        version=json.loads((folder/'ui/ui_track.json').read_text()).get('version')
        if not land:
            require(version not in ('0.3','0.4'),'missing v0.3+ landscape')
            return 'no landscape in historical package'
        require(all(n['lod_out']>=30000 for n in land),'landscape draw distance too short for horizon')
        road=shapely.union_all(shapely.polygons(triangles[:,:,[0,2]]))
        all_tri=np.concatenate([n['positions'][n['indices']] for n in land])
        require(len(all_tri)<600000,'terrain triangle budget exceeded')
        shapely.prepare(road);polygons=shapely.polygons(all_tri[:,:,[0,2]])
        hit=shapely.intersects(road,polygons)
        overlap=shapely.area(shapely.intersection(polygons[hit],road)).sum()
        require(overlap<.01,f'landscape overlaps road: {overlap:.6f} m2')
        visual=[n for n in land if n['name'].startswith('LAND_')]
        visual_tri=np.concatenate([n['positions'][n['indices']] for n in visual]) if visual else np.empty((0,3,3))
        band=road.buffer(145);shapely.prepare(band)
        require(not len(visual_tri) or not shapely.intersects(band,shapely.polygons(visual_tri[:,:,[0,2]])).any(),'visual-only terrain within physical corridor')
        ribbon=[n for n in meshes if n['name'].startswith(('1ROAD_','1KERB_','1GRAVEL_','1GRASS_')) and not n['name'].startswith('1GRASS_LAND_')]
        strip=np.concatenate([n['positions'][n['indices']] for n in ribbon])
        xyz,indices=np.unique(strip.reshape(-1,3),axis=0,return_inverse=True);indices=indices.reshape(-1,3)
        edges=np.sort(np.concatenate([indices[:,[0,1]],indices[:,[1,2]],indices[:,[2,0]]]),axis=1)
        edge_ids,count=np.unique(edges,axis=0,return_counts=True)
        border=xyz[edge_ids[count==1]]
        vertices=np.unique(all_tri.reshape(-1,3),axis=0)
        segments=border[:,:,[0,2,1]].copy();segments[:,:,1]*=-1
        xy=vertices[:,[0,2]].copy();xy[:,1]*=-1
        distance,edge_z=edge_height(xy,segments);near=distance<1.5
        clearance=edge_z-vertices[:,1]
        require(near.any() and clearance[near].min()>.008,f'landscape above ribbon join: {clearance[near].min() if near.any() else "none"}')
        return f'{len(all_tri)} triangles; physical/visual meshes={len(land)-len(visual)}/{len(visual)}; road overlap={overlap:.6f} m2; join clearance min={clearance[near].min():.3f} m'
    check('landscape_geometry',landscape)
    def vegetation():
        veg=[n for n in meshes if n['name'].startswith('DECOR_VEG_')]
        version=json.loads((folder/'ui/ui_track.json').read_text()).get('version')
        if not veg:
            config=configparser.ConfigParser();config.read(folder/'extension/ext_config.ini')
            if config.has_section('TREES'):
                from treefx import validate_model,validate_foliage_texture
                listing=folder/'extension'/config['TREES']['LIST_0']
                require(listing.is_file(),'missing external TreeFX list')
                lines=listing.read_text().splitlines();require(bool(lines),'empty TreeFX list')
                names=set();instances=[];angles=[]
                for line in lines:
                    parts=line.split(';');name=parts[0].removeprefix('tree: ').strip()
                    require(Path(name).name==name and name.endswith('.bin'),'unsafe external tree model name')
                    values=dict(p.strip().split('=',1) for p in parts[1:]);xyz=[float(v) for v in values['pos'].split(',')]
                    require(len(xyz)==3 and np.isfinite(xyz).all() and float(values['size'])>0,'invalid external tree transform')
                    require(np.isfinite([float(values['angle']),float(values['width']),*[float(v) for v in values['color'].split(',')]]).all(),'invalid external tree colour/rotation')
                    require(float(values['width'])==1,'unexpected external tree width')
                    names.add(name);instances.append((name,xyz,float(values['size'])));angles.append(np.radians(float(values['angle'])))
                metrics={name:validate_model(listing.parent/name,geometry=True) for name in names}
                require(all(len(lods)==2 for lods in metrics.values()),'external TreeFX LOD missing')
                radii={name:max(np.linalg.norm(lod['positions'][:,[0,2]],axis=1).max() for lod in lods) for name,lods in metrics.items()}
                road=shapely.union_all(shapely.polygons(triangles[:,:,[0,2]]))
                centers=np.asarray([xyz for _,xyz,_ in instances])[:,[0,2]]
                distances=shapely.distance(road,shapely.points(centers))
                clearance=distances-np.array([radii[name]*scale for name,_,scale in instances])
                outlines={name:shapely.get_coordinates(shapely.convex_hull(shapely.multipoints(np.concatenate([lod['positions'][:,[0,2]] for lod in lods])))) for name,lods in metrics.items() if name.startswith('maquis_')}
                for i,(name,xyz,scale) in enumerate(instances):
                    if name in outlines:clearance[i]=shapely.distance(road,footprint(outlines[name],np.asarray(xyz)[[0,2]],angles[i],scale))
                require(clearance.min()>3.999,'external canopy violates 4m road-edge clearance')
                require(not any(n['name'].endswith(('_pine_foliage','_olive_foliage','_maquis')) for n in meshes),'old foliage remains')
                total=sum(n['triangles'] for n in meshes)+sum(sum(lod['triangles'] for lod in metrics[name]) for name,_,_ in instances)
                require(sum(n['vertices'] for n in meshes)<=2000000,'KN5 exceeds 2M vertices')
                require(len(instances)<=8000,'TreeFX instance budget exceeded')
                require(distances.max()<=80.001,'TreeFX outside 80m corridor')
                require(config['GRASS_FX'].get('TEXTURE_GROUP_0_CHANCE')=='0.14','missing GrassFX replacement group')
                validate_foliage_texture((folder/'extension'/config['GRASS_FX']['TEXTURE']).read_bytes())
                return f'external TreeFX: {len(lines)} instances / {len(names)} models; {total} base+instantiated LOD triangles; clearance min={clearance.min():.3f} m; binary/alpha coverage valid; GrassFX tufts/scrub'
            require(version!='0.4','missing v0.4 vegetation')
            return 'no replacement foliage in historical package'
        require(sum(n['triangles'] for n in meshes)<1600000,'total vegetation/track triangle budget exceeded')
        require(not any(n['name'].endswith(('_pine_foliage','_olive_foliage','_maquis')) for n in meshes),'old block foliage remains')
        lod0=[n for n in veg if n['name'].startswith('DECOR_VEG_L0_')];lod1=[n for n in veg if n['name'].startswith('DECOR_VEG_L1_')]
        require(lod0 and lod1,'missing foliage LOD')
        require(all((n['lod_in'],n['lod_out'])==(0,150) for n in lod0),'wrong LOD0 range')
        require(all((n['lod_in'],n['lod_out'])==(150,600) for n in lod1),'wrong LOD1 range')
        require({n['name'].split('_')[3] for n in lod0}=={n['name'].split('_')[3] for n in lod1},'unpaired vegetation chunks')
        road=shapely.union_all(shapely.polygons(triangles[:,:,[0,2]])).buffer(4)
        shapely.prepare(road)
        faces=np.concatenate([n['positions'][n['indices']] for n in veg])
        require(not shapely.intersects(road,shapely.polygons(faces[:,:,[0,2]])).any(),'vegetation inside 4m road-edge clearance')
        cards=[m for m in parsed['materials'] if m['name'].startswith(('veg_canopy','veg_impostor'))]
        require(len(cards)==6 and all(m['shader']=='ksPerPixelAT' for m in cards),'missing cutout materials')
        from foliage import coverage_report
        for m in cards:
            name=m['textures']['txDiffuse'];t=parsed['texture_info'][name]
            require((t['width'],t['height'],t['mips'],t['format'])==(1024,1024,11,'DXT5'),'invalid foliage DDS')
            coverage=np.asarray(coverage_report(parsed['texture_blobs'][name]))
            require(np.max(abs(coverage[:7]-coverage[0]))<.13,'foliage alpha coverage lost in mips')
        return f'{len(lod0)} LOD0 / {len(lod1)} LOD1 meshes; six 1K BC3 atlases; alpha coverage verified'
    check('vegetation',vegetation)
    def roadside():
        detail=[n for n in meshes if n['name'].startswith('DETAIL_')]
        if not detail:return 'not built (optional roadside stage)'
        require(not any(n['name'].startswith('1') for n in detail),'roadside must be visual-only')
        faces=np.concatenate([n['positions'][n['indices']] for n in detail])
        road=shapely.union_all(shapely.polygons(triangles[:,:,[0,2]]))
        require(not shapely.intersects(road.buffer(1),shapely.polygons(faces[:,:,[0,2]])).any(),'roadside inside 1m road-edge clearance')
        require(all((n['lod_in'],n['lod_out'])==(0,1400) for n in detail),'wrong roadside LOD range')
        require(all(n['castShadows'] for n in detail if not n['name'].endswith('_roadside_litter')),'roadside shadow casting disabled')
        require(all(not n['castShadows'] for n in detail if n['name'].endswith('_roadside_litter')),'ground litter casts shadows')
        require(all(n['name'].startswith('DETAIL_') for n in detail),'physical roadside name')
        signs=[m for m in parsed['materials'] if m['name']=='roadside_signs']
        require(len(signs)==1 and signs[0]['shader']=='ksPerPixel','missing procedural sign material')
        info=parsed['texture_info'].get('roadside_signs.dds',{})
        require((info.get('width'),info.get('height'),info.get('mips'),info.get('format'))==(1024,1024,11,'DXT1'),'invalid procedural sign atlas')
        return f'{len(detail)} visual meshes / {sum(n["triangles"] for n in detail)} triangles; road clearance >=1m; 1K procedural signs'
    check('roadside',roadside)
    def map_image():
        ini = configparser.ConfigParser();ini.read(folder/'data/map.ini');params=ini['PARAMETERS']
        with Image.open(folder/'map.png') as im:
            require(im.size==(int(params['WIDTH']),int(params['HEIGHT'])), 'map image/INI dimensions differ')
            size=im.size
        for key in ('X_OFFSET','Z_OFFSET','SCALE_FACTOR','MARGIN','DRAWING_SIZE','MAX_SIZE'):
            require(np.isfinite(float(params[key])),f'invalid {key}')
        require(float(params['SCALE_FACTOR'])>0, 'invalid map scale')
        return f'{size[0]}x{size[1]}, finite offsets and positive scale'
    check('map_dimensions', map_image)
    print(f'VALIDATION_{"PASS" if all(results) else "FAIL"} checks={len(results)} passed={sum(results)}')
    return all(results)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',nargs='?',type=Path,default=ROOT/'out/bejaia_saket')
    raise SystemExit(0 if validate(parser.parse_args().folder) else 1)
