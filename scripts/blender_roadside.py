"""Attach visual-only roadside batches and preserve the physical meshes."""
import json
import hashlib
import os
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from blender_mesh import object_mesh
from check_kn5 import inspect_dds


def main():
    bpy.ops.preferences.addon_enable(module='blender_assetto_corsa_tools')
    for obj in list(bpy.data.objects):
        if obj.name.startswith('DETAIL_'):bpy.data.objects.remove(obj,do_unlink=True)
    from blender_materials import material_nodes,main as export
    recipe=json.loads((ROOT/'data/roadside_info.json').read_text())
    specs=dict(roadside_signs=recipe['sign_material'],roadside_litter=recipe['litter_material'],roadside_concrete=recipe['concrete_material'])
    for name,spec in specs.items():material_nodes(bpy.data.materials.get(name) or bpy.data.materials.new(name),spec)
    data=np.load(ROOT/'data/roadside.npz')
    for i,(name,material) in enumerate(data['names']):
        obj=object_mesh(name,data[f'v{i}'],data[f'f{i}'].tolist(),bpy.data.materials[material])
        if material in specs:
            for loop,uv in zip(obj.data.uv_layers.active.data,[data[f'uv{i}'][v.vertex_index] for v in obj.data.loops]):loop.uv=uv
    if os.environ.get('BS_ROADSIDE_PREVIEW_ONLY'):
        path=ROOT/'data/research_cache/vegetation_preview_materials.json';info=json.loads(path.read_text())
        info['materials'].update(specs);path.write_text(json.dumps(info,indent=2)+'\n')
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'data/research_cache/vegetation_preview.blend'))
        print('ROADSIDE_PREVIEW_OK')
        return
    path=ROOT/'data/materials_info.json';info=json.loads(path.read_text());info['materials'].update(specs)
    for name in specs:
        texture=ROOT/'textures/v2'/(name+'.dds');blob=texture.read_bytes()
        info['textures'][name+'.dds']=dict(inspect_dds(blob),sha256=hashlib.sha256(blob).hexdigest(),file=str(texture.relative_to(ROOT)))
    info['dds_gpu_bytes']=sum(v['gpu_bytes'] for v in info['textures'].values())
    path.write_text(json.dumps(info,indent=2)+'\n')
    path=ROOT/'blend/settings.json';settings=json.loads(path.read_text())
    for name in list(settings['nodes']):
        if name.startswith('DETAIL_'):del settings['nodes'][name]
    settings['nodes']['DETAIL_*']=dict(lodIn=0,lodOut=1400,castShadows=True)
    settings['nodes']['DETAIL_*_roadside_litter']=dict(lodIn=0,lodOut=1400,castShadows=False)
    path.write_text(json.dumps(settings,indent=2)+'\n')
    export()
    print('ROADSIDE_SCENE_OK visual_only=True')


if __name__=='__main__':main()
