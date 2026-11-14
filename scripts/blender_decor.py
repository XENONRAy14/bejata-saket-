"""Light procedural decor, merged by actual terrain chunk and material."""
import json
import math
import os
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from blender_mesh import object_mesh, camera
from blender_acdata import main as export_scene

MATERIALS = ('bark','pine_foliage','olive_foliage','maquis','plaster','sand','water','marker_red')


def box(vertices,faces,center,size):
    start = len(vertices)
    x,y,z = center
    a,b,c = np.asarray(size)/2
    vertices.extend([(x-a,y-b,z-c),(x+a,y-b,z-c),(x+a,y+b,z-c),(x-a,y+b,z-c),(x-a,y-b,z+c),(x+a,y-b,z+c),(x+a,y+b,z+c),(x-a,y+b,z+c)])
    faces.extend([tuple(start+i for i in face) for face in ((3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7))])


def blob(vertices,faces,center,size):
    start = len(vertices)
    points = [[0,0,-1]]
    for latitude in (-math.pi/6,math.pi/6):
        points.extend([[math.cos(angle)*math.cos(latitude),math.sin(angle)*math.cos(latitude),math.sin(latitude)] for angle in np.arange(6)*math.pi/3])
    points.append([0,0,1])
    vertices.extend((np.asarray(points)*size+center).tolist())
    for i in range(6):
        j = (i+1)%6
        faces.extend([tuple(start+k for k in face) for face in ((0,1+j,1+i),(1+i,1+j,7+j,7+i),(7+i,7+j,13))])


def trunk(vertices,faces,height,radius,twist=False):
    start = len(vertices)
    for level in range(3):
        for angle in np.arange(6)*math.pi/3+level*(.3 if twist else 0):
            vertices.append([math.cos(angle)*radius*(1-.2*level)+(.13*level if twist else 0),math.sin(angle)*radius*(1-.2*level),height*level/2-.1])
    for level in range(2):
        for i in range(6):
            j = (i+1)%6
            faces.append(tuple(start+k for k in (level*6+i,level*6+j,(level+1)*6+j,(level+1)*6+i)))
    faces.extend([tuple(start+i for i in reversed(range(6))),tuple(start+12+i for i in range(6))])


def prototype(kind,variant,foundation=-.1):
    groups = {}
    def mesh(material):
        return groups.setdefault(material,([],[]))
    if kind==0:
        trunk(*mesh('bark'),5+variant*.4,.18)
        blob(*mesh('pine_foliage'),[0,0,5.5+variant*.4],[2.9,2.6,1.05])
        blob(*mesh('pine_foliage'),[.25,0,6.6+variant*.4],[2.2,2.,.95])
        if variant==2:
            blob(*mesh('pine_foliage'),[0,0,7.8],[1.3,1.4,.75])
    elif kind==1:
        trunk(*mesh('bark'),2.6,.27,True)
        for center in ([-.65,0,3.1],[.7,.1,3.3],[0,-.45,3.9+variant*.15]):
            blob(*mesh('olive_foliage'),center,[1.6,1.65,1.15])
    elif kind==2:
        blob(*mesh('maquis'),[0,0,.65],[1.2,1.05,.8])
        if variant:
            center,size = ([.35,-.1,.8],[.75,.8,.9]) if variant==1 else ([-.35,.25,.85],[.9,.65,.95])
            blob(*mesh('maquis'),center,size)
    elif kind==3:
        material = 'plaster' if variant else 'bark'
        trunk(*mesh(material),6.8,.15)
        box(*mesh(material),[0,0,6.2],[2.1,.16,.18])
        for x in (-.85,.85):
            box(*mesh('plaster'),[x,0,6.4],[.15,.15,.25])
    elif kind==4:
        box(*mesh('plaster'),[0,0,.4],[.55,.45,.9])
        box(*mesh('marker_red'),[0,0,.9],[.56,.46,.18])
    else:
        height = 3.6+variant*.9
        box(*mesh('plaster'),[0,0,(foundation+height)/2],[6,5,height-foundation])
        box(*mesh('plaster'),[0,0,height],[6.2,5.2,.18])
        box(*mesh('bark'),[0,-2.51,1.1],[.9,.04,2.2])
        for x in (-1.8,1.8):
            box(*mesh('bark'),[x,-2.51,2.2],[.8,.04,1.1])
    return groups


