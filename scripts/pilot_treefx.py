"""Compile the CC0 pine prototypes to the project's documented TreeFX wire format."""
import io
import copy
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import zipfile

import bpy
import numpy as np
from pilot_common import DATA,OUT,TEX,dump,dds,replace_material_slots,foliage_image_metrics
from PIL import Image
from mathutils import Vector
import math
from treefx_wire import mesh_blob,read_mesh
from scenery_assets import card_lod_groups


def groups_for_mesh(mesh,specs,texture_names,double_sided=False):
    mesh.calc_loop_triangles();mesh.calc_normals_split()
    uv=mesh.uv_layers.active
    if uv is None:raise ValueError('Tree prototype has no native UV map')
    groups=[]
    for material_index in sorted(set(t.material_index for t in mesh.loop_triangles)):
        material=mesh.materials[material_index]
        if material is None:raise ValueError('Used tree material is missing')
        spec=specs[material.name]
        diffuse=spec['textures']['txDiffuse']['textureName'];normal=spec['textures']['txNormal']['textureName']
        indices=(texture_names.index(diffuse),texture_names.index(normal))
        vertices=[];normals=[];coords=[];faces=[];lookup={}
        def flush():
            if faces:groups.append((*indices,SimpleNamespace(vertices=vertices.copy(),normals=normals.copy(),uv=coords.copy(),faces=faces.copy())))
        for tri in mesh.loop_triangles:
            if tri.material_index!=material_index or tri.area<1e-12:continue
            if len(vertices)+6>60000:
                flush();vertices=[];normals=[];coords=[];faces=[];lookup={}
            face=[]
            for loop_index in tri.loops:
                loop=mesh.loops[loop_index];normal_vector=loop.normal.normalized()
                if normal_vector.length_squared<.5:normal_vector=tri.normal.normalized()
                coord=uv.data[loop_index].uv
                key=(loop.vertex_index,*normal_vector,*coord)
                if key not in lookup:
                    lookup[key]=len(vertices)
                    vertices.append(tuple(mesh.vertices[loop.vertex_index].co));normals.append(tuple(normal_vector));coords.append(tuple(coord))
                face.append(lookup[key])
            faces.append(face)
            if double_sided and spec['preview']['kind']=='foliage':
                back=[]
                for index in reversed(face):
                    back.append(len(vertices));vertices.append(vertices[index]);coords.append(coords[index]);normals.append(tuple(-x for x in normals[index]))
                faces.append(back)
        flush()
    return groups


