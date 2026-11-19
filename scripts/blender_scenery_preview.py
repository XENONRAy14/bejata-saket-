"""Matched driver-height qualification renders from the actual KN5/TreeFX outputs."""
import configparser
import io
import json
from pathlib import Path
import struct
import sys
import zipfile

import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from pilot_common import frame
from scenery_kn5 import Reader, nodes, parse_tree, read
from scenery_preview_common import tree_lod


def blender_vector(values):return np.asarray(values)[:,[0,2,1]]*[1,-1,1]


def material(name,texture,folder,alpha=False,object_color=False):
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF');shader.inputs['Roughness'].default_value=.85
    if texture:
        path=folder/texture[0]
        if not path.exists():path.write_bytes(texture[1])
        image=bpy.data.images.load(str(path),check_existing=True)
        image.alpha_mode='CHANNEL_PACKED'
        node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
        mat.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])
        if object_color:
            tint=mat.node_tree.nodes.new('ShaderNodeObjectInfo');mixed=mat.node_tree.nodes.new('ShaderNodeMixRGB')
            mixed.blend_type='MULTIPLY';mixed.inputs[0].default_value=1
            mat.node_tree.links.new(node.outputs['Color'],mixed.inputs[1]);mat.node_tree.links.new(tint.outputs['Color'],mixed.inputs[2])
            mat.node_tree.links.new(mixed.outputs[0],shader.inputs['Base Color'])
        if alpha:
            clip=mat.node_tree.nodes.new('ShaderNodeMath');clip.operation='GREATER_THAN';clip.inputs[1].default_value=.3
            mat.node_tree.links.new(node.outputs['Alpha'],clip.inputs[0]);mat.node_tree.links.new(clip.outputs[0],shader.inputs['Alpha'])
            if name=='forest_edge':
                nodes=mat.node_tree.nodes;links=mat.node_tree.links;geometry=nodes.new('ShaderNodeNewGeometry')
                front=nodes.new('ShaderNodeMath');front.operation='SUBTRACT';front.inputs[0].default_value=1
                links.new(geometry.outputs['Backfacing'],front.inputs[1])
                coverage=nodes.new('ShaderNodeMath');coverage.operation='MULTIPLY'
                links.new(front.outputs[0],coverage.inputs[0]);links.new(clip.outputs[0],coverage.inputs[1]);links.new(coverage.outputs[0],shader.inputs['Alpha'])
            mat.blend_method='CLIP';mat.alpha_threshold=.3
    return mat


def multilayer(mat,spec,textures,folder):
    nodes=mat.node_tree.nodes;links=mat.node_tree.links
    shader=nodes.get('Principled BSDF');macro=next(n for n in nodes if n.type=='TEX_IMAGE')
    def texture(slot):
        name=spec['textures'][slot];path=folder/name
        if not path.exists():path.write_bytes(textures[name])
        tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(path),check_existing=True)
        tex.image.alpha_mode='CHANNEL_PACKED'
        tex.image.colorspace_settings.name='Non-Color' if slot=='txMask' else 'sRGB'
        return tex
    mask_texture=texture('txMask');mask=nodes.new('ShaderNodeSeparateRGB');links.new(mask_texture.outputs['Color'],mask.inputs[0])
    geometry=nodes.new('ShaderNodeNewGeometry');mapping=nodes.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY'
    scale=spec['properties']['multR'][0];mapping.inputs[1].default_value=(scale,-scale,0)
    links.new(geometry.outputs['Position'],mapping.inputs[0])
    weights=[mask.outputs[c] for c in 'RGB']+[mask_texture.outputs['Alpha']];combined=None
    for channel,weight in zip('RGBA',weights):
        detail=texture('txDetail'+channel);links.new(mapping.outputs[0],detail.inputs['Vector'])
        weighted=nodes.new('ShaderNodeMixRGB');weighted.blend_type='MULTIPLY';weighted.inputs[0].default_value=1
        links.new(detail.outputs['Color'],weighted.inputs[1]);links.new(weight,weighted.inputs[2])
        if combined is None:combined=weighted.outputs[0]
        else:
            total=nodes.new('ShaderNodeMixRGB');total.blend_type='ADD';total.inputs[0].default_value=1
            links.new(combined,total.inputs[1]);links.new(weighted.outputs[0],total.inputs[2]);combined=total.outputs[0]
    mixed=nodes.new('ShaderNodeMixRGB');mixed.blend_type='MULTIPLY';mixed.inputs[0].default_value=1
    links.new(macro.outputs['Color'],mixed.inputs[1]);links.new(combined,mixed.inputs[2]);links.new(mixed.outputs[0],shader.inputs['Base Color'])


def object_mesh(name,positions,faces,uv,materials,indices=None,normals=None):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(positions.tolist(),[],np.asarray(faces).tolist());mesh.update()
    for mat in materials:mesh.materials.append(mat)
    if indices is not None:
        for face,index in zip(mesh.polygons,indices):face.material_index=index
    layer=mesh.uv_layers.new()
    for loop in mesh.loops:layer.data[loop.index].uv=uv[loop.vertex_index]
    if normals is not None:
        mesh.use_auto_smooth=True;mesh.normals_split_custom_set_from_vertices(normals.tolist())
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);return obj


