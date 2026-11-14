"""Blender-only scene construction from the pure-Python metric arrays."""
import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = .85 if name != 'metal' else .36
    shader.inputs['Metallic'].default_value = .65 if name == 'metal' else 0
    image = bpy.data.images.load(str(ROOT/'textures'/f'{name}.png'))
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = image
    node.interpolation = 'Linear'
    mat.node_tree.links.new(node.outputs['Color'], shader.inputs['Base Color'])
    mat.diffuse_color = {'asphalt':(.18,.19,.20,1), 'grass':(.3,.4,.16,1), 'gravel':(.48,.43,.32,1), 'rock':(.4,.36,.28,1), 'metal':(.55,.6,.63,1), 'kerb':(.65,.62,.5,1)}[name]
    return mat


def object_mesh(name, vertices, faces, mat, uv=None):
    if not faces:
        return None
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(np.asarray(vertices).tolist(), [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(mat)
    layer = mesh.uv_layers.new()
    for poly in mesh.polygons:
        for loop in poly.loop_indices:
            vi = mesh.loops[loop].vertex_index
            co = mesh.vertices[vi].co
            layer.data[loop].uv = uv[vi] if uv is not None else (co.x/4, co.z/4+co.y/4)
    if len(mesh.vertices) >= 65000:
        raise AssertionError(f'Oversized object {name}')
    return obj


def strip(name, grid, mat, s, across, reverse=False):
    count, cols, _ = grid.shape
    faces = []
    for i in range(count-1):
        for j in range(cols-1):
            a, b = i*cols+j, (i+1)*cols+j
            # Explicit triangles allow checking the actual exported winding.
            pair = [(a,b,b+1),(a,b+1,a+1)]
            faces.extend([tuple(reversed(f)) if reverse else f for f in pair])
    uv = [(float(across[j]), float(s[i]/7)) for i in range(count) for j in range(cols)]
    obj = object_mesh(name, grid.reshape(-1,3), faces, mat, uv)
    if obj and any(p.normal.z <= 0 for p in obj.data.polygons):
        raise AssertionError(f'Folded or downward strip {name}')
    return obj


def add_box(verts, faces, a, b, width, low, high):
    a, b = np.asarray(a), np.asarray(b)
    delta = b[:2]-a[:2]
    normal = np.array([-delta[1],delta[0]])/np.linalg.norm(delta)*width/2
    corners = [a[:2]-normal, b[:2]-normal, b[:2]+normal, a[:2]+normal]
    start = len(verts)
    for zoff in (low, high):
        for i, p in enumerate(corners):
            verts.append([*p, (a[2] if i in (0,3) else b[2])+zoff])
    for f in [(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]:
        faces.append(tuple(start+k for k in f))


def camera(name, position, target, ortho=None):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = Vector(position)
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    data.clip_start = .08
    data.clip_end = 40000
    data.lens = 24
    if ortho:
        data.type = 'ORTHO'
        data.ortho_scale = ortho
    bpy.context.scene.camera = obj
    return obj


def main():
    data = np.load(ROOT/'data/centerline.npz')
    xy, z, s = data['xy'], data['z'], data['s']
    sides, normal, tangent = data['sides'], data['normal'], data['tangent']
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for old in list(bpy.data.materials):
        bpy.data.materials.remove(old)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    mats = {n:material(n) for n in ('asphalt','grass','gravel','rock','metal','kerb')}
    chunk_ends = np.unique(np.r_[0,np.searchsorted(s,np.arange(400,s[-1],400)),len(s)-1]).tolist()
    for chunk, (a,b) in enumerate(zip(chunk_ends,chunk_ends[1:])):
        subset = slice(a,b+1)
        road = np.stack([sides[1,subset,0], sides[0,subset,0]], axis=1)
        strip(f'1ROAD_{chunk:03d}', road, mats['asphalt'], s[subset], [0,1])
        for side, letter in enumerate(('L','R')):
            grid = sides[side,subset]
            strip(f'1KERB_{chunk:03d}_{letter}', grid[:,:2], mats['kerb'], s[subset], [0,1], side==1)
            strip(f'1GRAVEL_{chunk:03d}_{letter}', grid[:,1:3], mats['gravel'], s[subset], [0,1], side==1)
            strip(f'1GRASS_{chunk:03d}_{letter}', grid[:,2:], mats['grass'], s[subset], [0,.2,.4,.65,1], side==1)
            verts, faces = [], []
            cut_verts, cut_faces = [], []
            for i in range(a,b):
                if data['guard'][side,i] and data['guard'][side,i+1]:
                    p = sides[side,i,2].copy()
                    q = sides[side,i+1,2].copy()
                    add_box(verts,faces,p,q,.16,.65,.95)
                    if i == a or int(s[i]/4) != int(s[i-1]/4):
                        pa, pb = p.copy(),p.copy()
                        pa[:2] -= tangent[i]*.07
                        pb[:2] += tangent[i]*.07
                        add_box(verts,faces,pa,pb,.12,-.08,.95)
                if data['cut'][side,i] and data['cut'][side,i+1]:
                    # Cut-face toe shares the shoulder edge, leaning into the terrain.
                    start = len(cut_verts)
                    for j in (i,i+1):
                        toe = sides[side,j,2].copy()
                        top = sides[side,j,3].copy()
                        top[2] = max(toe[2]+.5, sides[side,j,4,2])
                        cut_verts.extend([toe.tolist(),top.tolist()])
                    face = (start,start+2,start+3,start+1)
                    cut_faces.append(face if side == 0 else tuple(reversed(face)))
            object_mesh(f'1WALL_GUARD_{chunk:03d}_{letter}',verts,faces,mats['metal'])
            object_mesh(f'1WALL_CUT_{chunk:03d}_{letter}',cut_verts,cut_faces,mats['rock'])
    meshes = [o for o in scene.objects if o.type == 'MESH']
    metrics = json.loads((ROOT/'data/geometry_info.json').read_text())
    metrics.update(mesh_objects=len(meshes), vertices=sum(len(o.data.vertices) for o in meshes), triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes), max_object_vertices=max(len(o.data.vertices) for o in meshes), downward_strip_triangles=0)
    (ROOT/'data/geometry_info.json').write_text(json.dumps(metrics,indent=2)+'\n')
    scene.world.color = (.4,.5,.6)
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.52,.66,.78,1)
    background.inputs['Strength'].default_value = .65
    sun_data = bpy.data.lights.new('Sun','SUN')
    sun = bpy.data.objects.new('Sun',sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (.45,-.35,-.5)
    sun_data.energy = 3
    sun_data.angle = .15
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.use_gtao = True
    scene.eevee.gtao_distance = 3
    scene.eevee.taa_render_samples = 32
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'Medium High Contrast'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    preview = ROOT/'out/preview'
    bounds_min = xy.min(axis=0)
    bounds_max = xy.max(axis=0)
    midpoint = (bounds_min+bounds_max)/2
    extent = max(bounds_max-bounds_min)*1.12
    camera('Top', [*midpoint,18000], [*midpoint,0], extent)
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1400
    scene.render.filepath = str(preview/'top.png')
    if not os.environ.get('BS_SKIP_RENDER'):bpy.ops.render.render(write_still=True)
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    for fraction in (.1,.4,.7,.95):
        i = int(np.searchsorted(s,s[-1]*fraction))
        j = int(np.searchsorted(s,min(s[-1],s[i]+35)))
        camera(f'Road_{int(fraction*100):02d}', [*xy[i],z[i]+1.2], [*xy[j],z[j]+1.2])
        scene.render.filepath = str(preview/f'road_{int(fraction*100):02d}.png')
        if not os.environ.get('BS_SKIP_RENDER'):bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'blend/bejaia_saket.blend'))
    print('MESH_OK',json.dumps(metrics))


if __name__ == '__main__':
    main()
