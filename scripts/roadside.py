"""Procedural roadside furniture on the accepted terrain; visual meshes only."""
import json
import os
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from geometry import ROOT
from check_kn5 import inspect_kn5
from materials import material_spec
from vegetation import Terrain, blender_triangles


class Mesh:
    def __init__(self):self.vertices=[];self.faces=[];self.uv=[]

    def quad(self,points,uv=((0,0),(1,0),(1,1),(0,1))):
        start=len(self.vertices);self.vertices.extend(np.asarray(points).tolist());self.uv.extend(uv)
        self.faces.extend([(start,start+1,start+2),(start,start+2,start+3)])

    def triangle(self,points):
        start=len(self.vertices);self.vertices.extend(np.asarray(points).tolist());self.uv.extend(((0,0),(1,0),(0,1)));self.faces.append((start,start+1,start+2))

    def slab(self,a,b,width,low,high):
        a,b=np.asarray(a),np.asarray(b);direction=b[:2]-a[:2];direction/=np.linalg.norm(direction)
        n=np.r_[-direction[1],direction[0],0]*width/2
        points=np.array([a-n+[0,0,low],b-n+[0,0,low],b+n+[0,0,low],a+n+[0,0,low],
                         a-n+[0,0,high],b-n+[0,0,high],b+n+[0,0,high],a+n+[0,0,high]])
        for face in ((3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)):self.quad(points[list(face)])

    def box(self,center,size,tangent):
        tangent=np.asarray(tangent);normal=np.array([-tangent[1],tangent[0]])
        x,y,z=np.asarray(size)/2
        local=np.array([[-x,-y,-z],[x,-y,-z],[x,y,-z],[-x,y,-z],[-x,-y,z],[x,-y,z],[x,y,z],[-x,y,z]])
        local[:,:2]=local[:,:2]@np.array([tangent,normal]);points=local+center
        for face in ((3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)):self.quad(points[list(face)])


def sign_atlas(size=1024):
    if size<256 or size%2:raise ValueError('Need an even atlas size of at least 256')
    image=Image.new('RGB',(size,size),(232,230,216));draw=ImageDraw.Draw(image);half=size//2
    for tile in (0,1):
        x=tile*half;direction=1 if tile else -1
        points=np.array([[.18,.16],[.49,.16],[.82,.5],[.49,.84],[.18,.84],[.5,.5]])
        if direction<0:points[:,0]=1-points[:,0]
        draw.polygon([(x+int(a*half),int(b*half)) for a,b in points],fill=(174,30,30))
    draw.ellipse((half*.1,half*1.1,half*.9,half*1.9),fill=(174,30,30))
    draw.ellipse((half*.18,half*1.18,half*.82,half*1.82),fill=(238,236,224))
    draw.text((half*.5,half*1.51),'50',font=ImageFont.load_default(size=int(half*.36)),fill=(28,30,31),anchor='mm')
    draw.rectangle((half*1.1,half*1.1,half*1.9,half*1.9),fill=(28,69,119))
    draw.rounded_rectangle((half*1.28,half*1.25,half*1.72,half*1.68),radius=int(half*.04),fill=(237,235,223))
    draw.rectangle((half*1.32,half*1.3,half*1.68,half*1.48),fill=(28,69,119))
    for x in (1.36,1.64):draw.ellipse((half*(x-.045),half*1.62,half*(x+.045),half*1.75),fill=(28,30,31))
    return image


def sign_spec():
    return material_spec('ksPerPixel',dict(ksAmbient=.4,ksDiffuse=.6,ksSpecular=.12,ksSpecularEXP=24),
                         dict(txDiffuse='roadside_signs.dds'),kind='sign',roughness=.75)