def tree_model(path,folder,lod=0):
    with zipfile.ZipFile(path) as archive:
        config=configparser.ConfigParser();config.read_string(archive.read('tree.ini').decode())
        height=float(config['BASIC']['HEIGHT']);radius=float(config['BASIC']['WIDTH'])/2
        reader=Reader(archive.read(config[f'LOD_{lod}']['MODEL']))
        reader.take(5);names=[]
        for _ in range(reader.number()):reader.take(4);names.append(reader.text())
        materials=[];vertices=[];uvs=[];normals=[];faces=[];face_materials=[]
        while reader.offset<len(reader.blob):
            diffuse=reader.number('i')
            if diffuse==-1:break
            reader.number();indices=np.frombuffer(reader.take(reader.number()*2),dtype='<u2').reshape(-1,3)
            count=reader.number();values=np.frombuffer(reader.take(count*44),dtype=np.dtype([('v','<f4',(8,)),('tail','u1',(12,))]))['v'].copy()
            offset=len(vertices);vertices.extend(blender_vector(values[:,:3]*[radius,height,radius]));normals.extend(blender_vector(values[:,3:6]))
            uvs.extend(values[:,6:8]*[1,-1]+[0,1]);faces.extend(indices.astype(np.int64)+offset)
            face_materials.extend([len(materials)]*len(indices))
            name=names[diffuse];materials.append(material(name,(name,archive.read(name)),folder,alpha=True,object_color=True))
        obj=object_mesh(path.stem,np.asarray(vertices),faces,np.asarray(uvs),materials,face_materials,np.asarray(normals))
        bpy.context.collection.objects.unlink(obj)
        return obj.data


def render(track,output,label,data,station,reverse=False):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    folder=output/'preview_cache';folder.mkdir(exist_ok=True)
    model=read(track/'bejaia_saket.kn5');textures={t['name']:t['blob'] for t in model['textures']}
    mats=[]
    for entry in model['materials']:
        texture=entry['textures'].get('txDiffuse')
        mat=material(entry['name'],(texture,textures[texture]) if texture else None,folder,'AT' in entry['shader'])
        if 'txMask' in entry['textures']:multilayer(mat,entry,textures,folder)
        mats.append(mat)
    origin,tangent,_=frame(data,station);origin[2]+=1.25
    for node in nodes(model):
        if node['kind']!=2 or not node['tail'][-1]:continue
        lod_in,lod_out=struct.unpack_from('<2f',node['tail'],4)
        vertices=np.frombuffer(node['vertices'],dtype='<f4').reshape(-1,11)
        positions=blender_vector(vertices[:,:3]);center=(positions.max(0)+positions.min(0))/2
        distance=np.linalg.norm(center-origin)
        if distance<lod_in or distance>lod_out:continue
        delta=np.maximum(np.maximum(positions.min(0)-origin,origin-positions.max(0)),0)
        if np.linalg.norm(delta[:2])>1700:continue
        faces=np.frombuffer(node['indices'],dtype='<u2').reshape(-1,3)
        object_mesh(node['name'],positions,faces,vertices[:,6:8]*[1,-1],[mats[node['material']]],normals=blender_vector(vertices[:,3:6]))
    prototypes={};tree_count=0
    for line in (track/'extension/trees/trees.txt').read_text().splitlines():
        plant=parse_tree(line);distance=np.linalg.norm(np.asarray(plant['position'])-origin)
        if distance>900:continue
        path=track/'extension/trees'/plant['model']
        with zipfile.ZipFile(path) as archive:
            config=configparser.ConfigParser();config.read_string(archive.read('tree.ini').decode())
            lod=tree_lod(config,distance)
            if lod is None:continue
        key=(str(path),lod)
        if key not in prototypes:prototypes[key]=tree_model(path,folder,lod)
        obj=bpy.data.objects.new('TREE_'+str(tree_count),prototypes[key]);bpy.context.collection.objects.link(obj)
        obj.color=(*plant['color'],1)
        obj.location=plant['position'];obj.rotation_euler.z=plant['angle'];obj.scale=(plant['scale']*plant['width'],plant['scale']*plant['width'],plant['scale']);tree_count+=1
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
    scene.cycles.transparent_max_bounces=128;scene.render.threads_mode='FIXED';scene.render.threads=8
    scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.55,.68,.85,1)
    scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.45
    sun_data=bpy.data.lights.new('SUN','SUN');sun_data.energy=3;sun=bpy.data.objects.new('SUN',sun_data);bpy.context.collection.objects.link(sun)
    sun.rotation_euler=(.55,-.4,-.8);sun_data.angle=.08
    cam_data=bpy.data.cameras.new('SUMMIT_DRIVER');cam=bpy.data.objects.new('SUMMIT_DRIVER',cam_data);bpy.context.collection.objects.link(cam)
    cam.location=origin;target=origin+tangent*(-40 if reverse else 40)+[0,0,-.7]
    cam.rotation_euler=(Vector(target)-Vector(origin)).to_track_quat('-Z','Y').to_euler();cam_data.lens=28;cam_data.clip_end=4000;scene.camera=cam
    scene.view_settings.view_transform='Filmic';scene.view_settings.look='Medium High Contrast';scene.view_settings.exposure=0
    scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.render.resolution_percentage=100
    scene.render.filepath=str(output/f'{label}.png');bpy.ops.render.render(write_still=True)
    print('SCENERY_DRIVER_RENDER_OK',label,'station',station,'height',1.25,'reverse',reverse,'tree_preview_instances',tree_count,flush=True)


if __name__=='__main__':
    output=Path(sys.argv[sys.argv.index('--')+1])
    with np.load(ROOT/'data/centerline.npz') as source:data=dict(source)
    for label,track in [('before',ROOT/'out/bejaia_saket'),('after',output)]:
        render(track,output,label,data,1030.)
        render(track,output,label+'_exit_reverse',data,1230.,reverse=True)
