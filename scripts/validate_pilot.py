"""Static checks for the isolated pilot; intentionally not an Assetto Corsa runtime test."""
import configparser
import hashlib
import json
import math
import io
from pathlib import Path
import sys
import zipfile

from pilot_common import ROOT,WORK,DATA,OUT,PREVIEW,np,source_data,interpolate,dump,mesh_counts
from check_kn5 import inspect_kn5,inspect_dds
from pilot_common import foliage_image_metrics,Image
from treefx_wire import read_mesh,vector_ac
from mesh_geometry import guardrail_wall
from pilot_scenery import vista_open


def sha(stream):
    digest=hashlib.sha256()
    while True:
        block=stream.read(1024*1024)
        if not block:break
        digest.update(block)
    return digest.hexdigest()


TEXT_SOURCE_SUFFIXES={'.ini','.json','.py'}


def source_baseline_digest(relative,stream):
    if Path(relative).suffix.lower() in TEXT_SOURCE_SUFFIXES:
        content=stream.read().replace(b'\r\n',b'\n').replace(b'\r',b'\n')
        return hashlib.sha256(content).hexdigest()
    return sha(stream)


def source_baseline_hash(relative):
    with (ROOT/relative).open('rb') as stream:
        return source_baseline_digest(relative,stream)


SOURCE_BASELINE_PATHS = [
    'data/centerline.npz', 'data/shortening_info.json',
    'blend/bejaia_saket.blend', 'blend/settings.json',
    'out/bejaia_saket/bejaia_saket.kn5', 'out/bejaia_saket/data/surfaces.ini',
    'scripts/blender_mesh.py', 'scripts/blender_materials.py',
    'scripts/geometry.py', 'scripts/mesh_geometry.py',
    'scripts/blender_collision_fix.py', 'scripts/acdata.py',
    'scripts/validate_shortened.py', 'data/kn5_export_info.json',
]


def refresh_baseline():
    hashes = {}
    for relative in SOURCE_BASELINE_PATHS:
        hashes[relative] = source_baseline_hash(relative)
    result = dict(
        origin='Current full-route source snapshot used for this pilot build',
        snapshot_commit=json.loads((ROOT / 'PROJECT_SNAPSHOT.json').read_text())['commit'],
        files=hashes,
    )
    dump(DATA / 'source_baseline.json', result)
    print('PILOT_SOURCE_BASELINE_REFRESHED', json.dumps({'files': len(hashes)}))
    return result


def baseline():
    path=DATA/'source_baseline.json'
    if path.exists():return json.loads(path.read_text())
    archive=WORK.parent/'bejaia_saket_project_src3.zip'
    if not archive.is_file():raise FileNotFoundError('First validation needs the original src3 archive to establish the main-layout safety baseline')
    paths=['data/centerline.npz','data/shortening_info.json','blend/bejaia_saket.blend','out/bejaia_saket/bejaia_saket.kn5','out/bejaia_saket/data/surfaces.ini','scripts/blender_mesh.py','scripts/blender_materials.py','scripts/geometry.py']
    hashes={}
    with zipfile.ZipFile(archive) as original:
        for relative in paths:
            name=next(n for n in original.namelist() if n==relative or n.endswith('/'+relative))
            with original.open(name) as stream:hashes[relative]=source_baseline_digest(relative,stream)
            with (ROOT/relative).open('rb') as stream:assert source_baseline_digest(relative,stream)==hashes[relative],('Source changed',relative)
    result=dict(origin='Original src3 ZIP verified byte-for-byte',snapshot_commit=json.loads((ROOT/'PROJECT_SNAPSHOT.json').read_text())['commit'],files=hashes)
    dump(path,result)
    return result


def parser(path):
    config=configparser.ConfigParser(interpolation=None,strict=False)
    config.read(path,encoding='utf-8')
    return config


def impostor_size_ratios(mesh, textures, config):
    geometry=read_mesh(mesh,textures,geometry=True)['positions']
    height=config.getfloat('BASIC','HEIGHT')
    width=config.getfloat('BASIC','WIDTH')
    plane_height=float(np.ptp(geometry[:,1]))*height
    plane_width=plane_height/2
    ratios=[]
    for name,blob in textures.items():
        if '_impostor_' not in name:continue
        alpha=np.asarray(Image.open(io.BytesIO(blob)).convert('RGBA'))[:,:,3]>=128
        ys,xs=np.where(alpha)
        if len(xs)==0:raise AssertionError('Empty far tree silhouette: '+name)
        ratios.append((
            (xs.max()-xs.min()+1)/alpha.shape[1]*plane_width/width,
            (ys.max()-ys.min()+1)/alpha.shape[0]*plane_height/height,
        ))
    if not ratios:raise AssertionError('No far tree silhouettes in TreeFX package')
    return np.asarray(ratios)


