"""Create logical AC objects and export via the unchanged addon's writer."""
import configparser
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time

import bpy
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from blender_mesh import add_box, camera, object_mesh


def main():
    output = ROOT/'out/bejaia_saket'
    plan = json.loads((ROOT/'data/acdata_info.json').read_text())
    data = np.load(ROOT/'data/centerline.npz')
    for obj in list(bpy.data.objects):
        if obj.name.startswith('AC_') or obj.name in ('1WALL_END','1WALL_START_END','__AC_END_CHECK'):
            bpy.data.objects.remove(obj,do_unlink=True)
        elif obj.type in ('CAMERA','LIGHT') and not obj.name.startswith('__'):
            obj.name = '__'+obj.name
    for entry in plan['empties']:
        obj = bpy.data.objects.new(entry['name'],None)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = entry['position_m']
        obj.rotation_euler = (0,0,math.radians(entry['yaw_deg']))
        obj.empty_display_type = 'ARROWS'
        obj.empty_display_size = .7
    cross_section = np.concatenate([data['sides'][1,-1,::-1],data['sides'][0,-1]])
    cross_section[:,:2] -= data['tangent'][-1]*.5
    verts,faces = [],[]
    for a,b in zip(cross_section,cross_section[1:]):
        add_box(verts,faces,a,b,.5,-.2,1.2)
    object_mesh('1WALL_END',verts,faces,bpy.data.materials['rock'])
    if 'spawn_s' in data:
        cross_section=np.concatenate([data['sides'][1,0,::-1],data['sides'][0,0]])
        cross_section[:,:2]+=data['tangent'][0]*.5
        verts,faces=[],[]
        for a,b in zip(cross_section,cross_section[1:]):add_box(verts,faces,a,b,.8,-.5,1.5)
        object_mesh('1WALL_START_END',verts,faces,bpy.data.materials['rock'])
    source = Path(os.environ.get('AC_ADDON_SOURCE',str(Path.home()/'tools/blender-assetto-corsa-tools')))
    addons = Path(bpy.utils.user_resource('SCRIPTS',path='addons',create=True))
    target = addons/'blender_assetto_corsa_tools'
    shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git'))
    bpy.utils.refresh_script_paths()
    bpy.ops.preferences.addon_enable(module=target.name)
    exporter = importlib.import_module(target.name+'.exporter')
    utilities = importlib.import_module(target.name+'.exporter.exporter_utils')
    for material in bpy.data.materials:
        for node in material.node_tree.nodes:
            if node.type == 'TEX_IMAGE':
                node.show_texture = True
        assert utilities.get_active_material_texture_slot(material)
    bpy.context.view_layer.update()
    for entry in plan['empties']:
        obj = bpy.data.objects[entry['name']]
        matrix = utilities.convert_matrix(obj.matrix_world)
        forward = matrix.to_3x3() @ Vector((0,0,1))
        yaw = math.radians(entry['yaw_deg'])
        expected = Vector((math.sin(yaw),0,math.cos(yaw)))
        assert (forward-expected).length < 1e-5
        assert (matrix.to_3x3() @ Vector((0,1,0))-Vector((0,1,0))).length < 1e-5
        assert obj.rotation_euler.x == obj.rotation_euler.y == 0
        assert entry['chunk_seam_distance_m'] >= 2
    physical_keys = {re.match(r'^\d+([A-Z]+)',obj.name)[1] for obj in bpy.data.objects if obj.type=='MESH' and re.match(r'^\d+([A-Z]+)',obj.name)}
    config = configparser.ConfigParser()
    config.read(output/'data/surfaces.ini')
    assert physical_keys == {config[section]['KEY'] for section in config.sections()}
    scene = bpy.context.scene
    i = int(np.searchsorted(data['s'],data['s'][-1]-18))
    position = np.r_[data['xy'][i],data['z'][i]+2.5]
    camera('__AC_END_CHECK',position,[*data['xy'][-1],data['z'][-1]+.8])
    scene.render.resolution_x,scene.render.resolution_y = 1280,720
    scene.render.filepath = str(ROOT/'out/preview/end_barrier.png')
    if not os.environ.get('BS_SKIP_RENDER'):bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'blend/bejaia_saket.blend'))
    counts = dict(mesh_objects=0,export_meshes=0,vertex_limit_splits=0,max_expanded_vertices_before_split=0)
    original = exporter.NodeWriter
    class MeasuredNodeWriter(original):
        def _write_mesh_node(self,obj):
            counts['mesh_objects'] += 1
            return super()._write_mesh_node(obj)

        def _split_meshes_for_vertex_limit(self,meshes):
            counts['max_expanded_vertices_before_split'] = max(counts['max_expanded_vertices_before_split'],max(len(m.vertices) for m in meshes))
            result = super()._split_meshes_for_vertex_limit(meshes)
            counts['vertex_limit_splits'] += len(result)-len(meshes)
            counts['export_meshes'] += len(result)
            return result
    exporter.NodeWriter = MeasuredNodeWriter
    settings = json.loads((ROOT/'blend/settings.json').read_text())
    warnings = []
    path = output/'bejaia_saket.kn5'
    partial = ROOT/'blend/bejaia_saket.kn5.partial'
    started = time.perf_counter()
    try:
        with partial.open('wb') as stream:
            exporter.KN5FileWriter(stream,bpy.context,settings,warnings).write()
        with partial.open('rb') as stream:
            assert stream.read(6) == b'sc6969'
        partial.replace(path)
    finally:
        exporter.NodeWriter = original
    report = dict(file=str(path.relative_to(ROOT)),bytes=path.stat().st_size,seconds=time.perf_counter()-started,blender=bpy.app.version_string,warnings=warnings,empties=len(plan['empties']),physical_keys=sorted(physical_keys),**counts)
    report['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (ROOT/'data/kn5_export_info.json').write_text(json.dumps(report,indent=2)+'\n')
    print('AC_SCENE_CHECK_OK empties=%d road_offset_m=1.5 seam_clearance_m=2 physical_keys=%s'%(len(plan['empties']),','.join(sorted(physical_keys))))
    print('FULL_KN5_OK',json.dumps(report))


if __name__ == '__main__':
    main()
