"""Small-leaf CC0 shrub preparation; original downloads stay untouched."""
import bpy
import math
import numpy as np
from pilot_common import ASSETS


def radial_cluster(obj,count):
    if not obj.users_collection:bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    for index in range(1,count):
        branch=obj.copy()
        bpy.context.collection.objects.link(branch)
        branch.rotation_euler.z=index*2*math.pi/count
        scale=1-.05*(index%3)
        branch.scale=(scale,scale,scale)
        branch.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.join()
    bpy.context.collection.objects.unlink(obj)
    return obj


def load_shrubs():
    path=ASSETS/'searsia_lucida/searsia_lucida_1k.blend'
    wanted=('searsia_lucida_e_LOD2','searsia_lucida_f_LOD2','searsia_lucida_c_LOD2')
    with bpy.data.libraries.load(str(path),link=False) as (a,b):
        if not all(n in a.objects for n in wanted):raise ValueError('Unexpected CC0 shrub source')
        b.objects=list(wanted)
    shrubs=[]
    for index,obj in enumerate(b.objects):
        obj.parent=None
        obj.matrix_world.identity()
        obj.data=obj.data.copy()
        points=np.asarray([v.co[:] for v in obj.data.vertices])
        origin=np.r_[(points[:,:2].min(axis=0)+points[:,:2].max(axis=0))/2,points[:,2].min()]
        for vertex in obj.data.vertices:vertex.co=np.asarray(vertex.co)-origin
        for modifier in list(obj.modifiers):obj.modifiers.remove(modifier)
        if index<2:
            obj.name=f'PH_shrub_{index+1:02d}'
            bpy.context.collection.objects.link(obj)
            triangles=sum(len(p.vertices)-2 for p in obj.data.polygons)
            if triangles>3000:
                modifier=obj.modifiers.new('Shrub near budget','DECIMATE')
                modifier.ratio=3000/triangles
                modifier.use_collapse_triangulate=True
                bpy.context.view_layer.objects.active=obj
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            shrubs.append(radial_cluster(obj,3))
        else:
            obj.name='PH_shrub_canopy'
            canopy=radial_cluster(obj,7)
    return shrubs,canopy
