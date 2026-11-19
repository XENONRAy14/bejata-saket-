"""Build a separate 300 m summit test track; never alter the main layout or AC install."""
from pathlib import Path
import copy
import hashlib
import json
import math
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from pilot_common import *
import bpy
from mathutils import Vector
import blender_assetto_corsa_tools as addon
addon.register()
from blender_assetto_corsa_tools import exporter
from blender_mesh import strip,object_mesh,add_box,camera,collision_uvs
from mesh_geometry import guardrail_wall
from blender_materials import material_nodes,apply
from check_kn5 import inspect_kn5
from pilot_treefx import compile_models, impostors
from pilot_shrubs import load_shrubs
from pilot_scenery import edge_layout, forest_edge_atlas, vista_open
from scenery_placement import edge_batches, pilot_tree_layout, plan_sector, RoadClearance, sea_sides, load_zones, zone_contains


def shade_foliage(material):
    if material.get('_pilot_translucent'):return
    nodes=material.node_tree.nodes;links=material.node_tree.links
    principal=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL')
    color=principal.inputs['Base Color'].links[0].from_socket
    alpha=principal.inputs['Alpha'].links[0].from_socket
    links.remove(principal.inputs['Alpha'].links[0]);principal.inputs['Alpha'].default_value=1
    translucent=nodes.new('ShaderNodeBsdfTranslucent');links.new(color,translucent.inputs['Color'])
    mix=nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.35
    links.new(principal.outputs[0],mix.inputs[1]);links.new(translucent.outputs[0],mix.inputs[2])
    opacity=nodes.new('ShaderNodeMixShader');transparent=nodes.new('ShaderNodeBsdfTransparent')
    links.new(alpha,opacity.inputs[0]);links.new(transparent.outputs[0],opacity.inputs[1]);links.new(mix.outputs[0],opacity.inputs[2]);links.new(opacity.outputs[0],output.inputs[0])
    material['_pilot_translucent']=True


def clean_unused():
    for mesh in list(bpy.data.meshes):
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    for material in list(bpy.data.materials):
        if material.users==0:bpy.data.materials.remove(material)
    for image in list(bpy.data.images):
        if image.users==0:bpy.data.images.remove(image)


def backdrop(data):
    landscape=np.load(ROOT/'data/landscape.npz')
    vertices=landscape['vertices'];faces=landscape['faces'];keys=landscape['keys']
    center=data['xy'].mean(axis=0)
    selected=np.linalg.norm(vertices[faces].mean(axis=1)[:,:2]-center,axis=1)<1200
    for group,key in enumerate(np.unique(keys[selected],axis=0)):
        chosen=faces[selected&np.all(keys==key,axis=1)]
        indices,inverse=np.unique(chosen,return_inverse=True)
        material=bpy.data.materials['landcover']
        obj=object_mesh(f'LAND_PILOT_{group:04d}',vertices[indices],inverse.reshape(-1,3).tolist(),material)
        for poly in obj.data.polygons:poly.use_smooth=True
    object_mesh('DECOR_SEA',landscape['sea_vertices'],landscape['sea_faces'].tolist(),bpy.data.materials['water'])


def add_empties(data):
    entries=[]
    def place(name,station,lateral=0):
        point,tangent,left=frame(data,station);point+=left*lateral;point[2]+=1.5
        yaw=math.atan2(tangent[0],-tangent[1])
        obj=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(obj)
        obj.location=point;obj.rotation_euler=(0,0,yaw);obj.empty_display_type='ARROWS'
        entries.append(dict(name=name,station_m=station,position=list(point),yaw_rad=yaw))
    for name in ('AC_START_0','AC_PIT_0','AC_HOTLAP_START_0'):place(name,12)
    for name,station in [('AC_AB_START',15),('AC_TIME_0',103),('AC_TIME_1',191),('AC_AB_FINISH',280)]:
        width=float(np.interp(station,data['s3'],data['width']))
        for letter,sign in [('L',1),('R',-1)]:place(name+'_'+letter,station,sign*width/2)
    dump(DATA/'spawns.json',entries)