def main():
    for obj in list(bpy.data.objects):
        if obj.name.startswith(('DECOR_','__DECOR_')):
            mesh = obj.data if obj.type=='MESH' else None
            bpy.data.objects.remove(obj,do_unlink=True)
            if mesh is not None and mesh.users==0:
                bpy.data.meshes.remove(mesh)
    for name in MATERIALS:
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        shader = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        shader.inputs['Roughness'].default_value = .25 if name=='water' else .9
        node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image = bpy.data.images.load(str(ROOT/'textures'/f'{name}.png'),check_existing=True)
        mat.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])
        output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(shader.outputs['BSDF'],output.inputs['Surface'])
    data = np.load(ROOT/'data/centerline.npz')
    plan = np.load(ROOT/'data/decor_plan.npz')
    seams = np.unique(np.r_[0,np.searchsorted(data['s'],np.arange(400,data['s'][-1],400)),len(data['s'])-1])
    batches = {}
    for entry in plan['placements']:
        kind,variant = map(int,entry[:2])
        xyz,yaw,scale = entry[2:5],entry[5],entry[6]
        chunk = int(np.searchsorted(data['s'][seams],entry[8],side='right')-1)
        rotation = np.array([[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]])
        foundation = (entry[11]-xyz[2]-.15)/scale if kind==5 else -.1
        for material,(vertices,faces) in prototype(kind,variant,foundation).items():
            out_vertices,out_faces = batches.setdefault((chunk,material),([],[]))
            start = len(out_vertices)
            out_vertices.extend((np.asarray(vertices)*scale@rotation.T+xyz).tolist())
            out_faces.extend([tuple(start+i for i in face) for face in faces])
    for (chunk,material),(vertices,faces) in sorted(batches.items()):
        object_mesh(f'DECOR_{chunk:03d}_{material}',vertices,faces,bpy.data.materials[material])
    sea = [Vector(p) for p in plan['sea']]
    faces = list(tessellate_polygon([sea]))
    faces = [tuple(reversed(f)) if np.cross(np.asarray(sea[f[1]])-sea[f[0]],np.asarray(sea[f[2]])-sea[f[0]])[2]<0 else f for f in faces]
    object_mesh('DECOR_SEA',plan['sea'],faces,bpy.data.materials['water'])
    object_mesh('DECOR_BEACH',plan['beach'],plan['beach_faces'].tolist(),bpy.data.materials['sand'])
    meshes = [obj for obj in bpy.data.objects if obj.type=='MESH' and obj.name.startswith('DECOR_')]
    triangles = sum(sum(len(p.vertices)-2 for p in obj.data.polygons) for obj in meshes)
    assert triangles <= 150000, f'Decor budget exceeded: {triangles}'
    assert all(len(obj.data.vertices)<65000 for obj in meshes)
    info = json.loads((ROOT/'data/decor_info.json').read_text())
    info.update(triangles_added=triangles,mesh_objects_added=len(meshes),vertices_added=sum(len(obj.data.vertices) for obj in meshes),max_object_vertices=max(len(obj.data.vertices) for obj in meshes),sea_triangles=len(faces),beach_triangles=len(plan['beach_faces']))
    (ROOT/'data/decor_info.json').write_text(json.dumps(info,indent=2)+'\n')
    scene = bpy.context.scene
    scene.render.resolution_x,scene.render.resolution_y = 1400,1400
    lower,upper = data['xy'].min(0),data['xy'].max(0)
    midpoint = (lower+upper)/2
    camera('__DECOR_TOP', [*midpoint,18000],[*midpoint,0],max(upper-lower)*1.12)
    scene.render.filepath = str(ROOT/'out/preview/top.png')
    if not os.environ.get('BS_SKIP_RENDER'):bpy.ops.render.render(write_still=True)
    scene.render.resolution_x,scene.render.resolution_y = 1280,720
    for fraction in (.1,.4,.7,.95):
        i = int(np.searchsorted(data['s'],data['s'][-1]*fraction))
        j = int(np.searchsorted(data['s'],min(data['s'][-1],data['s'][i]+35)))
        camera(f'__DECOR_ROAD_{int(fraction*100)}',[*data['xy'][i],data['z'][i]+1.2],[*data['xy'][j],data['z'][j]+1.2])
        scene.render.filepath = str(ROOT/f'out/preview/road_{int(fraction*100):02d}.png')
        if not os.environ.get('BS_SKIP_RENDER'):bpy.ops.render.render(write_still=True)
    houses = plan['placements'][(plan['placements'][:,0]==5)&(plan['placements'][:,8]<2000)]
    town_chainage = float(houses[len(houses)//2,8]-45)
    for label,chainage in [('town',town_chainage),('saket',float(data['s'][-1]-340))]:
        i = int(np.searchsorted(data['s'],chainage))
        j = int(np.searchsorted(data['s'],chainage+50))
        target = np.r_[data['xy'][j],data['z'][i]+1.6]
        if label=='saket':
            target[:2] += np.array([0,18])
        camera(f'__DECOR_{label.upper()}',[*data['xy'][i],data['z'][i]+1.6],target)
        scene.render.filepath = str(ROOT/f'out/preview/decor_{label}.png')
        if not os.environ.get('BS_SKIP_RENDER'):bpy.ops.render.render(write_still=True)
    export_scene()


if __name__ == '__main__':
    main()
