"""Optional, matched v1/v2 Cycles CPU comparisons; no scene/export changes."""
from pathlib import Path
import json
import os
import sys

import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from blender_mesh import camera


def main():
    label=sys.argv[sys.argv.index('--')+1]
    selected=sys.argv[sys.argv.index('--')+2:]
    if label not in ('before','after'):raise ValueError('Expected before or after')
    output=Path(os.environ.get('BS_COMPARISON_DIR',str(ROOT/'out/preview/v2_materials')))/label;output.mkdir(parents=True,exist_ok=True)
    for image in bpy.data.images:
        if image.source=='FILE':
            source=Path(bpy.path.abspath(image.filepath))
            if not source.exists():
                candidate=ROOT/'textures'/source.name
                if not candidate.exists():candidate=ROOT/'textures/v2'/source.name
                if not candidate.exists():raise FileNotFoundError(source)
                image.filepath=str(candidate)
    if label=='after':
        bpy.utils.refresh_script_paths()
        bpy.ops.preferences.addon_enable(module='blender_assetto_corsa_tools')
        from blender_materials import material_nodes
        info=json.loads((ROOT/'data/materials_info.json').read_text())
        if os.environ.get('BS_VEGETATION_PREVIEW') and (ROOT/'data/research_cache/vegetation_preview_materials.json').exists():
            info=json.loads((ROOT/'data/research_cache/vegetation_preview_materials.json').read_text())
        for name,spec in info['materials'].items():material_nodes(bpy.data.materials[name],spec)
    scene=bpy.context.scene;scene.render.engine='CYCLES'
    scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=True
    scene.cycles.transparent_max_bounces=64
    for obj in bpy.data.objects:
        if obj.name.startswith('DECOR_VEG_L1_'):obj.hide_render=True
    scene.render.threads_mode='FIXED';scene.render.threads=8
    scene.render.resolution_x,scene.render.resolution_y=1280,720
    scene.render.resolution_percentage=100
    data=np.load(ROOT/'data/centerline.npz');plan=np.load(ROOT/'data/decor_plan.npz')
    views=[]
    for fraction in (.1,.4,.7,.95):
        i=int(np.searchsorted(data['s'],data['s'][-1]*fraction));j=int(np.searchsorted(data['s'],min(data['s'][-1],data['s'][i]+35)))
        views.append((f'road_{int(fraction*100):02d}',[*data['xy'][i],data['z'][i]+1.2],[*data['xy'][j],data['z'][j]+1.2]))
    houses=plan['placements'][(plan['placements'][:,0]==5)&(plan['placements'][:,8]<2000)]
    for name,chainage in [('town',float(houses[len(houses)//2,8]-45)),('saket',float(data['s'][-1]-340))]:
        i=int(np.searchsorted(data['s'],chainage));j=int(np.searchsorted(data['s'],chainage+50))
        point=np.r_[data['xy'][j],data['z'][i]+1.6]
        if name=='saket':point[:2]+=np.array([0,18])
        views.append(('decor_'+name,[*data['xy'][i],data['z'][i]+1.6],point))
    terrain=bool(os.environ.get('BS_TERRAIN_PREVIEW'))
    if os.environ.get('BS_VEGETATION_PREVIEW'):
        from foliage import SIZES
        plants=np.load(ROOT/'data/vegetation.npz')['plants']
        selected_plants=plants[(plants[:,0]==2)&(plants[:,12]<35)&(plants[:,13]<15)]
        if not len(selected_plants):selected_plants=plants[plants[:,0]<3]
        plant=selected_plants[len(selected_plants)//2];point=plant[2:5];nearest=np.argmin(np.linalg.norm(data['xy']-point[:2],axis=1))
        origin=np.r_[data['xy'][nearest],data['z'][nearest]+2.2]
        views.append(('trees_closeup',origin,point+np.array([0,0,SIZES[int(plant[0])][1]*plant[6]*.55])))
        if os.environ.get('BS_ROADSIDE_PREVIEW'):
            heroes=plants[(plants[:,0]<3)&(plants[:,6]>1.3)]
            if not len(heroes):heroes=plants[plants[:,0]<3]
            hero=heroes[len(heroes)//2];point=hero[2:5];nearest=np.argmin(np.linalg.norm(data['xy']-point[:2],axis=1))
            inward=data['xy'][nearest]-point[:2];inward/=np.linalg.norm(inward)
            views.append(('hero_tree',point+np.r_[inward*24,3.2],point+[0,0,SIZES[int(hero[0])][1]*hero[6]*.63]))
            nearest=int(np.searchsorted(data['s'],data['s'][-1]*.4))
            i=max(0,nearest-12);j=min(len(data['s'])-1,nearest+16)
            higher=int(np.argmax(data['sides'][:,j,-1,2]));inward=data['xy'][j]-data['sides'][higher,j,2,:2];inward/=np.linalg.norm(inward)
            views.append(('low_sun',[*data['xy'][i],data['z'][i]+1.6],[*data['xy'][j],data['z'][j]+1.6]))
            shadow_direction=np.r_[inward*np.cos(np.radians(20)),-np.sin(np.radians(20))]
    if os.environ.get('BS_ROADSIDE_PREVIEW'):
        info=json.loads((ROOT/'data/roadside_info.json').read_text())
        wall=min(info['walls'],key=lambda w:abs(w['chainage_m']-data['s'][-1]*.4))
        point=np.asarray(wall['center']);tangent=np.asarray(wall['tangent'])
        nearest=np.argmin(np.linalg.norm(data['xy']-point[:2],axis=1));inward=data['xy'][nearest]-point[:2];inward/=np.linalg.norm(inward)
        origin=point+np.r_[inward*5-tangent*8,2.0]
        views.append(('wall_closeup',origin,point+[0,0,.7]))
        dangerous=np.argwhere(data['guard'])
        side,index=dangerous[len(dangerous)//2];point=data['sides'][side,index,2];tangent=data['tangent'][index]
        inward=data['xy'][index]-point[:2];inward/=np.linalg.norm(inward)
        views.append(('guardrail_closeup',point+np.r_[inward*2-tangent*7,1.6],point+np.r_[tangent*12,.5]))
    if terrain:
        midpoint=(data['xy'].min(0)+data['xy'].max(0))/2
        views.insert(0,('top',[*midpoint,45000],[*midpoint,0]))
        landscape=np.load(ROOT/'data/landscape.npz')['vertices']
        for name,chainage,offset in [('boulimat',18500,(550,-550)),('city',1000,(850,-650))]:
            i=int(np.searchsorted(data['s'],chainage));xy=data['xy'][i]+offset
            nearby=landscape[np.linalg.norm(landscape[:,:2]-xy,axis=1)<1000,2]
            elevation=float(nearby.max()+500) if len(nearby) else 1200
            views.append(('elevated_'+name,[*xy,elevation],[*data['xy'][i],data['z'][i]]))
    views.sort(key=lambda view:view[0]=='low_sun')
    if set(selected)-{view[0] for view in views}:raise ValueError('Unknown view')
    for name,origin,target in views:
        if selected and name not in selected:continue
        view=camera('__COMPARISON_'+name,origin,target,32000 if name=='top' else None)
        if name=='hero_tree':view.data.lens=28
        if terrain:view.data.clip_end=100000
        if name=='low_sun':
            from mathutils import Vector
            for light in bpy.data.objects:
                if light.type=='LIGHT' and light.data.type=='SUN':
                    light.rotation_euler=Vector(shadow_direction).to_track_quat('-Z','Y').to_euler();light.data.energy=3
            if scene.world and scene.world.use_nodes:
                for node in scene.world.node_tree.nodes:
                    if node.type=='BACKGROUND':node.inputs['Strength'].default_value=.18
        scene.render.filepath=str(output/(name+'.png'))
        bpy.ops.render.render(write_still=True)
    print(f'COMPARISON_RENDER_OK side={label} views={len(selected) if selected else len(views)} engine=CYCLES device=CPU samples=16 denoising=True')


if __name__=='__main__':main()