def impostors(proto,specs,height,*,cache_dir=DATA,texture_dir=TEX):
    cache_dir=Path(cache_dir);texture_dir=Path(texture_dir)
    cache_dir.mkdir(parents=True,exist_ok=True);texture_dir.mkdir(parents=True,exist_ok=True)
    scene=bpy.data.scenes.new('__IMPOSTOR_BAKE')
    scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=False;scene.cycles.transparent_max_bounces=256
    scene.render.resolution_x=512;scene.render.resolution_y=1024;scene.render.resolution_percentage=100
    scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
    scene.view_settings.exposure=0;scene.view_settings.gamma=1
    mesh=proto.data.copy();obj=bpy.data.objects.new('__IMPOSTOR_TREE',mesh);scene.collection.objects.link(obj)
    materials=[]
    def emission_copy(original):
        material=bpy.data.materials.new('__IMPOSTOR_EMISSION');material.use_nodes=True
        materials.append(material)
        nodes=material.node_tree.nodes;nodes.clear();links=material.node_tree.links
        output=nodes.new('ShaderNodeOutputMaterial');emission=nodes.new('ShaderNodeEmission')
        if original is None:
            links.new(emission.outputs[0],output.inputs[0]);return material
        spec=specs[original.name];texture=nodes.new('ShaderNodeTexImage')
        texture.image=bpy.data.images.load(str(texture_dir/spec['textures']['txDiffuse']['textureName']),check_existing=True)
        links.new(texture.outputs['Color'],emission.inputs['Color'])
        if spec['preview']['kind']=='foliage':
            threshold=nodes.new('ShaderNodeMath');threshold.operation='GREATER_THAN';threshold.inputs[1].default_value=.3
            links.new(texture.outputs['Alpha'],threshold.inputs[0]);mix=nodes.new('ShaderNodeMixShader');transparent=nodes.new('ShaderNodeBsdfTransparent')
            links.new(threshold.outputs[0],mix.inputs[0]);links.new(transparent.outputs[0],mix.inputs[1]);links.new(emission.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],output.inputs[0])
        else:links.new(emission.outputs[0],output.inputs[0])
        return material
    replace_material_slots(mesh,emission_copy)
    camera_data=bpy.data.cameras.new('__IMPOSTOR_CAMERA');camera_obj=bpy.data.objects.new('__IMPOSTOR_CAMERA',camera_data);scene.collection.objects.link(camera_obj)
    camera_data.type='ORTHO';camera_data.ortho_scale=height*1.06;camera_data.clip_end=300
    scene.camera=camera_obj;groups=[];names=[]
    for view in range(4):
        angle=view*math.pi/4
        right=np.array([math.cos(angle),math.sin(angle),0.])
        projected=np.asarray([v.co[:] for v in proto.data.vertices])@right
        span=max(height*1.06,float(np.ptp(projected))*2*1.06)
        camera_data.ortho_scale=span
        camera_obj.location=(math.sin(angle)*50,-math.cos(angle)*50,height/2)
        camera_obj.rotation_euler=(Vector((0,0,height/2))-camera_obj.location).to_track_quat('-Z','Y').to_euler()
        path=cache_dir/f'{proto.name}_impostor_{view}.png';scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True,scene=scene.name)
        with Image.open(path) as image:
            foliage_image_metrics(image)
            name=dds(image.copy(),texture_dir/f'{proto.name}_impostor_{view}.dds',coverage=True)
        half=span/4
        low=height/2-span/2;high=height/2+span/2
        points=[-right*half+[0,0,low],right*half+[0,0,low],right*half+[0,0,high],-right*half+[0,0,high]]
        normal=np.array([math.sin(angle),-math.cos(angle),0.])
        part=SimpleNamespace(vertices=points+points,normals=[normal]*4+[-normal]*4,uv=[(0,0),(1,0),(1,1),(0,1)]*2,faces=[(0,1,2),(0,2,3),(4,6,5),(4,7,6)])
        groups.append((name,part));names.append(name)
    bpy.data.objects.remove(camera_obj,do_unlink=True);bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh)
    bpy.data.scenes.remove(scene)
    for material in materials:bpy.data.materials.remove(material)
    return groups,names


def reduce_card_views(mesh):
    import bmesh
    bm=bmesh.new();bm.from_mesh(mesh);uv=bm.loops.layers.uv.active
    remove=[]
    for face in bm.faces:
        material=mesh.materials[face.material_index]
        if material and '_card' in material.name and 'sapling' not in material.name:
            # The left atlas column contains the two orthogonal twig views.
            if sum(loop[uv].uv.x for loop in face.loops)/len(face.loops)>.5:remove.append(face)
    bmesh.ops.delete(bm,geom=remove,context='FACES')
    bm.to_mesh(mesh);bm.free();mesh.update()


