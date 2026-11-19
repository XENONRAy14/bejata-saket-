"""Bake the original CC0 needle geometry into twig cards, instead of deleting needles."""
from pathlib import Path
import json
import math
import re
import sys
W=Path(__file__).resolve().parent
sys.path[:0]=[str(W/'tools/pydeps'),str(W/'project/scripts')]
from pilot_common import replace_material_slots,foliage_image_metrics
import bpy
import numpy as np
from PIL import Image
from mathutils import Vector
SOURCE=W/'assets/pine_forest/polyhaven_pine_fir_forest.blend'
OUTPUT=W/'assets/pine_cards';OUTPUT.mkdir(exist_ok=True)
with bpy.data.libraries.load(str(SOURCE),link=False) as (a,b):b.objects=['pine_01','pine_sapling_small_a']
for image in bpy.data.images:
    if image.source=='FILE':
        path=SOURCE.parent/'textures'/Path(image.filepath.replace('\\','/')).name
        if path.exists():image.filepath=str(path)
objects=[o for o in bpy.data.objects if o.type=='MESH' and (re.fullmatch(r'pine_twig_\d+',o.name) or o.name=='pine_sapling_small_a')]
report=[]
for original in objects:
    mesh=original.data.copy()
    if not mesh.uv_layers and mesh.attributes.get('UVMap'):
        attr=mesh.attributes['UVMap'];values=np.empty(len(mesh.loops)*3,dtype=np.float32);attr.data.foreach_get('vector',values);mesh.attributes.remove(attr)
        mesh.uv_layers.new(name='UVMap').data.foreach_set('uv',values.reshape(-1,3)[:,:2].ravel())
    points=np.asarray([v.co[:] for v in mesh.vertices]);center=points.mean(axis=0)
    _,eigen=np.linalg.eigh(np.cov((points-center).T));up=eigen[:,-1];right=eigen[:,-2]
    if up[2]<0:up=-up
    front=np.cross(up,right);basis=np.column_stack([right,front,up])
    normalized=(points-center)@basis
    # Include all needle tips, with space for antialiasing at the alpha boundary.
    half=float(np.max(abs(normalized)))*1.07;scale=half*2
    for v,co in zip(mesh.vertices,normalized):v.co=co
    emission_materials=[]
    def emission_copy(material):
        if material is None:
            placeholder=bpy.data.materials.new('__CARD_EMPTY');emission_materials.append(placeholder);return placeholder
        copy=material.copy();copy.name='__CARD_EMISSION';emission_materials.append(copy)
        nodes=copy.node_tree.nodes;links=copy.node_tree.links
        principal=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
        output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL');emission=nodes.new('ShaderNodeEmission')
        if principal.inputs['Base Color'].is_linked:links.new(principal.inputs['Base Color'].links[0].from_socket,emission.inputs['Color'])
        else:emission.inputs['Color'].default_value=principal.inputs['Base Color'].default_value
        if principal.inputs['Alpha'].is_linked:
            alpha=principal.inputs['Alpha'].links[0].from_socket
            threshold=nodes.new('ShaderNodeMath');threshold.operation='GREATER_THAN';threshold.inputs[1].default_value=.3;links.new(alpha,threshold.inputs[0])
            mix=nodes.new('ShaderNodeMixShader');transparent=nodes.new('ShaderNodeBsdfTransparent')
            links.new(threshold.outputs[0],mix.inputs[0]);links.new(transparent.outputs[0],mix.inputs[1]);links.new(emission.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],output.inputs[0])
        else:links.new(emission.outputs[0],output.inputs[0])
        return copy
    replace_material_slots(mesh,emission_copy)
    scene=bpy.data.scenes.new('__CARD_BAKE');obj=bpy.data.objects.new('__CARD_RAW',mesh);scene.collection.objects.link(obj)
    scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=False;scene.cycles.transparent_max_bounces=16
    scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    scene.render.resolution_x=512;scene.render.resolution_y=512;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    camera_data=bpy.data.cameras.new('__CARD_CAMERA');camera=bpy.data.objects.new('__CARD_CAMERA',camera_data);scene.collection.objects.link(camera)
    camera_data.type='ORTHO';camera_data.ortho_scale=scale;camera_data.clip_end=100;scene.camera=camera
    atlas=Image.new('RGBA',(1024,1024),(0,0,0,0));vertices=[];faces=[];uvs=[]
    for view in range(4):
        theta=view*math.pi/4;camera.location=(math.sin(theta)*scale*3,-math.cos(theta)*scale*3,0)
        camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler()
        path=OUTPUT/f'{original.name}_view{view}.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True,scene=scene.name)
        with Image.open(path) as image:
            foliage_image_metrics(image)
            atlas.paste(image,(view%2*512,view//2*512))
            bounds=image.getchannel('A').point(lambda a:255 if a>8 else 0).getbbox()
            left,top,right,bottom=bounds
            left=max(0,left-3);top=max(0,top-3);right=min(512,right+3);bottom=min(512,bottom+3)
        direction=np.array([math.cos(theta),math.sin(theta),0.])
        x0=left/512*scale-half;x1=right/512*scale-half
        z0=half-bottom/512*scale;z1=half-top/512*scale
        local=[direction*x0+[0,0,z0],direction*x1+[0,0,z0],direction*x1+[0,0,z1],direction*x0+[0,0,z1]]
        index=len(vertices);vertices.extend([basis@p+center for p in local])
        faces.append((index,index+1,index+2,index+3))
        u0=(view%2*512+left)/1024;u1=(view%2*512+right)/1024
        v0=1-(view//2*512+bottom)/1024;v1=1-(view//2*512+top)/1024
        uvs.extend([(u0,v0),(u1,v0),(u1,v1),(u0,v1)])
    diffuse=OUTPUT/f'{original.name}_card_diff.png';alpha=OUTPUT/f'{original.name}_card_alpha.png'
    atlas.save(diffuse);atlas.getchannel('A').save(alpha)
    material=bpy.data.materials.new('PH_'+original.name+'_card');material.use_nodes=True;material.blend_method='CLIP';material.alpha_threshold=.3
    nodes=material.node_tree.nodes;links=material.node_tree.links;principal=nodes.get('Principled BSDF')
    texture=nodes.new('ShaderNodeTexImage');texture.image=bpy.data.images.load(str(diffuse));links.new(texture.outputs['Color'],principal.inputs['Base Color'])
    texture=nodes.new('ShaderNodeTexImage');texture.image=bpy.data.images.load(str(alpha));texture.image.colorspace_settings.name='Non-Color';links.new(texture.outputs['Color'],principal.inputs['Alpha'])
    for face in list(faces):
        base=len(vertices);vertices.extend([vertices[i].copy() for i in face][::-1]);uvs.extend([uvs[i] for i in face][::-1]);faces.append(tuple(range(base,base+4)))
    card=bpy.data.meshes.new(original.name+'_cards');card.from_pydata(vertices,[],faces);card.update();card.materials.append(material)
    uv=card.uv_layers.new(name='UVMap')
    for target,value in zip(uv.data,uvs):target.uv=value
    original.data=card;original.modifiers.clear()
    bpy.data.objects.remove(camera,do_unlink=True);bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(mesh);bpy.data.scenes.remove(scene)
    for material in emission_materials:bpy.data.materials.remove(material)
    report.append(dict(name=original.name,raw_vertices=len(points),card_triangles=sum(len(face)-2 for face in faces),atlas=str(diffuse)))
    print('CC0_NEEDLE_CARDS_OK',json.dumps(report[-1]),flush=True)
bpy.data.libraries.write(str(W/'assets/pine_cards.blend'),set(objects),path_remap='RELATIVE',compress=True)
(W/'pine_cards.json').write_text(json.dumps(report,indent=2)+'\n')
