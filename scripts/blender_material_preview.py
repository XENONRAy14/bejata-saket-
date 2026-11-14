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
    if set(selected)-{'road_10','road_40','road_70','road_95','decor_town','decor_saket'}:raise ValueError('Unknown view')
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
        for name,spec in info['materials'].items():material_nodes(bpy.data.materials[name],spec)
    scene=bpy.context.scene;scene.render.engine='CYCLES'
    scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=True
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
    if terrain:
        midpoint=(data['xy'].min(0)+data['xy'].max(0))/2
        views.insert(0,('top',[*midpoint,45000],[*midpoint,0]))
        landscape=np.load(ROOT/'data/landscape.npz')['vertices']
        for name,chainage,offset in [('boulimat',18500,(550,-550)),('city',1000,(850,-650))]:
            i=int(np.searchsorted(data['s'],chainage));xy=data['xy'][i]+offset
            nearby=landscape[np.linalg.norm(landscape[:,:2]-xy,axis=1)<1000,2]
            elevation=float(nearby.max()+500) if len(nearby) else 1200
            views.append(('elevated_'+name,[*xy,elevation],[*data['xy'][i],data['z'][i]]))
    for name,origin,target in views:
        if selected and name not in selected:continue
        view=camera('__COMPARISON_'+name,origin,target,32000 if name=='top' else None)
        if terrain:view.data.clip_end=100000
        scene.render.filepath=str(output/(name+'.png'))
        bpy.ops.render.render(write_still=True)
    print(f'COMPARISON_RENDER_OK side={label} views={len(selected) if selected else len(views)} engine=CYCLES device=CPU samples=16 denoising=True')


if __name__=='__main__':main()
