"""Replace block foliage, preserving terrain, road and non-vegetation props."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from blender_mesh import object_mesh
from blender_decor import prototype as old_prototype
from foliage import prototype,TINTS,mesh_batch_key


def replaced(obj):
    return obj.name.startswith('DECOR_VEG_') or (obj.name.startswith('DECOR_') and obj.name.endswith(('_bark','_pine_foliage','_olive_foliage','_maquis')))


def digest():
    h=hashlib.sha256()
    for obj in sorted(bpy.data.objects,key=lambda o:o.name):
        if obj.type not in ('MESH','EMPTY') or replaced(obj):continue
        h.update(obj.name.encode());h.update(np.asarray(obj.matrix_world,dtype='<f4').tobytes())
        if obj.type=='MESH':
            h.update(np.asarray([v.co[:] for v in obj.data.vertices],dtype='<f4').tobytes())
            for p in obj.data.polygons:h.update(np.asarray(p.vertices[:],dtype='<i4').tobytes())
    return h.hexdigest()


def main():
    before=digest()
    for obj in list(bpy.data.objects):
        if replaced(obj):
            mesh=obj.data
            bpy.data.objects.remove(obj,do_unlink=True)
            if mesh.users==0:bpy.data.meshes.remove(mesh)
    # Old trunks were merged with pole trunks and building joinery by material.
    data=np.load(ROOT/'data/centerline.npz');plan=np.load(ROOT/'data/decor_plan.npz')
    seams=np.unique(np.r_[0,np.searchsorted(data['s'],np.arange(400,data['s'][-1],400)),len(data['s'])-1]);batches={}
    for entry in plan['placements']:
        kind,variant=map(int,entry[:2])
        if kind not in (3,5):continue
        xyz,yaw,scale=entry[2:5],entry[5],entry[6];chunk=int(np.searchsorted(data['s'][seams],entry[8],side='right')-1)
        rotation=np.array([[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]])
        foundation=(entry[11]-xyz[2]-.15)/scale if kind==5 else -.1
        groups=old_prototype(kind,variant,foundation)
        if 'bark' not in groups:continue
        vertices,faces=groups['bark'];out_v,out_f=batches.setdefault(chunk,([],[]));start=len(out_v)
        out_v.extend((np.asarray(vertices)*scale@rotation.T+xyz).tolist());out_f.extend([tuple(start+k for k in f) for f in faces])
    for chunk,(v,f) in batches.items():object_mesh(f'DECOR_{chunk:03d}_bark',v,f,bpy.data.materials['bark'])
    plants=np.load(ROOT/'data/vegetation.npz')['plants'];batches={};prototypes={}
    for p in plants:
        kind,variant=int(p[0]),int(p[1]);yaw,scale=p[5],p[6];rotation=np.array([[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]])
        if kind>=5:
            z=p[9:12];x=rotation[:,0]-z*np.dot(rotation[:,0],z);x/=np.linalg.norm(x);rotation=np.column_stack([x,np.cross(z,x),z])
        for lod in (0,1):
            key=(kind,variant,lod)
            if key not in prototypes:prototypes[key]=prototype(kind,variant,lod,quality=os.environ.get('BS_KN5_VEGETATION')!='1')
            groups=prototypes[key]
            for material,mesh in groups.items():
                if not mesh.faces:continue
                name='bark' if material=='bark' else ('veg_impostor' if lod else 'veg_canopy')+TINTS[int(p[7])]
                key=mesh_batch_key(batches,(int(p[8]),lod,name),len(mesh.vertices))
                v,f,uv,n=batches.setdefault(key,([],[],[],[]));start=len(v)
                v.extend((np.asarray(mesh.vertices)*scale@rotation.T+p[2:5]).tolist());f.extend([tuple(start+k for k in face) for face in mesh.faces]);uv.extend(mesh.uv);n.extend((np.asarray(mesh.normals)@rotation.T).tolist())
    counts={0:0,1:0}
    for (chunk,lod,material,part),(v,f,uv,n) in sorted(batches.items()):
        name=f'DECOR_VEG_L{lod}_{chunk:03d}_{part:02d}_{material}'
        if material not in bpy.data.materials:bpy.data.materials.new(material)
        obj=object_mesh(name,v,f,bpy.data.materials[material]);obj.data.use_auto_smooth=True
        for p in obj.data.polygons:
            p.use_smooth=True
            for loop in p.loop_indices:obj.data.uv_layers.active.data[loop].uv=uv[obj.data.loops[loop].vertex_index]
        obj.data.normals_split_custom_set_from_vertices(n);counts[lod]+=len(f)
    assert digest()==before,'Non-vegetation geometry changed'
    settings_path=ROOT/'blend/settings.json';settings=json.loads(settings_path.read_text())
    settings['nodes']['DECOR_VEG_L0_*']=dict(lodIn=0,lodOut=150)
    settings['nodes']['DECOR_VEG_L1_*']=dict(lodIn=150,lodOut=600)
    settings_path.write_text(json.dumps(settings,indent=2)+'\n')
    total=sum(sum(len(p.vertices)-2 for p in obj.data.polygons) for obj in bpy.data.objects if obj.type=='MESH')
    if os.environ.get('BS_KN5_VEGETATION')=='1':assert total<1600000,f'Vegetation exceeds total triangle budget: {total}'
    path=ROOT/'data/vegetation_info.json';info=json.loads(path.read_text());info.update(after_triangles=total,lod0_triangles=counts[0],lod1_triangles=counts[1],nonvegetation_sha256_before_and_after=before,vegetation_objects=len(batches),max_vegetation_vertices=max(len(v[0]) for v in batches.values()))
    path.write_text(json.dumps(info,indent=2)+'\n')
    from blender_materials import main as export,apply
    if os.environ.get('BS_KN5_VEGETATION')!='1':
        bpy.ops.preferences.addon_enable(module='blender_assetto_corsa_tools')
        materials_path=ROOT/'data/materials_info.json';materials=json.loads(materials_path.read_text());apply(materials)
        (ROOT/'data/research_cache/vegetation_preview_materials.json').write_text(json.dumps(materials))
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'data/research_cache/vegetation_preview.blend'),compress=True)
        for obj in list(bpy.data.objects):
            if obj.name.startswith('DECOR_VEG_'):
                mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
                if not mesh.users:bpy.data.meshes.remove(mesh)
        for name in list(materials['materials']):
            if name.startswith(('veg_canopy','veg_impostor')):
                del materials['materials'][name];materials['textures'].pop(name+'.dds',None)
                bpy.data.materials.remove(bpy.data.materials[name],do_unlink=True)
        materials['dds_gpu_bytes']=sum(v['gpu_bytes'] for v in materials['textures'].values())
        materials_path.write_text(json.dumps(materials,indent=2)+'\n')
    export()
    info['preview_triangles']=total
    info['after_triangles']=sum(sum(len(p.vertices)-2 for p in obj.data.polygons) for obj in bpy.data.objects if obj.type=='MESH')
    info['kn5_vegetation_objects']=sum(obj.name.startswith('DECOR_VEG_') for obj in bpy.data.objects)
    info['mode']='KN5 fallback' if os.environ.get('BS_KN5_VEGETATION')=='1' else 'TreeFX + GrassFX'
    info['wind']='deferred for KN5 fallback; native TreeFX height-driven wind exists in source, runtime unverified'
    path.write_text(json.dumps(info,indent=2)+'\n')
    print('VEGETATION_SCENE_OK '+json.dumps(info))


if __name__=='__main__':main()