def guardrail_source(info):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(ASSETS/'guard-rail.glb'))
    objects=[o for o in bpy.data.objects if o not in before]
    body=next(o for o in objects if o.type=='MESH')
    material=body.data.materials[0]
    images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    base=next(i for i in images if 'basecolor' in i.name.lower())
    normal=next(i for i in images if 'normal' in i.name.lower())
    combined=next(i for i in images if 'metallic' in i.name.lower())
    rough=DATA/'guard_roughness.png';image_pixels(combined,'RGB').getchannel('G').save(rough)
    info['materials'][material.name]=pbr_material(material.name,base,normal,rough,metal=True)
    points=np.asarray([tuple(body.matrix_world@v.co) for v in body.data.vertices])
    faces=[tuple(p.vertices) for p in body.data.polygons]
    uv=[tuple(d.uv) for d in body.data.uv_layers.active.data]
    dimensions=np.ptp(points,axis=0)
    assert np.allclose(dimensions,[4,.30035,.753915],atol=.003),dimensions
    for obj in objects:bpy.data.objects.remove(obj,do_unlink=True)
    return points,faces,uv,material.name


def rails(data,source,sea_side):
    points,faces,uv,material_name=source
    material=bpy.data.materials[material_name]
    instances=0
    for side in (sea_side,):
        for center in np.arange(2,300,4):
            origin,tangent,left=frame(data,float(center))
            edge=interpolate(data['sides'][side,:,2],center,data['s3'])
            orientation=1 if np.dot(edge[:2]-origin[:2],left[:2])>0 else -1
            transformed=[]
            for x,y,z in points:
                station=float(np.clip(center+orientation*x,0,300))
                p,t,l=frame(data,station)
                edge=interpolate(data['sides'][side,:,2],station,data['s3'])
                transformed.append(edge+orientation*l*y+np.array([0,0,z]))
            obj=object_mesh(f'DETAIL_RAIL_{instances:03d}',transformed,faces,material)
            for target,value in zip(obj.data.uv_layers.active.data,uv):target.uv=value
            for poly in obj.data.polygons:poly.use_smooth=True
            distant=bpy.data.objects.new(f'LOD_RAIL_{instances:03d}',obj.data.copy())
            bpy.context.collection.objects.link(distant)
            decimate=distant.modifiers.new('Distant rail geometry budget','DECIMATE')
            decimate.ratio=.12;decimate.use_collapse_triangulate=True
            dg=bpy.context.evaluated_depsgraph_get()
            reduced=bpy.data.meshes.new_from_object(distant.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
            distant.modifiers.clear();distant.data=reduced
            instances+=1
        vertices,polygons=guardrail_wall(data['sides'][side,:,2],data['normal'],.25,-.15,.8)
        collider=object_mesh(f'1WALL_COLLIDER_RAIL_{side}',vertices,polygons,material)
        collider.hide_render=True
        collision_uvs(collider)
    return instances


def terrain_detail(data,prototypes,info,mountain_side):
    rock=next(o for o in prototypes if 'rock_moss' in o.name)
    fern=next(o for o in prototypes if 'fern_' in o.name)
    rng=np.random.default_rng(24024)
    for i,station in enumerate(np.arange(12,294,11.5)):
        for original,target_height,extra in ((rock,float(rng.uniform(.45,1.1)),float(rng.uniform(3,6))),(fern,float(rng.uniform(.4,.85)),float(rng.uniform(2.3,4.5)))):
            extent=max(v.co.z for v in original.data.vertices)-min(v.co.z for v in original.data.vertices)
            scale=target_height/max(extent,.01)
            width=float(np.interp(station,data['s3'],data['width']))
            position=ground(data,float(station),mountain_side,width/2+extra)
            position[2]-=.08
            angle=float(rng.uniform(0,2*np.pi));c,s=math.cos(angle),math.sin(angle)
            transform=np.array([[c,-s,0],[s,c,0],[0,0,1]])*scale
            coords=[position+transform@np.asarray(v.co) for v in original.data.vertices]
            mesh=original.data.copy()
            for vertex,point in zip(mesh.vertices,coords):vertex.co=point
            obj=bpy.data.objects.new(f'DETAIL_PH_{original.name}_{i:03d}',mesh);bpy.context.collection.objects.link(obj)
    stations=np.arange(55,177,2)
    points=interpolate(data['sides'][mountain_side,:,2],stations,data['s3'])
    normals=interpolate(data['normal'],stations,data['s3'])
    vertices,faces=guardrail_wall(points,normals,.4,-.2,1.3)
    wall=object_mesh('1WALL_PILOT_RETAINING',vertices,faces,bpy.data.materials['kerb'])
    # A low wall, not a new mountain: the original Copernicus terrain is untouched.
    return wall


def forest_edges(data, info, sea_side=None,*,cache_dir=DATA,texture_dir=TEX,s0=None,s1=None,zones=None):
    cache_dir=Path(cache_dir);cache_dir.mkdir(parents=True,exist_ok=True)
    pilot=s0 is None and s1 is None and sea_side is not None
    profile=load_zones()['pilot' if pilot else 'main'] if zones is None else zones
    atlas, atlas_metrics = forest_edge_atlas(cache_dir=cache_dir)
    spec = pbr_material('forest_edge', atlas, foliage=True,texture_dir=texture_dir)
    spec['textures'] = {'txDiffuse': spec['textures']['txDiffuse']}
    spec['alphaBlendMode'] = 'Opaque'
    spec['properties']['ksSpecular']['valueA'] = 0
    info['materials']['forest_edge'] = spec
    material = bpy.data.materials.new('forest_edge')
    preview=copy.deepcopy(spec)
    for entry in preview['textures'].values():entry['textureName']=str(Path(texture_dir).resolve()/entry['textureName'])
    material_nodes(material, preview)
    shade_foliage(material)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
    surface = output.inputs['Surface'].links[0].from_socket
    geometry = nodes.new('ShaderNodeNewGeometry')
    backface = nodes.new('ShaderNodeMixShader')
    transparent = nodes.new('ShaderNodeBsdfTransparent')
    links.new(geometry.outputs['Backfacing'], backface.inputs[0])
    links.new(surface, backface.inputs[1])
    links.new(transparent.outputs[0], backface.inputs[2])
    links.new(backface.outputs[0], output.inputs['Surface'])
    if pilot:
        layout = edge_layout(data,sea_side,zones=profile)
    else:
        layout = edge_layout(data,sea_side,s0=s0,s1=s1,zones=profile)
        road=RoadClearance(data);sea=sea_sides(data,profile.get('side_smoothing_m',30))
        layout=[p for p in layout if road.allows(p['position'],p['width']/2,profile.get('road_clearance_m',4))
                and not zone_contains(p['station'],p['side'],sea(p['station']),profile,'exclusions','edge',p['width']/2)]
    totals = {}
    for distant in (False, True):
        groups = edge_batches(data,layout,distant=distant)
        prefix = 'LOD_EDGE' if distant else 'DETAIL_EDGE'
        triangles = 0
        for (chunk, side), (vertices, faces, uvs, normals) in groups.items():
            obj = object_mesh(f'{prefix}_{chunk:03d}_{side}', vertices, faces, material)
            for loop in obj.data.loops:
                obj.data.uv_layers.active.data[loop.index].uv = uvs[loop.vertex_index]
            obj.data.use_auto_smooth = True
            obj.data.normals_split_custom_set_from_vertices(normals)
            triangles += len(faces) * 2
        totals['far' if distant else 'near'] = dict(meshes=len(groups), triangles=triangles)
    result = dict(atlas=atlas_metrics, clumps=len(layout), lods=totals,
                  native_slope_preserved=True, physical_ground_limit_m_from_center=13.3,
                  vista_openings=profile['vista_openings'], ac_runtime_verified=False)
    dump(cache_dir/'edge_layout.json', layout)
    dump(cache_dir/'scenery_report.json', result)
    return result


def scatter_trees(data,models,sea_side=None,*,output_dir=OUT,cache_dir=DATA,s0=None,s1=None,zones=None):
    output_dir=Path(output_dir);cache_dir=Path(cache_dir)
    (output_dir/'extension/trees').mkdir(parents=True,exist_ok=True);cache_dir.mkdir(parents=True,exist_ok=True)
    if s0 is None and s1 is None and sea_side is not None:
        plants=pilot_tree_layout(data,models,sea_side,zones=zones)
    else:
        plants=plan_sector(data,models,s0,s1,zones=zones)['trees']
    lines=[]
    for plant in plants:
        x,y,z=plant['position'];angle=-math.degrees(plant['angle'])
        lines.append(f"tree: {models[plant['model']]['file']}; pos={x:.9g}, {z:.9g}, {-y:.9g}; angle={angle:.9g}; size={plant['scale']:.9g}; width={plant['width']:.9g}; color=1, 1, 1")
    (output_dir/'extension/trees/trees.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    dump(cache_dir/'plants.json',plants)
    return plants


def package_metadata(data,meta,guard_material):
    for folder in ('data','ui','extension/trees'):(OUT/folder).mkdir(parents=True,exist_ok=True)
    original=ROOT/'out/bejaia_saket/data/surfaces.ini'
    shutil.copy2(original,OUT/'data/surfaces.ini')
    assert original.read_bytes()==(OUT/'data/surfaces.ini').read_bytes()
    meta['surfaces_sha256']=hashlib.sha256(original.read_bytes()).hexdigest()
    (OUT/'models.ini').write_text('[MODEL_0]\nFILE=bejaia_saket_pilot300.kn5\nPOSITION=0,0,0\nROTATION=0,0,0\n')
    ui=dict(name='Bejaia - Saket / Pilote sommet 300 m',description='Prototype graphique isole de 300 m. Pins sylvestres Poly Haven CC0, glissiere Grab3D CC0, asphalte Poly Haven CC0. PAS le circuit principal. Essai AC requis.',tags=['road','point-to-point','pilot'],country='Algeria',city='Bejaia',author='Project contributors',version='pilot-0.4-treefx-lod',length='300 m',width='7 m',pitboxes='1',run='point-to-point')
    dump(OUT/'ui/ui_track.json',ui)
    xy=data['xy']*np.array([1,-1]);lower=xy.min(axis=0);span=np.ptp(xy,axis=0);scale=float(max(span)/472);offset=20*scale-lower
    size=np.ceil(span/scale+40).astype(int);pixels=(xy+offset)/scale
    image=Image.new('RGBA',tuple(size),(0,0,0,0));draw=ImageDraw.Draw(image);draw.line([tuple(p) for p in pixels],fill='white',width=10)
    image.save(OUT/'map.png');image.thumbnail((256,256));image.save(OUT/'ui/outline.png')
    ini=dict(WIDTH=int(size[0]),HEIGHT=int(size[1]),MARGIN=0,SCALE_FACTOR=scale,MAX_SIZE=512,X_OFFSET=float(offset[0]),Z_OFFSET=float(offset[1]),DRAWING_SIZE=10)
    (OUT/'data/map.ini').write_text('[PARAMETERS]\n'+''.join(f'{key}={value}\n' for key,value in ini.items()))
    config=pilot_csp_config((ROOT/'out/bejaia_saket/extension/ext_config.ini').read_text(encoding='utf-8'),guard_material)
    (OUT/'extension/ext_config.ini').write_text(config,encoding='utf-8')
    shutil.copy2(ROOT/'out/bejaia_saket/extension/trees/grass.dds',OUT/'extension/trees/grass.dds')
    p,t,_=frame(data,150);p[2]+=6;forward=np.array([t[0],-.3,t[1]])
    position=f'{p[0]},{p[2]},{-p[1]}'
    (OUT/'data/cameras.ini').write_text('[HEADER]\nVERSION=3\nCAMERA_COUNT=1\nSET_NAME=Pilote\n[CAMERA_0]\nNAME=Summit\nPOSITION='+position+'\nUP=0,1,0\nFORWARD='+f'{t[0]},-0.1,{-t[1]}'+'\nMIN_FOV=50\nMAX_FOV=50\nIN_POINT=0\nOUT_POINT=1\nSHADOW_SPLIT0=120\nSHADOW_SPLIT1=250\nSHADOW_SPLIT2=600\nNEAR_PLANE=0.1\nFAR_PLANE=3000\nMIN_EXPOSURE=0.35\nMAX_EXPOSURE=0.55\nDOF_FACTOR=0\nDOF_RANGE=10000\nDOF_FOCUS=0\nDOF_MANUAL=0\nSPLINE=\nSPLINE_ROTATION=0\nFOV_GAMMA=1\nSPLINE_ANIMATION_LENGTH=15\nIS_FIXED=0\n')
    licenses=json.loads((WORK/'asset_licenses.json').read_text());licenses.pop('tracktools',None)
    licenses['project_base']=dict(credits='CREDITS.md',osm='https://www.openstreetmap.org/copyright',copernicus='https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model')
    dump(OUT/'LICENSES.json',licenses)
    credits=(ROOT/'out/bejaia_saket/CREDITS.md').read_text(encoding='utf-8')
    intro='# Pilote graphique 300 m : nouveaux credits\n\nPins sylvestres, jeune pin, fougeres et rocher : Poly Haven Pine Forest, CC0-1.0. Geometrie de rameaux originale cuite en cartes alpha par ce projet. Asphalte Worn Asphalt : Poly Haven, CC0-1.0. Glissiere : Grab3D guard-rail, CC0-1.0. Sources et licences : LICENSES.json. Aucun asset de circuit de reference, aucun contenu TrackTools.\n\nLe modele de jeune pin utilise quatre plans photographiques croises pour limiter son cout. Les trois grands pins conservent un tronc et des branches 3D avec cartes de rameaux derivees du modele source.\n\n## Credits historiques du projet source (avant ce pilote)\n\n'
    (OUT/'CREDITS.md').write_text(intro+credits+'\n\n## Additional shrub source\nPoly Haven searsia_lucida: https://polyhaven.com/a/searsia_lucida — CC0-1.0, https://polyhaven.com/license . Original download hashes: assets/searsia_lucida/SOURCE.json in the development copy. South African source species used as a visual small-leaf shrub surrogate, NOT claimed native to Algeria. No Akagi assets, textures, geometry or names are included.\n',encoding='utf-8')
    dump(DATA/'selection.json',meta)


def render_setup(data,station=35):
    scene=bpy.context.scene
    for obj in list(bpy.data.objects):
        if obj.type=='LIGHT':bpy.data.objects.remove(obj,do_unlink=True)
    eye,_,_=frame(data,station);eye[2]+=1.3
    target,_,_=frame(data,min(station+37,float(data['s3'][-1])-1));target[2]+=1.3
    obj=camera('__PILOT_CAMERA',eye,target);obj.data.lens=28;obj.data.clip_end=5000
    light=bpy.data.lights.new('__PILOT_SUN','SUN');sun=bpy.data.objects.new('__PILOT_SUN',light);scene.collection.objects.link(sun)
    light.energy=3;light.color=(1,.98,.94);light.angle=.12;sun.rotation_euler=Vector((-.35,-.5,-.8)).to_track_quat('-Z','Y').to_euler()
    scene.world=bpy.data.worlds.new('__PILOT_RENDER_WORLD');scene.world.use_nodes=True
    background=scene.world.node_tree.nodes.get('Background');background.inputs['Color'].default_value=(.57,.7,.9,1);background.inputs['Strength'].default_value=.8
    scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.cycles.transparent_max_bounces=256
    scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Filmic';scene.view_settings.look='Medium High Contrast';scene.view_settings.exposure=.3
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    try:
        preferences=bpy.context.preferences.addons['cycles'].preferences;preferences.compute_device_type='CUDA';preferences.get_devices()
        devices=[device for device in preferences.devices if device.type=='CUDA']
        if devices:
            for device in preferences.devices:device.use=device.type=='CUDA'
            scene.cycles.device='GPU'
    except (TypeError,RuntimeError):pass
    return scene


def build():
    for folder in (DATA,OUT,PREVIEW):folder.mkdir(parents=True,exist_ok=True)
    for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
    clean_unused()
    data,meta=select_sector(source_data())
    print('PILOT_SECTOR',json.dumps(meta),flush=True)
    info=json.loads((ROOT/'data/materials_info.json').read_text())
    with bpy.data.libraries.load(str(ASSETS/'optimized_pines.blend'),link=False) as (a,b):b.objects=list(a.objects)
    prototypes=list(b.objects)
    shrubs,shrub_canopy=load_shrubs()
    prototypes.extend(shrubs)
    tree_palette(prototypes+[shrub_canopy],info);asphalt(info)
    ground_textures=ASSETS/'pine_forest/textures'
    floor=pbr_material('forest_floor',ground_textures/'forest_ground_04_diff.png',ground_textures/'forest_ground_04_nor_gl.png',ground_textures/'forest_ground_04_rough.png')
    floor['preview']['tile_m']=3.5
    info['materials']['forest_floor']=floor
    photo=np.asarray(image_pixels(ground_textures/'forest_ground_04_diff.png','RGB'),dtype=float)/255
    light=photo@np.array([.2126,.7152,.0722])
    detail=np.clip(light/max(float(light.mean()),.01),.45,1.7)[:,:,None]
    macro=Image.fromarray(np.uint8(np.random.default_rng(24027).uniform(40,215,(16,16)))).resize((1024,1024),Image.Resampling.BICUBIC)
    blend=np.asarray(macro,dtype=float)[:,:,None]/255
    earth=np.array([.28,.27,.19]);scrub=np.array([.23,.28,.15])
    pixels=np.uint8(np.clip(detail*(earth*(1-blend)+scrub*blend)*255,0,255))
    landscape_diff=dds(Image.fromarray(pixels),TEX/'PH_pilot_landcover.dds')
    info['materials']['landcover']=dict(shaderName='ksPerPixel',alphaBlendMode='Opaque',alphaTested=False,depthMode='DepthNormal',properties=properties(ksAmbient=.4,ksDiffuse=.6,ksSpecular=0),textures=dict(txDiffuse=dict(textureName=landscape_diff),txNormal=dict(textureName='flat_normal.dds')),preview=dict(kind='simple',roughness=1,tile_m=18))
    guard=guardrail_source(info)
    water=copy.deepcopy(info['materials']['metal'])
    water['textures']['txDiffuse']['textureName']=dds(Image.new('RGBA',(16,16),(18,58,80,255)),TEX/'PH_pilot_water.dds')
    water['textures']['txNormal']['textureName']='flat_normal.dds'
    water['preview']['roughness']=.18
    info['materials']['water']=water
    for name,spec in info['materials'].items():
        material=bpy.data.materials.get(name) or bpy.data.materials.new(name);material_nodes(material,spec)
        if spec['preview']['kind']=='foliage':shade_foliage(material)
    sides=data['sides'];s=data['source_s']
    strip('1ROAD_000',np.stack([sides[1,:,0],sides[0,:,0]],axis=1),bpy.data.materials['asphalt'],s,[0,1])
    for side,letter in enumerate(('L','R')):
        grid=sides[side]
        strip(f'1KERB_000_{letter}',grid[:,:2],bpy.data.materials['kerb'],s,[0,1],side==1)
        strip(f'1GRAVEL_000_{letter}',grid[:,1:3],bpy.data.materials['gravel'],s,[0,1],side==1)
        strip(f'1GRASS_000_{letter}',grid[:,2:4],bpy.data.materials['forest_floor'],s,[0,1],side==1)
        strip(f'LAND_SLOPE_{letter}',grid[:,3:],bpy.data.materials['landcover'],s,[0,.3,.6,1],side==1)
    sea_side=int(np.argmin(sides[:,:,6,2].mean(axis=1)));mountain_side=1-sea_side
    backdrop(data)
    count=rails(data,guard,sea_side)
    terrain_detail(data,prototypes,info,mountain_side)
    for station,label in ((.5,'START'),(299.5,'END')):
        center,tangent,left=frame(data,station);vertices=[];faces=[]
        add_box(vertices,faces,center-left*9,center+left*9,.6,-.3,1.2)
        object_mesh('1WALL_PILOT_'+label,vertices,faces,bpy.data.materials['roadside_concrete'])
    add_empties(data)
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH':continue
        if obj.name.startswith('1ROAD_'):
            for loop in obj.data.uv_layers.active.data:loop.uv.y*=7/140
        elif obj.name.startswith(('1KERB_','1GRAVEL_','1GRASS_','LAND_','1WALL_PILOT_','DECOR_SEA')):
            for poly in obj.data.polygons:
                material=obj.data.materials[poly.material_index]
                spec=info['materials'][material.name]
                period=spec['preview'].get('period_m',spec['preview'].get('tile_m',1))
                for index in poly.loop_indices:
                    co=obj.matrix_world@obj.data.vertices[obj.data.loops[index].vertex_index].co
                    if obj.name.startswith('1WALL_PILOT_') and abs(poly.normal.z)<.7:
                        obj.data.uv_layers.active.data[index].uv=((co.x if abs(poly.normal.y)>abs(poly.normal.x) else co.y)/period,co.z/period)
                    else:obj.data.uv_layers.active.data[index].uv=(co.x/period,co.y/period)
    models=compile_models(prototypes,info['materials'])
    shrub_height=max(v.co.z for v in shrub_canopy.data.vertices)
    impostors(shrub_canopy,info['materials'],shrub_height)
    bpy.data.objects.remove(shrub_canopy,do_unlink=True)
    scenery=forest_edges(data,info,sea_side)
    plants=scatter_trees(data,models,sea_side)
    bpy.data.libraries.write(str(DATA/'prototypes.blend'),set(prototypes),path_remap='RELATIVE',compress=True)
    for obj in prototypes:bpy.data.objects.remove(obj,do_unlink=True)
    clean_unused()
    settings=dict(materials={name:{k:v for k,v in spec.items() if k!='preview'} for name,spec in info['materials'].items()},nodes={'*':dict(lodIn=0,lodOut=5000,castShadows=True,visible=True,renderable=True),'1WALL_COLLIDER_*':dict(visible=True,renderable=False,castShadows=False),'DETAIL_*':dict(lodIn=0,lodOut=350),'DETAIL_RAIL_*':dict(lodIn=0,lodOut=45),'LOD_RAIL_*':dict(lodIn=45,lodOut=350),'DETAIL_EDGE_*':dict(lodIn=0,lodOut=110,castShadows=True),'LOD_EDGE_*':dict(lodIn=110,lodOut=350,castShadows=False),'DECOR_SEA':dict(lodIn=0,lodOut=60000,castShadows=False)})
    dump(DATA/'settings.json',settings)
    original_texture_writer=exporter.TextureWriter
    class DDSWriter(original_texture_writer):
        def _get_image_data_from_texture(self,texture):
            path=Path(bpy.path.abspath(texture.image.filepath))
            return path.read_bytes() if path.suffix.lower()=='.dds' else super()._get_image_data_from_texture(texture)
    exporter.TextureWriter=DDSWriter
    path=OUT/'bejaia_saket_pilot300.kn5';partial=path.with_suffix('.kn5.partial');warnings=[]
    try:
        with partial.open('wb') as stream:exporter.KN5FileWriter(stream,bpy.context,settings,warnings).write()
    finally:exporter.TextureWriter=original_texture_writer
    report=inspect_kn5(partial,geometry=True);counts=mesh_counts(report)
    road=next(n for n in report['nodes'] if n['name'].startswith('1ROAD_'))
    expected=sides[:,: ,0].transpose(1,0,2)[:,::-1].reshape(-1,3)[:,[0,2,1]].copy();expected[:,2]*=-1
    actual=road['positions']
    expected_set={tuple(v) for v in expected.astype('<f4')};actual_set={tuple(v) for v in actual}
    assert expected_set==actual_set,'Pilot road was moved or regraded'
    for node in report['nodes']:
        if 'vertices' in node:
            assert node['tangent_stats']['finite'] and node['tangent_stats']['normal_length_error']<.001
    partial.replace(path)
    package_metadata(data,meta,guard[3])
    dump(DATA/'build_report.json',dict(**counts,kn5_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rail_tiles=count,tree_instances=len(plants),tree_models=models,scenery=scenery,road_vertices_match_source=True,surfaces_unchanged=True,runtime_tested=False,warnings=warnings))
    with bpy.data.libraries.load(str(DATA/'prototypes.blend'),link=False) as (a,b):b.objects=list(a.objects)
    lookup={o.name:o for o in b.objects}
    for i,plant in enumerate(plants):
        original=lookup[plant['model']]
        obj=bpy.data.objects.new(f'__TREEFX_PREVIEW_{i:04d}',original.data);bpy.context.collection.objects.link(obj)
        obj.location=plant['position'];obj.rotation_euler.z=plant['angle'];scale=plant['scale'];width=plant['width'];obj.scale=(scale*width,scale*width,scale)
    for obj in b.objects:bpy.data.objects.remove(obj,do_unlink=True)
    for obj in bpy.context.scene.objects:
        if obj.name.startswith(('LOD_RAIL_','LOD_EDGE_')):obj.hide_render=True
    render_setup(data)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'blend/pilot300.blend'),compress=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'blend/pilot300.blend'),compress=True)
    print('PILOT_BUILD_OK',json.dumps(dict(**counts,kn5_bytes=path.stat().st_size,tree_instances=len(plants))),flush=True)


