"""Attach generated landscape meshes without touching the accepted corridor."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from blender_mesh import object_mesh


def corridor_digest():
    digest=hashlib.sha256()
    for obj in sorted(bpy.data.objects,key=lambda o:o.name):
        if obj.type!='MESH' or obj.name.startswith(('LAND_','1GRASS_LAND_')) or obj.name=='DECOR_SEA':continue
        digest.update(obj.name.encode())
        digest.update(np.asarray(obj.matrix_world,dtype='<f4').tobytes())
        digest.update(np.asarray([v.co[:] for v in obj.data.vertices],dtype='<f4').tobytes())
        for polygon in obj.data.polygons:digest.update(np.asarray(polygon.vertices[:],dtype='<i4').tobytes())
    return digest.hexdigest()


def main():
    before=corridor_digest()
    base_triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith(('LAND_','1GRASS_LAND_')) and o.name!='DECOR_SEA')
    for obj in list(bpy.data.objects):
        if obj.name.startswith(('LAND_','1GRASS_LAND_')) or obj.name=='DECOR_SEA':bpy.data.objects.remove(obj,do_unlink=True)
    data=np.load(ROOT/'data/landscape.npz');keys=data['keys']
    all_faces=data['faces'];tri=data['vertices'][all_faces]
    face_normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    normals=np.zeros_like(data['vertices'])
    np.add.at(normals,all_faces.ravel(),np.repeat(face_normals,3,axis=0))
    normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    groups,labels=np.unique(keys,axis=0,return_inverse=True)
    counts=dict(physical=0,visual=0);maximum=0
    for i,key in enumerate(groups):
        faces=data['faces'][labels==i]
        indices,inverse=np.unique(faces,return_inverse=True)
        physical=bool(key[0]);material='rock' if key[-1] else 'grass'
        name=('1GRASS_LAND_' if physical else 'LAND_')+f'{i:04d}_{material}'
        obj=object_mesh(name,data['vertices'][indices],inverse.reshape(-1,3).tolist(),bpy.data.materials[material])
        for poly in obj.data.polygons:poly.use_smooth=True
        obj.data.use_auto_smooth=True
        obj.data.normals_split_custom_set_from_vertices(normals[indices].tolist())
        counts['physical' if physical else 'visual']+=1;maximum=max(maximum,len(indices))
    sea=object_mesh('DECOR_SEA',data['sea_vertices'],data['sea_faces'].tolist(),bpy.data.materials['water'])
    for i,loop in enumerate(sea.data.uv_layers.active.data):
        co=sea.data.vertices[sea.data.loops[i].vertex_index].co
        loop.uv=(co.x/4,co.y/4)
    assert corridor_digest()==before,'Original road/ribbon/decor geometry changed'
    settings_path=ROOT/'blend/settings.json';settings=json.loads(settings_path.read_text())
    for key in list(settings['nodes']):
        if key.startswith(('LAND_','1GRASS_LAND_')):del settings['nodes'][key]
    for obj in bpy.data.objects:
        if obj.name.startswith(('LAND_','1GRASS_LAND_')) or obj.name=='DECOR_SEA':settings['nodes'][obj.name]=dict(lodIn=0,lodOut=60000)
    settings_path.write_text(json.dumps(settings,indent=2)+'\n')
    info_path=ROOT/'data/landscape_info.json';info=json.loads(info_path.read_text())
    info.update(corridor_sha256_before_and_after=before,physical_meshes=counts['physical'],visual_meshes=counts['visual'],max_object_vertices=maximum,
        before_triangles=base_triangles+json.loads((ROOT/'data/decor_info.json').read_text())['sea_triangles'],
        after_triangles=base_triangles+len(data['faces'])+len(data['sea_faces']))
    info_path.write_text(json.dumps(info,indent=2)+'\n')
    from blender_materials import main as export
    export()
    print('LANDSCAPE_SCENE_OK '+json.dumps(counts)+' corridor_geometry_unchanged=True')


if __name__=='__main__':main()
