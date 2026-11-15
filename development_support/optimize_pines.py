"""Bake practical pine prototypes from the user's copied CC0 procedural forest."""
from pathlib import Path
import hashlib
import json
import re
import bpy

WORK=Path(__file__).resolve().parent
ASSETS=WORK/'assets'
source=ASSETS/'pine_forest/polyhaven_pine_fir_forest.blend'
with bpy.data.libraries.load(str(source),link=False) as (a,b):
    b.objects=['pine_01','pine_03','pine_04','pine_sapling_small_a','fern_02_a_lod1','rock_moss_set_01_a_lod1']
roots=list(b.objects)
for obj in list(bpy.context.scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
for image in bpy.data.images:
    if image.source=='FILE':
        target=source.parent/'textures'/Path(image.filepath.replace('\\','/')).name
        if target.exists():image.filepath=str(target)


def decimated(obj,ratio):
    modifier=obj.modifiers.new('Development geometry budget','DECIMATE')
    modifier.ratio=ratio
    modifier.use_collapse_triangulate=True
    linked=obj.name in bpy.context.collection.objects
    if not linked:bpy.context.collection.objects.link(obj)
    dg=bpy.context.evaluated_depsgraph_get()
    mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
    obj.modifiers.clear()
    obj.data=mesh
    if not linked:bpy.context.collection.objects.unlink(obj)

with bpy.data.libraries.load(str(ASSETS/'pine_cards.blend'),link=False) as (a,b):b.objects=list(a.objects)
for card in b.objects:
    original=bpy.data.objects.get(card.name.rsplit('.',1)[0])
    if original is not None and original!=card:
        original.data=card.data.copy();original.modifiers.clear()
for image in bpy.data.images:
    target=ASSETS/'pine_cards'/Path(image.filepath.replace('\\','/')).name
    if target.exists():image.filepath=str(target)
for obj in list(bpy.data.objects):
    if obj.type=='MESH' and re.fullmatch(r'pine_twig_\d+(\.\d+)?',obj.name):
        if len(obj.data.polygons)>1000:decimated(obj,.010)
    elif obj.type=='MESH' and (re.fullmatch(r'pine_branch_\d+(\.\d+)?',obj.name) or obj.name.startswith('pine_dead_branch_')):
        decimated(obj,.08)
    elif obj.type=='MESH' and obj.name.startswith('pine_trunk_'):
        decimated(obj,.12)
for group in bpy.data.node_groups:
    if group.bl_idname=='GeometryNodeTree' and re.fullmatch(r'pine_twig_\d+',group.name):
        for node in group.nodes:
            if node.type=='GROUP_INPUT':
                pass
        for socket in group.inputs:
            if socket.name=='needles_amount':socket.default_value=18
            elif socket.name=='dry needles_amount':socket.default_value=3
for obj in bpy.data.objects:
    for mod in obj.modifiers:
        if mod.type!='NODES' or not mod.node_group:continue
        if re.fullmatch(r'pine_twig_\d+',mod.node_group.name):
            for socket in mod.node_group.inputs:
                if socket.name=='needles_amount':mod[socket.identifier]=18
                elif socket.name=='dry needles_amount':mod[socket.identifier]=3
        elif mod.node_group.name.startswith('scots_pine_'):
            for socket in mod.node_group.inputs:
                if socket.name=='trunk_res':mod[socket.identifier]=36
                elif socket.name=='trunk_circle_res':mod[socket.identifier]=12
                elif socket.name=='branch_res':mod[socket.identifier]=15
for obj in bpy.data.objects:obj.update_tag()
for group in bpy.data.node_groups:group.update_tag()
prototypes=[];report=[]
for root in roots:
    if root.name=='pine_sapling_small_a' and len(root.data.polygons)>1000:decimated(root,.18)
    bpy.context.collection.objects.link(root)
    root.location=(0,0,0)
    root.hide_viewport=False
    root.hide_set(False)
    bpy.context.view_layer.update()
    dg=bpy.context.evaluated_depsgraph_get()
    evaluated=root.evaluated_get(dg)
    mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=dg)
    name='PH_'+root.name
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.collection.objects.unlink(root)
    import bmesh
    import numpy as np
    attribute=mesh.attributes.get('UVMap')
    if not mesh.uv_layers and attribute and attribute.domain=='CORNER':
        values=np.zeros(len(mesh.loops)*3,dtype=np.float32)
        attribute.data.foreach_get('vector',values)
        mesh.attributes.remove(attribute)
        uv=mesh.uv_layers.new(name='UVMap')
        uv.data.foreach_set('uv',values.reshape(-1,3)[:,:2].ravel())
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(mesh);bm.free();mesh.update()
    mesh.calc_loop_triangles()
    if len(mesh.loop_triangles)>20000:
        decimated(obj,20000/len(mesh.loop_triangles))
        mesh=obj.data
    for p in mesh.polygons:
        material=mesh.materials[p.material_index]
        p.use_smooth=not (material and '_card' in material.name)
    print('TREE_UV_LAYERS',name,list(mesh.uv_layers.keys()),flush=True)
    points=[v.co for v in mesh.vertices]
    bounds=[[min(p[j] for p in points),max(p[j] for p in points)] for j in range(3)]
    low=bounds[2][0]
    for vertex in mesh.vertices:vertex.co.z-=low
    mesh.calc_loop_triangles()
    row=dict(name=name,vertices=len(mesh.vertices),triangles=len(mesh.loop_triangles),bounds=bounds,materials=[m.name if m else None for m in mesh.materials])
    report.append(row);prototypes.append(obj)
    print('OPTIMIZED_PROTOTYPE',json.dumps(row),flush=True)
    bpy.context.collection.objects.unlink(obj)
output=ASSETS/'optimized_pines.blend'
bpy.data.libraries.write(str(output),set(prototypes),fake_user=True,compress=True)
(ASSETS/'optimized_pines.json').write_text(json.dumps(dict(license='CC0-1.0',species='Scots pine (Pinus sylvestris), not Aleppo pine; no firs selected',source_library='pine_forest/polyhaven_pine_fir_forest.blend',prototypes=report),indent=2),encoding='utf-8')
print('OPTIMIZED_PINES_OK',output,flush=True)