def audit_blend():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'blend/pilot300.blend'),load_ui=False,use_scripts=False)
    paths={}
    for image in bpy.data.images:
        if image.source!='FILE':continue
        path=Path(bpy.path.abspath(image.filepath)).resolve()
        assert image.filepath.startswith('//'),('Non-relative texture',image.name,image.filepath)
        assert path.is_file(),('Missing texture',image.name,str(path))
        assert path.is_relative_to(WORK.resolve()),('Texture outside development copy',str(path))
        paths[image.name]=image.filepath
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH':
            assert obj.data.uv_layers.active is not None,('Missing UV layer',obj.name)
    preview_trees=sum(o.name.startswith('__TREEFX_PREVIEW_') for o in bpy.context.scene.objects)
    assert preview_trees==len(json.loads((DATA/'plants.json').read_text()))
    result=dict(texture_paths_relative=True,texture_paths_exist=True,no_external_dependencies=True,native_uv_layers=True,images=len(paths),tree_preview_instances=preview_trees,paths=paths)
    dump(DATA/'blend_audit.json',result)
    print('PILOT_BLEND_AUDIT_OK',len(paths),'textures',preview_trees,'tree previews')


def render(which,station=35):
    with np.load(DATA/'centerline.npz') as source:data={key:source[key] for key in source.files}
    path=ROOT/'blend'/('bejaia_saket.blend' if which=='before' else 'pilot300.blend')
    if which=='baseline':path=WORK/json.loads((DATA/'art_baseline.json').read_text())['blend_relative_to_work']
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    if which=='baseline':
        for image in bpy.data.images:
            if image.source=='FILE' and image.filepath.startswith('//'):
                original=(ROOT/'blend'/image.filepath[2:]).resolve()
                if original.is_file():image.filepath=str(original);image.reload()
    if which=='after':
        for material in bpy.data.materials:
            if '_card' in material.name or material.name.startswith('fern_02'):shade_foliage(material)
    render_setup(data,station)
    image_name=which if station==35 else f'{which}_{station:03d}'
    bpy.context.scene.render.filepath=str(PREVIEW/(image_name+'.png'))
    bpy.ops.render.render(write_still=True)
    if which=='after' and station==35:
        shutil.copy2(PREVIEW/'after.png',OUT/'ui/preview.png')
        shutil.copy2(PREVIEW/'after.png',OUT/'ui/preview_orig.png')
    print('PILOT_RENDER_OK',which,flush=True)


if __name__=='__main__':
    job=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'build'
    if job=='build':build()
    elif job=='audit':audit_blend()
    elif job in ('before','after','baseline'):render(job)
    elif job=='review':
        for which in ('baseline','after'):
            for station in (35,120,215):render(which,station)
    else:raise ValueError('Unknown pilot job: '+job)
