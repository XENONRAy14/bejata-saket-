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
    material=bpy.data.materials.get('roadside_signs') or bpy.data.materials.new('roadside_signs')
    from blender_materials import material_nodes,main as export
    spec=json.loads((ROOT/'data/roadside_info.json').read_text())['sign_material']
    material_nodes(material,spec)
    data=np.load(ROOT/'data/roadside.npz')
    for i,(name,material) in enumerate(data['names']):
        obj=object_mesh(name,data[f'v{i}'],data[f'f{i}'].tolist(),bpy.data.materials[material])
        if material=='roadside_signs':
            for loop,uv in zip(obj.data.uv_layers.active.data,[data[f'uv{i}'][v.vertex_index] for v in obj.data.loops]):loop.uv=uv
    if os.environ.get('BS_ROADSIDE_PREVIEW_ONLY'):
        path=ROOT/'data/research_cache/vegetation_preview_materials.json';info=json.loads(path.read_text())
        info['materials']['roadside_signs']=spec;path.write_text(json.dumps(info,indent=2)+'\n')
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'data/research_cache/vegetation_preview.blend'))
        print('ROADSIDE_PREVIEW_OK')
        return
    path=ROOT/'data/materials_info.json';info=json.loads(path.read_text());info['materials']['roadside_signs']=spec
    texture=ROOT/'textures/v2/roadside_signs.dds';blob=texture.read_bytes()
    info['textures']['roadside_signs.dds']=dict(inspect_dds(blob),sha256=hashlib.sha256(blob).hexdigest(),file=str(texture.relative_to(ROOT)))
    info['dds_gpu_bytes']=sum(v['gpu_bytes'] for v in info['textures'].values())
    path.write_text(json.dumps(info,indent=2)+'\n')
    path=ROOT/'blend/settings.json';settings=json.loads(path.read_text())
    for name in list(settings['nodes']):
        if name.startswith('DETAIL_'):del settings['nodes'][name]
    settings['nodes']['DETAIL_*']=dict(lodIn=0,lodOut=1400,castShadows=True)
    path.write_text(json.dumps(settings,indent=2)+'\n')
    export()
    print('ROADSIDE_SCENE_OK visual_only=True')


if __name__=='__main__':main()