def compile_models(prototypes,specs,*,output_dir=OUT/'extension/trees',cache_dir=DATA,texture_dir=TEX):
    folder=Path(output_dir);cache_dir=Path(cache_dir);texture_dir=Path(texture_dir)
    folder.mkdir(parents=True,exist_ok=True);cache_dir.mkdir(parents=True,exist_ok=True)
    models={};background_previews=[]
    for proto in prototypes:
        if not proto.name.startswith(('PH_pine_0','PH_pine_sapling','PH_shrub_')):continue
        source_name=proto.name
        filename=source_name.lower()+'.bin'
        points=np.asarray([v.co[:] for v in proto.data.vertices])
        radius=float(np.max(abs(points[:,:2])));height=float(points[:,2].max())
        assert radius>0 and height>0
        texture_names=[]
        for material in proto.data.materials:
            if not material:continue
            for slot in ('txDiffuse','txNormal'):
                name=specs[material.name]['textures'][slot]['textureName']
                if name not in texture_names:texture_names.append(name)
        far_groups,far_names=impostors(proto,specs,height,cache_dir=cache_dir,texture_dir=texture_dir)
        texture_names.extend(far_names)
        if 'flat_normal.dds' not in texture_names:texture_names.append('flat_normal.dds')
        textures={name:(texture_dir/name).read_bytes() for name in texture_names}
        config=f'[BASIC]\nHEIGHT={height:.9g}\nWIDTH={radius*2:.9g}\n[SHADING]\nSPECULAR=1\nSUBSCATTERING=1\nREFLECTIVITY=1\nBRIGHTNESS=1\nUSE_AO_CHANNEL=0\n[NORMALS]\nBOOST=0.9\nSPHERE=1\n[LEAVES]\nMULT=20\nOFFSET=0\n[FAKE_SHADOW]\nSIZE=1\nOPACITY=1\n'
        payloads=dict(textures);lod_metrics=[]
        shrub=source_name.startswith('PH_shrub_')
        targets=(10000,2000,16) if shrub else ((1000,500,16) if 'sapling' in source_name else (20000,9000,16))
        distances=(20,75,900) if shrub else (28,100,900)
        for lod,(target,distance) in enumerate(zip(targets,distances)):
            temporary=bpy.data.objects.new('__TREE_LOD_BUILD',proto.data.copy())
            bpy.context.collection.objects.link(temporary)
            if lod==1:reduce_card_views(temporary.data)
            source_triangles=sum(len(p.vertices)-2 for p in temporary.data.polygons)
            if source_triangles>target and not (lod==1 and source_name.startswith('PH_pine_0')):
                mod=temporary.modifiers.new('TreeFX LOD','DECIMATE');mod.ratio=target/source_triangles;mod.use_collapse_triangulate=True
            bpy.context.view_layer.update()
            dg=bpy.context.evaluated_depsgraph_get();dg.update()
            mesh=bpy.data.meshes.new_from_object(temporary.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
            if lod==2:
                groups=[(texture_names.index(name),texture_names.index('flat_normal.dds'),part) for name,part in far_groups]
            elif lod==1 and source_name.startswith('PH_pine_0'):groups=card_lod_groups(near_groups,texture_names)
            else:groups=groups_for_mesh(mesh,specs,texture_names,double_sided=shrub)
            if lod==0:near_groups=groups
            blob,metrics=mesh_blob(groups,textures,radius,height)
            if lod==1 and source_name.startswith('PH_pine_0'):medium_preview_mesh=mesh.copy()
            if lod==2:assert metrics['triangles']==16
            assert read_mesh(blob,textures)==metrics
            payloads[f'LOD{lod}.mesh']=blob;lod_metrics.append(metrics)
            config+=f'[LOD_{lod}]\nMODEL=LOD{lod}.mesh\nDISTANCE={distance}\n'
            bpy.data.objects.remove(temporary,do_unlink=True);bpy.data.meshes.remove(mesh)
        payloads['tree.ini']=config.encode()
        output=folder/filename
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,blob in sorted(payloads.items()):
                entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(entry,blob)
        with zipfile.ZipFile(output) as archive:assert archive.testzip() is None
        models[source_name]=dict(kind='shrub' if shrub else 'pine',file=filename,lods=lod_metrics,bytes=output.stat().st_size,height=height,width=radius*2)
        print('PILOT_TREEFX_MODEL_OK',source_name,json.dumps(models[source_name]),flush=True)
        if source_name.startswith('PH_pine_0'):
            from blender_mesh import object_mesh
            from blender_materials import material_nodes
            from pilot_common import properties
            background_name=source_name.replace('PH_pine_','PH_pine_bg_',1)
            background_file=background_name.lower()+'.bin'
            background_names=far_names+['flat_normal.dds']
            background_textures={name:payloads[name] for name in background_names}
            background_groups=[(background_names.index(name),background_names.index('flat_normal.dds'),part) for name,part in far_groups]
            background_blob,background_metrics=mesh_blob(background_groups,background_textures,radius,height)
            assert read_mesh(background_blob,background_textures)==background_metrics==lod_metrics[-1]
            background_payload=dict(background_textures)
            background_payload['LOD2.mesh']=background_blob
            background_config=config.split('[LOD_0]')[0]
            for lod,distance in enumerate((180,450,900)):
                background_config+=f'[LOD_{lod}]\nMODEL=LOD2.mesh\nDISTANCE={distance}\n'
            background_payload['tree.ini']=background_config.encode()
            with zipfile.ZipFile(folder/background_file,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for name,blob in sorted(background_payload.items()):
                    entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
                    archive.writestr(entry,blob)
            vertices=[];faces=[];uv=[];normals=[];materials=[];face_materials=[]
            for view,(texture,part) in enumerate(far_groups):
                start=len(vertices);vertices.extend(part.vertices);uv.extend(part.uv);normals.extend(part.normals)
                faces.extend(tuple(start+i for i in face) for face in part.faces)
                face_materials.extend([view]*len(part.faces))
                material_name=f'{background_name}_card_{view}'
                spec=dict(shaderName='ksPerPixelAT',alphaBlendMode='Opaque',alphaTested=True,depthMode='DepthNormal',properties=properties(ksAmbient=.4,ksDiffuse=.6,ksSpecular=0),textures=dict(txDiffuse=dict(textureName=texture)),preview=dict(kind='foliage',roughness=1))
                specs[material_name]=spec
                material=bpy.data.materials.new(material_name);preview=copy.deepcopy(spec)
                for entry in preview['textures'].values():entry['textureName']=str(texture_dir.resolve()/entry['textureName'])
                material_nodes(material,preview);materials.append(material)
            background=object_mesh(background_name,vertices,faces,materials[0],uv)
            for material in materials[1:]:background.data.materials.append(material)
            for face,index in zip(background.data.polygons,face_materials):face.material_index=index
            background.data.use_auto_smooth=True;background.data.normals_split_custom_set_from_vertices(normals)
            bpy.context.collection.objects.unlink(background)
            background_previews.append(background)
            models[background_name]=dict(kind='background',file=background_file,lods=[lod_metrics[-1]]*3,bytes=(folder/background_file).stat().st_size,height=height,width=radius*2)
            medium_name=source_name.replace('PH_pine_','PH_pine_mid_',1)
            medium_file=medium_name.lower()+'.bin'
            medium_payload={name:blob for name,blob in payloads.items() if name.endswith('.dds') or name in ('LOD1.mesh','LOD2.mesh')}
            medium_config=config.split('[LOD_0]')[0]
            for lod,(mesh_name,distance) in enumerate((('LOD1.mesh',28),('LOD1.mesh',110),('LOD2.mesh',900))):
                medium_config+=f'[LOD_{lod}]\nMODEL={mesh_name}\nDISTANCE={distance}\n'
            medium_payload['tree.ini']=medium_config.encode()
            with zipfile.ZipFile(folder/medium_file,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for name,blob in sorted(medium_payload.items()):
                    entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
                    archive.writestr(entry,blob)
            medium_preview=bpy.data.objects.new(medium_name,medium_preview_mesh)
            background_previews.append(medium_preview)
            models[medium_name]=dict(kind='midstory',file=medium_file,lods=[lod_metrics[1],lod_metrics[1],lod_metrics[2]],bytes=(folder/medium_file).stat().st_size,height=height,width=radius*2)
    prototypes.extend(background_previews)
    dump(cache_dir/'treefx_models.json',models)
    return models