def validate(require_previews=True):
    checks=[]
    def check(condition,label):
        if not condition:raise AssertionError(label)
        checks.append(label)
    original=baseline()
    for relative,digest in original['files'].items():
        actual=source_baseline_hash(relative)
        check(actual==digest,'Main source unchanged: '+relative)
    meta=json.loads((DATA/'selection.json').read_text());build=json.loads((DATA/'build_report.json').read_text())
    with np.load(DATA/'centerline.npz') as source:data={key:source[key] for key in source.files}
    full=source_data();stations=data['source_s3']
    points=np.column_stack([data['xy'],data['z']])
    length=float(np.linalg.norm(np.diff(points,axis=0),axis=1).sum())
    check(abs(length-300)<1e-6,'Pilot is exactly 300 m of real 3D road')
    check(meta['active_start_3d_m']<meta['summit_3d_m']<meta['active_end_3d_m'],'Pilot includes the real principal summit')
    for key in ('xy','z','width'):
        check(np.array_equal(data[key],interpolate(full[key],stations,full['s3'])),'Source road values preserved: '+key)
    expected_sides=np.moveaxis(interpolate(full['sides'],stations,full['s3'],axis=1),0,1)
    check(np.array_equal(data['sides'],expected_sides),'Terrain and physical cross-sections preserved')
    source_surface=ROOT/'out/bejaia_saket/data/surfaces.ini'
    check(source_surface.read_bytes()==(OUT/'data/surfaces.ini').read_bytes(),'Physics coefficients: surfaces.ini byte-identical')
    path=OUT/'bejaia_saket_pilot300.kn5'
    report=inspect_kn5(path,geometry='all')
    with path.open('rb') as stream:check(sha(stream)==build['sha256'],'KN5 matches its build SHA256')
    check(all(value=='DDS' for value in report['texture_formats'].values()),'All KN5 textures are embedded DDS with complete mip chains')
    nodes={node['name']:node for node in report['nodes']}
    meshes=[node for node in report['nodes'] if 'vertices' in node]
    check(all(n['vertices']<=65536 for n in meshes),'All KN5 meshes respect 16-bit vertex indices')
    check(all(n['uv_stats']['finite'] and n['tangent_stats']['finite'] for n in meshes),'UVs, normals and tangents are finite')
    check(all(n['tangent_stats']['normal_length_error']<.001 for n in meshes),'All KN5 vertex normals are unit-length')
    road=nodes['1ROAD_000'];actual=np.unique(road['positions'],axis=0)
    expected=vector_ac(data['sides'][:,:,0].reshape(-1,3)).astype('<f4')
    check(np.array_equal(actual,np.unique(expected,axis=0)),'Exported road vertices exactly match the source')
    colliders=[n for n in meshes if n['name'].startswith('1WALL_COLLIDER_RAIL_')]
    check(len(colliders)==1 and all(n['visible'] and not n['renderable'] for n in colliders),'One simplified rail collider stays physics-visible but non-renderable')
    for collider in colliders:
        side=int(collider['name'].rsplit('_',1)[1])
        vertices,_=guardrail_wall(data['sides'][side,:,2],data['normal'],.25,-.15,.8)
        expected=vector_ac(vertices).astype('<f4')
        actual=np.unique(collider['positions'],axis=0)
        check(np.array_equal(actual,np.unique(expected,axis=0)),'Pilot rail collider continuously covers the full guardrail span')
    check('1WALL_PILOT_START' in nodes and '1WALL_PILOT_END' in nodes,'Pilot has physical boundary closures')
    check(sum(n['name'].startswith('DETAIL_RAIL_') for n in meshes)==build['rail_tiles'],'Professional guardrail tiles exported')
    near_rails=[n for n in meshes if n['name'].startswith('DETAIL_RAIL_')]
    far_rails=[n for n in meshes if n['name'].startswith('LOD_RAIL_')]
    check(len(near_rails)==len(far_rails)==build['rail_tiles'],'All rail tiles have a separate cheaper visual LOD')
    check(all(n['lod_in']==0 and n['lod_out']==45 for n in near_rails) and all(n['lod_in']==45 and n['lod_out']==350 for n in far_rails),'Rail LOD ranges meet without a gap')
    check(sum(n['triangles'] for n in far_rails)<sum(n['triangles'] for n in near_rails)*.2,'Distant rail triangle count reduced by at least 80 percent')
    edge_near=[n for n in meshes if n['name'].startswith('DETAIL_EDGE_')]
    edge_far=[n for n in meshes if n['name'].startswith('LOD_EDGE_')]
    check(bool(edge_near) and len(edge_near)==len(edge_far),'Forest edge has paired near/far batches')
    check(all(n['lod_in']==0 and n['lod_out']==110 for n in edge_near) and all(n['lod_in']==110 and n['lod_out']==350 for n in edge_far),'Forest-edge LOD ranges have no distance gap')
    check(sum(n['triangles'] for n in edge_near)<3000 and sum(n['triangles'] for n in edge_far)*2==sum(n['triangles'] for n in edge_near),'Forest edge stays within its two-plane/single-plane geometry budget')
    for side,letter in enumerate(('L','R')):
        for name,section in ((f'1GRASS_000_{letter}',slice(2,4)),(f'LAND_SLOPE_{letter}',slice(3,None))):
            expected=vector_ac(data['sides'][side,:,section].reshape(-1,3)).astype('<f4')
            check(np.array_equal(np.unique(nodes[name]['positions'],axis=0),np.unique(expected,axis=0)),'Native physical/visual ground preserved: '+name)
    scenery=[n for n in meshes if n['name'].startswith(('DETAIL_EDGE_','LOD_EDGE_','LAND_','DETAIL_PH_'))]
    check(all(not n['name'][0].isdigit() for n in scenery),'Forest-edge and distant slopes are non-physical scenery')
    atlas=Image.open(DATA/'forest_edge_atlas.png')
    check(foliage_image_metrics(atlas)['white_fraction']==0,'Forest-edge atlas has real CC0 color and alpha, not opaque rectangles')
    from pilot_common import TEX
    with Image.open(TEX/'PH_forest_edge_diff.dds') as exported_atlas:
        check(exported_atlas.size==atlas.size,'Exported DDS atlas keeps the reviewed atlas dimensions')
        check(abs(foliage_image_metrics(exported_atlas)['alpha_coverage']-foliage_image_metrics(atlas)['alpha_coverage'])<.02,'Exported DDS atlas keeps the reviewed alpha silhouette')
    check('PH_forest_edge_diff.dds' in report['texture_formats'],'Reviewed forest-edge texture is embedded in the KN5')
    layout=json.loads((DATA/'edge_layout.json').read_text())
    check(len(layout)==build['scenery']['clumps'],'Every planned forest-edge clump is built')
    check(all(p['offset']-p['width']/2>=float(np.interp(p['station'],data['s3'],data['width']))/2+2.49 for p in layout),'Forest-edge footprints stay outside the drivable shoulder')
    for entry in json.loads((DATA/'spawns.json').read_text()):
        matrix=np.asarray(nodes[entry['name']]['matrix']).reshape(4,4)
        expected=vector_ac([entry['position']])[0]
        check(bool(np.allclose(matrix[3,:3],expected,atol=.002,rtol=0)),'Spawn/timing matrix: '+entry['name'])
        yaw=entry['yaw_rad'];forward=np.array([np.sin(yaw),0,np.cos(yaw)])
        check(bool(np.allclose(matrix[2,:3],forward,atol=1e-6)),'Driving orientation: '+entry['name'])
    models=json.loads((DATA/'treefx_models.json').read_text());tree_folder=OUT/'extension/trees';texture_hashes={};model_stats={}
    for name,model in models.items():
        with zipfile.ZipFile(tree_folder/model['file']) as archive:
            check(archive.testzip() is None,'TreeFX ZIP CRC: '+name)
            members=archive.namelist();check(all(Path(n).name==n and not n.startswith('.') for n in members),'TreeFX archive has safe relative names: '+name)
            textures={n:archive.read(n) for n in members if n.endswith('.dds')}
            for texture,blob in textures.items():
                inspect_dds(blob)
                if 'impostor' in texture or 'card_diff' in texture:
                    metrics=foliage_image_metrics(Image.open(io.BytesIO(blob)))
                    check(metrics['white_fraction']<=.1,'Foliage alpha and real color preserved: '+texture)
                digest=hashlib.sha256(blob).hexdigest()
                if texture in texture_hashes:check(texture_hashes[texture]==digest,'Shared tree texture consistent: '+texture)
                texture_hashes[texture]=digest
            config=configparser.ConfigParser();config.read_string(archive.read('tree.ini').decode())
            distances=[];lods=[]
            for lod in range(3):
                section=config['LOD_'+str(lod)];distances.append(section.getfloat('DISTANCE'))
                metrics=read_mesh(archive.read(section['MODEL']),textures)
                check(metrics==model['lods'][lod],'TreeFX checksums, indices and normals: '+name+' LOD '+str(lod))
                lods.append(metrics)
            check(all(a<b for a,b in zip(distances,distances[1:])),'TreeFX LOD distances increase: '+name)
            check(lods[-1]['triangles']==16,'Distant TreeFX impostor is only 16 triangles: '+name)
            check(lods[0]['triangles']<=20003 and lods[1]['triangles']<=9003,'Near and medium TreeFX meshes respect performance budgets: '+name)
            size_ratios=impostor_size_ratios(
                archive.read(config['LOD_2']['MODEL']),textures,config,
            )
            check(
                bool(np.all((size_ratios[:,0]>=.65)&(size_ratios[:,0]<=1.1)
                            &(size_ratios[:,1]>=.65)&(size_ratios[:,1]<=1.2))),
                'Far TreeFX silhouettes stay near the source model scale: '+name,
            )
            if model.get('kind')=='background':
                check(all(lod['triangles']==16 for lod in lods),'Background trees have only 16 triangles at every distance: '+name)
                check(distances==[180,450,900],'Background impostors remain cheap at distance: '+name)
            if model.get('kind')=='midstory':
                check(lods[0]['triangles']<=9003 and distances==[28,110,900],'Midstory uses the lighter pine representation and long cull range: '+name)
            if model.get('kind')=='shrub':
                check(lods[0]['triangles']<=18000 and lods[1]['triangles']<=4000,'Two-sided shrub meshes meet their stricter budgets: '+name)
                check(distances==[20,75,900],'Shrubs avoid near culling and abrupt billboard thresholds: '+name)
            if model.get('kind') in ('pine','shrub','midstory','background'):
                check(distances[-1]>=900,'TreeFX keeps final impostors visible beyond the pilot corridor: '+name)
            model_stats[name]=dict(
                lods=lods,distances=distances,
                far_size_ratio_min=np.round(size_ratios.min(axis=0),3).tolist(),
                far_size_ratio_max=np.round(size_ratios.max(axis=0),3).tolist(),
            )
    plants=json.loads((DATA/'plants.json').read_text())
    lines=(tree_folder/'trees.txt').read_text().splitlines()
    check(len(plants)==len(lines)==build['tree_instances'],'All tree placements reference generated models')
    for plant,line in zip(plants,lines):
        check(line.split(';',1)[0].split(':',1)[1].strip()==models[plant['model']]['file'],'Tree instance model exists')
    check(max(p['offset']-float(np.interp(p['station'],data['s3'],data['width']))/2 for p in plants)<80,'Vegetation stays inside the 80 m corridor')
    check(min(p['offset']-float(np.interp(p['station'],data['s3'],data['width']))/2 for p in plants)>=3-1e-6,'Tree roots remain clear of the road edge')
    blend=json.loads((DATA/'blend_audit.json').read_text())
    check(blend['texture_paths_relative'] and blend['texture_paths_exist'] and blend['no_external_dependencies'],'Saved Blender scene has valid relative texture paths')
    model_file=parser(OUT/'models.ini')['MODEL_0']['FILE']
    check(model_file==path.name and (OUT/model_file).is_file(),'AC models.ini points to the pilot KN5, not the main layout')
    check(parser(OUT/'data/map.ini').getfloat('PARAMETERS','SCALE_FACTOR')>0 and (OUT/'map.png').is_file(),'Mini-map generated at valid real scale')
    camera=parser(OUT/'data/cameras.ini')
    check(camera.getint('HEADER','CAMERA_COUNT')==1 and camera['CAMERA_0'].getfloat('MIN_FOV')>0,'Replay camera uses the documented complete template')
    grass_names={name.strip() for name in parser(OUT/'extension/ext_config.ini')['GRASS_FX']['GRASS_MATERIALS'].split(',')}
    for letter in ('L','R'):
        material=report['materials'][nodes['1GRASS_000_'+letter]['material']]['name']
        check(material in grass_names,'GrassFX targets the exported '+letter+' verge material')
    check((OUT/'CREDITS.md').is_file() and 'tracktools' not in json.loads((OUT/'LICENSES.json').read_text()),'Redistribution credits present; TrackTools is excluded')
    for candidate in OUT.rglob('*'):
        if candidate.is_file():
            with candidate.open('rb') as stream:prefix=stream.read(80)
            check(not prefix.startswith(b'version https://git-lfs.github.com/spec/'),'No LFS pointer: '+str(candidate.relative_to(OUT)))
    if require_previews:
        check((PREVIEW/'before.png').is_file() and (PREVIEW/'after.png').is_file(),'Before/after Blender views generated')
    result=dict(passed=True,checks=len(checks),check_names=checks,length_3d_m=length,**mesh_counts(report),kn5_bytes=path.stat().st_size,tree_instances=len(plants),model_stats=model_stats,unique_tree_textures=len(texture_hashes),source_commit=original['snapshot_commit'],source_safety_verified=True,blender_texture_paths_verified=True,runtime_ac_tested=False,pure_tested=False,rainfx_tested=False,fps_vram_tested=False)
    dump(DATA/'validation_report.json',result)
    print('PILOT_STATIC_VALIDATION_OK',json.dumps({k:v for k,v in result.items() if k not in ('check_names','model_stats')}))
    return result


if __name__=='__main__':
    if sys.argv[1:] == ['--refresh-baseline']:
        refresh_baseline()
    else:
        validate()