def plan(data,houses,terrain):
    if len(data['s'])<2:raise ValueError('Need a nonempty centerline')
    batches={};counts=dict(retaining_walls=0,stone_blocks=0,chevrons=0,speed_signs=0,fences=0,bus_stops=0,reflectors=0,guardrail_m=0,drain_m=0,stones=0)
    walls=[];roots=[]
    def batch(i,material):return batches.setdefault((int(data['s'][i]//400),material),Mesh())
    def at(i,side,extra):
        outward=data['sides'][side,i,2,:2]-data['xy'][i];outward/=np.linalg.norm(outward)
        xy=data['sides'][side,i,2,:2]+outward*extra
        z,n=terrain.sample(xy[None])
        if not np.isfinite(z[0]) or z[0]<2 or n[0,2]<.7:return None
        return np.r_[xy,z[0]]
    def board(i,side,tile,extra=.65,width=.65,height=.65):
        point=at(i,side,extra)
        if point is None:return False
        tangent=data['tangent'][i];right=np.r_[-tangent[1],tangent[0],0];up=np.array([0,0,1])
        center=point+up*2.05
        batch(i,'metal').box(point+up*.95,[.075,.075,1.9],tangent)
        batch(i,'metal').box(center,[.045,width+.035,height+.035],tangent)
        center-=np.r_[tangent,0]*.027
        u=(tile%2)/2;v=.5-(tile//2)/2;e=1/1024
        uv=[(u+e,v+e),(u+e,v+.5-e),(u+.5-e,v+.5-e),(u+.5-e,v+e)]
        batch(i,'roadside_signs').quad([center-right*width/2-up*height/2,center-right*width/2+up*height/2,center+right*width/2+up*height/2,center+right*width/2-up*height/2],uv)
        roots.append(point.tolist());return True
    for chainage in np.arange(180,data['s'][-1]-100,420):
        candidates=np.flatnonzero((abs(data['s']-chainage)<100)&data['cut'].any(0))
        if not len(candidates):continue
        i=int(candidates[len(candidates)//2]);side=int(np.flatnonzero(data['cut'][:,i])[0]);center=at(i,side,1.4)
        if center is None:continue
        tangent=data['tangent'][i];placed=0
        for position in np.arange(-9,10,2):
            xy=center[:2]+tangent*position;z,n=terrain.sample(xy[None])
            if not np.isfinite(z[0]) or n[0,2]<.65:continue
            for course in range(3):
                point=np.r_[xy+tangent*(.35 if course%2 else 0),z[0]+course*.43+.12]
                batch(i,'rock').box(point,[1.96,.48,.42],tangent);counts['stone_blocks']+=1
            placed+=1
        if placed:
            counts['retaining_walls']+=1;walls.append(dict(center=center.tolist(),tangent=tangent.tolist(),chainage_m=float(data['s'][i])))
            for distance in np.arange(-6,6,2):
                base=at(i,side,.6)
                if base is None:continue
                base[:2]+=tangent*distance;z,_=terrain.sample(base[None,:2])
                if not np.isfinite(z[0]):continue
                base[2]=z[0];cross=np.array([-tangent[1],tangent[0]])
                batch(i,'plaster').box(base+[0,0,.025],[1.98,.48,.05],tangent)
                for sign in (-1,1):batch(i,'plaster').box(base+np.r_[cross*sign*.22,.11],[1.98,.06,.18],tangent)
                counts['drain_m']+=2
    for chainage in np.arange(40,data['s'][-1]-20,80):
        i=int(np.searchsorted(data['s'],chainage));tangent=data['tangent'][i]
        for side in (0,1):
            point=at(i,side,.3)
            if point is None:continue
            batch(i,'plaster').box(point+[0,0,.4],[.1,.12,.85],tangent)
            batch(i,'marker_red').box(point+np.r_[-tangent*.057,.67],[.018,.09,.12],tangent);counts['reflectors']+=1
    for chainage in np.arange(20,data['s'][-1]-20,8):
        i=int(np.searchsorted(data['s'],chainage));tangent=data['tangent'][i]
        for side in (0,1):
            drop=data['sides'][side,i,-1,2]-data['z'][i]
            if drop>=-6 or data['guard'][side,i]:continue
            point=at(i,side,.15)
            if point is None:continue
            endpoints=point[:2]+tangent*np.array([[-3.975],[3.975]]);z,_=terrain.sample(endpoints)
            if not np.isfinite(z).all():continue
            batch(i,'metal').slab(np.r_[endpoints[0],z[0]],np.r_[endpoints[1],z[1]],.12,.51,.79)
            for distance in (-3,1):
                xy=point[:2]+tangent*distance;z,_=terrain.sample(xy[None])
                if np.isfinite(z[0]):batch(i,'metal').box(np.r_[xy,z[0]+.4],[.09,.09,.88],tangent)
            counts['guardrail_m']+=8
    rng=np.random.default_rng(24026)
    for chainage in np.arange(80,data['s'][-1]-40,65):
        i=int(np.searchsorted(data['s'],chainage));side=int(np.argmax(data['sides'][:,i,-1,2]));point=at(i,side,float(rng.uniform(2,12)))
        if point is None:continue
        r=float(rng.uniform(.14,.46));top=point+[0,0,r*.8];bottom=point-[0,0,r*.2]
        ring=[point+[np.cos(a)*r,np.sin(a)*r,0] for a in np.arange(5)*2*np.pi/5]
        for k in range(5):
            batch(i,'rock').triangle([ring[k],ring[(k+1)%5],top]);batch(i,'rock').triangle([ring[(k+1)%5],ring[k],bottom])
        counts['stones']+=1
    tangent=data['tangent'];curvature=(tangent[:-1,0]*tangent[1:,1]-tangent[:-1,1]*tangent[1:,0])/np.maximum(np.diff(data['s']),1)
    selected=[]
    for i in np.argsort(-abs(curvature)):
        if abs(curvature[i])<1/170:break
        if any(abs(data['s'][i]-data['s'][j])<300 for j in selected):continue
        side=1 if curvature[i]>0 else 0
        if board(int(i),side,1 if side else 0,width=.9,height=.6):
            selected.append(int(i));counts['chevrons']+=1
        if counts['chevrons']>=36:break
    for chainage in (250,1050,2400,float(data['s'][-1]-600)):
        i=min(len(data['s'])-1,int(np.searchsorted(data['s'],chainage)))
        if board(i,0,2):counts['speed_signs']+=1
    for house in houses[::max(1,len(houses)//36)]:
        xy=house[2:4];i=int(np.argmin(np.linalg.norm(data['xy']-xy,axis=1)))
        normal=data['xy'][i]-xy;normal/=max(np.linalg.norm(normal),1e-9);tangent=data['tangent'][i]
        center=xy+normal*5.2*house[6];placed=False
        for offset in np.arange(-4.5,4.6,1.5):
            q=center+tangent*offset;z,n=terrain.sample(q[None])
            if not np.isfinite(z[0]) or z[0]<2 or n[0,2]<.8:continue
            point=np.r_[q,z[0]]
            batch(i,'bark').box(point+[0,0,.5],[.11,.11,1.1],tangent)
            if offset<4:
                for height in (.4,.85):batch(i,'bark').box(point+np.r_[tangent*.75,height],[1.5,.07,.10],tangent)
            placed=True
        counts['fences']+=int(placed)
    for chainage in (550,1450):
        i=min(len(data['s'])-1,int(np.searchsorted(data['s'],chainage)));point=at(i,0,1.3)
        if point is None:continue
        tangent=data['tangent'][i];normal=np.array([-tangent[1],tangent[0]])
        batch(i,'plaster').box(point+[0,0,.05],[4.4,1.8,.16],tangent)
        for x in (-1.9,1.9):
            for y in (-.7,.7):batch(i,'metal').box(point+np.r_[tangent*x+normal*y,1.35],[.09,.09,2.65],tangent)
        batch(i,'metal').box(point+[0,0,2.7],[4.6,2,.12],tangent)
        batch(i,'bark').box(point+[0,0,.55],[3.3,.45,.12],tangent)
        for x in (-1.3,1.3):batch(i,'metal').box(point+np.r_[tangent*x,.28],[.08,.4,.5],tangent)
        board(i,0,3,extra=1.3,width=.45,height=.6);counts['bus_stops']+=1
    return batches,dict(counts=counts,walls=walls,sign_roots=roots)


def generate(root=ROOT):
    root=Path(root);parsed=inspect_kn5(root/'out/bejaia_saket/bejaia_saket.kn5',geometry='all')
    terrain=Terrain(np.concatenate([blender_triangles(n) for n in parsed['nodes'] if n['kind']==2 and n['name'].startswith(('1GRASS_','LAND_'))]))
    data=np.load(root/'data/centerline.npz');houses=np.load(root/'data/decor_plan.npz')['placements'];houses=houses[houses[:,0]==5]
    batches,info=plan(data,houses,terrain);arrays={};names=[]
    facings=0
    for node in parsed['nodes']:
        if node['kind']!=2 or not node['name'].startswith('1GRASS_') or node['name'].startswith('1GRASS_LAND_'):continue
        triangles=blender_triangles(node);normal=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-12);normal*=np.where(normal[:,2:3]<0,-1,1)
        for tri,n in zip(triangles[normal[:,2]<.82],normal[normal[:,2]<.82]):
            if tri[:,2].min()<1:continue
            i=int(np.argmin(np.linalg.norm(data['xy']-tri.mean(0)[:2],axis=1)))
            batch=batches.setdefault((int(data['s'][i]//400),'rock'),Mesh());batch.triangle(tri+n*.025);facings+=1
    info['counts']['cut_cliff_facing_triangles']=facings
    for i,((chunk,material),mesh) in enumerate(sorted(batches.items())):
        names.append((f'DETAIL_{chunk:03d}_{material}',material));arrays[f'v{i}']=np.asarray(mesh.vertices);arrays[f'f{i}']=np.asarray(mesh.faces);arrays[f'uv{i}']=np.asarray(mesh.uv)
    np.savez_compressed(root/'data/roadside.npz',names=np.asarray(names),**arrays)
    info.update(triangles=sum(len(m.faces) for m in batches.values()),meshes=len(batches),visual_only=True,sign_material=sign_spec())
    (root/'data/roadside_info.json').write_text(json.dumps(info,indent=2)+'\n')
    image=sign_atlas();path=root/'textures/v2/roadside_signs.png';image.save(path)
    subprocess.run(['convert',str(path),'-define','dds:compression=dxt1',str(path.with_suffix('.dds'))],check=True)
    return info


def build(blender):
    info=generate();environment=dict(os.environ)
    preview=ROOT/'data/research_cache/vegetation_preview.blend'
    if preview.exists():
        environment['BS_ROADSIDE_PREVIEW_ONLY']='1'
        subprocess.run([blender,'--background',str(preview),'--python-exit-code','1','--python',str(ROOT/'scripts/blender_roadside.py')],check=True,env=environment)
    subprocess.run([blender,'--background',str(ROOT/'blend/bejaia_saket.blend'),'--python-exit-code','1','--python',str(ROOT/'scripts/blender_roadside.py')],check=True)
    from materials import export_report, package_output
    export_report();package_output()
    print('ROADSIDE_OK '+json.dumps(info['counts']))


def render(blender):
    from PIL import ImageOps
    folder=ROOT/'out/preview/v2_roadside';preview=ROOT/'data/research_cache/vegetation_preview.blend'
    subprocess.run([blender,'--background',str(preview),'--python-exit-code','1','--python',str(ROOT/'scripts/blender_material_preview.py'),'--','after'],check=True,
                   env=dict(os.environ,BS_COMPARISON_DIR=str(folder),BS_VEGETATION_PREVIEW='1',BS_ROADSIDE_PREVIEW='1'))
    names=('road_10','road_40','road_70','road_95','decor_town','decor_saket','trees_closeup','hero_tree','wall_closeup','guardrail_closeup','low_sun')
    canvas=Image.new('RGB',(1920,4*382),(25,25,25));draw=ImageDraw.Draw(canvas)
    for i,name in enumerate(names):
        x=(i%3)*640;y=(i//3)*382
        with Image.open(folder/'after'/f'{name}.png') as im:canvas.paste(ImageOps.fit(im.convert('RGB'),(640,360)),(x,y))
        draw.text((x+10,y+362),name,fill='white')
    canvas.save(folder/'contact_sheet.jpg',quality=92)
    print('ROADSIDE_RENDER_OK '+str(folder/'contact_sheet.jpg'))
