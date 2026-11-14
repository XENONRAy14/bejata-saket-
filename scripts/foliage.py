"""Procedural Mediterranean cutout atlases and small, deterministic plant meshes."""
import io
import json
import math
from pathlib import Path
import struct

import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from scipy.ndimage import distance_transform_edt, label

from materials import ROOT,channel_mips,encode_data_dds,material_spec
from check_kn5 import inspect_dds
from assets import sha256,acquire

SPECIES=('aleppo_pine','stone_pine','olive','cypress','maquis','reeds','dry_grass')
TINTS=('', '_dark', '_silver')
SIZES=((6.7,7.6),(7.8,8.2),(5.2,5.0),(1.9,8.0),(2.4,1.8),(1.5,2.8),(1.1,.85))
SEED=24025


def tile_uv(kind):
    x,y=kind%4,kind//4
    return np.array([[(x+.025)/4,1-(y+.975)/2],[(x+.975)/4,1-(y+.975)/2],
                     [(x+.975)/4,1-(y+.025)/2],[(x+.025)/4,1-(y+.025)/2]])


def extract_twig(image):
    pixels=np.array(image.convert('RGBA').crop((0,0,256,474)))
    islands,_=label(pixels[:,:,3]>0)
    border=np.unique(np.r_[islands[0],islands[-1],islands[:,0],islands[:,-1]])
    pixels[np.isin(islands,border),3]=0
    return Image.fromarray(pixels)


def atlas_pixels(size=1024,impostor=False,twig=None):
    if size<32 or size%4:raise ValueError('Atlas size must be divisible by four and >=32')
    image=Image.new('RGBA',(1024,1024));rng=np.random.default_rng(SEED)
    for kind in range(7):
        tile=Image.new('RGBA',(256,512));draw=ImageDraw.Draw(tile)
        if kind<5:
            color=((61,94,43),(64,99,46),(118,133,92),(52,82,46),(72,103,48))[kind]
            # Branchlets carry individual paired leaves or needle fans, not blobs.
            for branch in range(52 if kind!=3 else 65):
                cx,cy=rng.normal([128,245],[47,88])
                if ((cx-128)/108)**2+((cy-245)/205)**2>1:continue
                angle=rng.uniform(0,2*np.pi);direction=np.array([math.cos(angle),math.sin(angle)])
                length=rng.uniform(25,65);a=np.array([cx,cy])-direction*length*.5;b=a+direction*length
                draw.line([tuple(a),tuple(b)],fill=(95,88,56,255),width=2)
                for t in np.linspace(.08,1,12):
                    origin=a+(b-a)*t
                    for sign in (-1,1):
                        theta=angle+sign*rng.uniform(.5,1.15)
                        d=np.array([math.cos(theta),math.sin(theta)])
                        c=np.clip(np.array(color)*rng.uniform(.7,1.25),0,255).astype(int)
                        if kind in (0,1,3):
                            for fan in (-.24,0,.24):
                                v=np.array([math.cos(theta+fan),math.sin(theta+fan)])*rng.uniform(9,20)
                                draw.line([tuple(origin),tuple(origin+v)],fill=tuple(c)+(255,),width=2)
                        else:
                            length=rng.uniform(10,19);width=length*(.16 if kind==2 else .29)
                            normal=np.array([-d[1],d[0]])*width;tip=origin+d*length;middle=origin+d*length*.48
                            draw.polygon([tuple(origin),tuple(middle+normal),tuple(tip),tuple(middle-normal)],fill=tuple(c)+(255,))
                            draw.line([tuple(origin),tuple(tip)],fill=tuple(np.minimum(c+16,255))+(255,),width=1)
        else:
            for blade in range(28 if kind==6 else 12):
                root=np.array([128+rng.uniform(-27,27),494]);height=rng.uniform(170,425)
                tip=root+np.array([rng.uniform(-100,100),-height]);bend=(root+tip)/2+np.array([rng.uniform(-35,35),-55])
                pts=[(1-t)**2*root+2*(1-t)*t*bend+t*t*tip for t in np.linspace(0,1,16)]
                color=(153,144,85,255) if kind==6 else (91,117,61,255)
                draw.line([tuple(p) for p in pts],fill=color,width=3 if kind==6 else 4)
                if kind==5:
                    draw.ellipse([tip[0]-3,tip[1]-23,tip[0]+3,tip[1]+13],fill=(129,107,67,255))
                    for t in (.35,.55,.7):
                        p=(1-t)*root+t*tip
                        draw.polygon([tuple(p),tuple(p+[-48,-68]),tuple(p+[3,-14])],fill=(103,126,65,255))
        if twig is not None and kind in (0,1):
            tile=Image.new('RGBA',(256,512))
            sprig=extract_twig(twig).resize((136,250),Image.Resampling.LANCZOS)
            for cluster in range(12):
                angle=float(rng.uniform(-75,75));center=(int(rng.uniform(64,193)),int(rng.uniform(125,365)))
                branch=sprig.rotate(angle,Image.Resampling.BICUBIC,expand=True)
                tile.alpha_composite(branch,(center[0]-branch.width//2,center[1]-branch.height//2))
            pixels=np.array(tile);yy,xx=np.mgrid[:512,:256]
            feather=np.clip((1-((xx-128)/119)**2-((yy-250)/237)**2)*8,0,1)
            pixels[:,:,3]=(pixels[:,:,3]*feather).astype('uint8');tile=Image.fromarray(pixels)
            tile.putalpha(tile.getchannel('A').filter(ImageFilter.MaxFilter(3)))
        alpha=tile.getchannel('A').filter(ImageFilter.GaussianBlur(.45));tile.putalpha(alpha)
        if impostor and kind<5:
            crown=tile.copy();tile=Image.new('RGBA',(256,512));draw=ImageDraw.Draw(tile)
            draw.line([(128,495),(125,240 if kind<2 else 290)],fill=(100,91,66,255),width=7 if kind!=2 else 11)
            boxes=((8,15,248,230),(5,10,251,238),(14,65,242,350),(83,8,173,440),(7,145,249,493))
            a,b,c,d=boxes[kind]
            crown=crown.resize((c-a,d-b),Image.Resampling.LANCZOS)
            tile.alpha_composite(crown,(a,b))
        image.alpha_composite(tile,((kind%4)*256,(kind//4)*512))
    pixels=np.asarray(image).copy()
    alpha=(pixels[:,:,3]>0)&(pixels[:,:,:3].max(axis=2)>8)
    _,indices=distance_transform_edt(~alpha,return_indices=True)
    pixels[:,:,:3]=pixels[indices[0],indices[1],:3]
    if size!=1024:pixels=np.asarray(Image.fromarray(pixels).resize((size,size),Image.Resampling.BOX)).copy()
    return pixels


def coverage_mips(pixels):
    pixels=np.asarray(pixels)
    if pixels.ndim!=3 or pixels.shape[2]!=4 or pixels.shape[0]<2 or pixels.shape[1]<4:raise ValueError('Need RGBA atlas pixels')
    base=pixels.copy();targets=[]
    for kind in range(8):
        h,w=base.shape[:2];cell=base[(kind//4)*h//2:(kind//4+1)*h//2,(kind%4)*w//4:(kind%4+1)*w//4,3]
        targets.append(float(np.mean(cell>=128)))
    for i,level in enumerate(channel_mips(base)):
        level=level.copy();h,w=level.shape[:2]
        if i and w>=16:
            for kind,target in enumerate(targets):
                ys=slice((kind//4)*h//2,(kind//4+1)*h//2);xs=slice((kind%4)*w//4,(kind%4+1)*w//4)
                alpha=level[ys,xs,3].astype(float);lo,hi=0.,12.
                for _ in range(22):
                    scale=(lo+hi)/2
                    if np.mean(alpha*scale>=128)<target:lo=scale
                    else:hi=scale
                choices=[1.,lo,hi]
                scale=min(choices,key=lambda s:abs(float(np.mean(alpha*s>=128))-target))
                level[ys,xs,3]=np.clip(alpha*scale,0,255).astype('uint8')
        yield level


def encode_coverage_dds(pixels,path):
    # Reuse the verified BC3 writer, then assemble the independently scaled levels.
    payload=[];header=None
    for i,level in enumerate(coverage_mips(pixels)):
        temporary=path.parent/f'.{path.stem}_level.dds'
        encode_data_dds(level,temporary)
        blob=temporary.read_bytes();temporary.unlink()
        if header is None:header=bytearray(blob[:128])
        size=max(1,(level.shape[0]+3)//4)*max(1,(level.shape[1]+3)//4)*16
        payload.append(blob[128:128+size])
    struct.pack_into('<I',header,28,len(payload))
    path.write_bytes(header+b''.join(payload))


def coverage_report(blob):
    from check_kn5 import inspect_dds
    info=inspect_dds(blob);offset=128;levels=[]
    for i in range(info['mips']):
        w=max(1,info['width']>>i);h=max(1,info['height']>>i);size=max(1,(w+3)//4)*max(1,(h+3)//4)*16
        header=bytearray(blob[:128]);struct.pack_into('<I',header,12,h);struct.pack_into('<I',header,16,w);struct.pack_into('<I',header,28,1)
        p=np.asarray(Image.open(io.BytesIO(header+blob[offset:offset+size])).convert('RGBA'));offset+=size
        if w<16:continue
        levels.append([float(np.mean(p[(k//4)*h//2:(k//4+1)*h//2,(k%4)*w//4:(k%4+1)*w//4,3]>=128)) for k in range(7)])
    return levels


def generate_textures(root=ROOT):
    folder=root/'textures/v2';folder.mkdir(parents=True,exist_ok=True)
    info=json.loads((root/'data/materials_info.json').read_text())
    manifest=acquire(root,manifest=json.loads((root/'data/foliage_assets.lock.json').read_text()))
    twig=Image.open(root/manifest['assets'][0]['files']['twig_diffuse']['path']).convert('RGBA')
    for impostor in (False,True):
        pixels=atlas_pixels(impostor=impostor,twig=twig)
        for index,tint in enumerate(TINTS):
            color=pixels.copy();color[:,:,:3]=np.clip(color[:,:,:3]*np.array(((1,1,1),(.82,.9,.8),(1.1,1.06,1.07))[index]),0,255).astype('uint8')
            name=('veg_impostor' if impostor else 'veg_canopy')+tint;path=folder/(name+'.dds')
            encode_coverage_dds(color,path)
            record=inspect_dds(path.read_bytes());record.update(sha256=sha256(path),alpha_coverage=coverage_report(path.read_bytes()))
            info['textures'][path.name]=record
            spec=material_spec('ksPerPixelAT',dict(ksAmbient=.5,ksDiffuse=.6,ksSpecular=.02,ksSpecularEXP=10),dict(txDiffuse=path.name),kind='foliage',roughness=.95)
            spec.update(alphaBlendMode='AlphaToCoverage',alphaTested=True)
            info['materials'][name]=spec
    info['dds_gpu_bytes']=sum(v['gpu_bytes'] for v in info['textures'].values())
    (root/'data/materials_info.json').write_text(json.dumps(info,indent=2)+'\n')
    return info


def mesh_batch_key(batches,key,count,limit=60000):
    if count<0 or count>limit:raise ValueError('Prototype exceeds mesh batch limit')
    part=0
    while len(batches.get((*key,part),([],))[0])+count>limit:part+=1
    return (*key,part)


class Mesh:
    def __init__(self):self.vertices=[];self.faces=[];self.uv=[];self.normals=[]

    def quad(self,points,uv,normals,double=False):
        start=len(self.vertices);self.vertices.extend(np.asarray(points).tolist());self.uv.extend(np.asarray(uv).tolist());self.normals.extend(np.asarray(normals).tolist())
        self.faces.extend([(start,start+1,start+2),(start,start+2,start+3)])
        if double:
            start=len(self.vertices);self.vertices.extend(np.asarray(points).tolist());self.uv.extend(np.asarray(uv).tolist());self.normals.extend(np.asarray(normals).tolist())
            self.faces.extend([(start,start+2,start+1),(start,start+3,start+2)])

    def cylinder(self,a,b,radius,sides=5,end_radius=None):
        a,b=np.asarray(a,float),np.asarray(b,float);direction=b-a;direction/=np.linalg.norm(direction)
        x=np.cross(direction,[0,1,0]);x/=np.linalg.norm(x);y=np.cross(direction,x)
        for k in range(sides):
            normals=np.array([math.cos(t)*x+math.sin(t)*y for t in (k*2*np.pi/sides,(k+1)*2*np.pi/sides)])
            end=radius*.7 if end_radius is None else end_radius
            points=[a+normals[0]*radius,a+normals[1]*radius,b+normals[1]*end,b+normals[0]*end]
            self.quad(points,[[0,0],[1,0],[1,1],[0,1]],normals[[0,1,1,0]])


def prototype(kind,variant,lod=0,quality=False):
    if kind not in range(7) or variant not in range(3) or lod not in (0,1):raise ValueError('Unknown species, variant or LOD')
    rng=np.random.default_rng(SEED+kind*101+variant*17);width,height=SIZES[kind]
    width*=1+variant*.06;height*=1+(variant-1)*.06
    bark,leaves=Mesh(),Mesh();uv=tile_uv(kind)
    if quality and lod and kind==4:width,height=7.4,2.5
    def card(center,w,h,angle,tilt=0,canopy=None):
        center=np.asarray(center,float);x=np.array([math.cos(angle),math.sin(angle),0]);y=np.array([-math.sin(angle)*math.sin(tilt),math.cos(angle)*math.sin(tilt),math.cos(tilt)])
        p=np.array([center-x*w/2-y*h/2,center+x*w/2-y*h/2,center+x*w/2+y*h/2,center-x*w/2+y*h/2])
        n=p-np.asarray(canopy if canopy is not None else center-[0,0,h*.1]);n[:,2]+=h*.2;n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-8)
        leaves.quad(p,uv,n,True)
    if lod:
        if quality and kind==4:
            for x,angle in ((-1.6,-.18),(1.6,.18)):card([x,0,height/2-.08],4.2,height,angle,canopy=[x,0,height*.45])
        else:
            for angle in (0,np.pi/2):card([0,0,height/2-.08],width,height,angle,canopy=[0,0,height*.45])
    elif kind<3 and quality:
        olive=kind==2;trunk_height=height*(.40 if olive else .56)
        radius=.38 if olive else .23;centers=[]
        for level in range(6):
            t=level/5
            lean=(.22*math.sin(t*5+variant) if olive else t*.65)
            centers.append(np.array([lean,.16*math.sin(t*5+variant),-.2+trunk_height*t]))
        for i,(a,b) in enumerate(zip(centers,centers[1:])):
            bark.cylinder(a,b,radius*(1-i*.11),6,end_radius=radius*(1-(i+1)*.11))
        if olive:
            for angle in (0,2.1,4.2):bark.cylinder([math.cos(angle)*.5,math.sin(angle)*.5,-.16],centers[1],.16,4,end_radius=.21)
        crown=np.array([centers[-1][0],0,height*(.70 if olive else .78)])
        def branch(a,b,r,depth,phase):
            middle=(a+b)/2+np.array([.1*math.sin(phase),.1*math.cos(phase),-.12])
            bark.cylinder(a,middle,r,4,end_radius=r*.72)
            bark.cylinder(middle,b,r*.72,4,end_radius=r*.45)
            if depth:
                for sign in (-1,1):
                    tip=b+np.array([math.cos(phase+sign*.7)*width*.13,math.sin(phase+sign*.7)*width*.13,rng.uniform(-.15,.5)])
                    branch(b,tip,r*.43,depth-1,phase+sign*.7)
            else:
                for j in range(18):
                    point=b+rng.normal(0,[width*.14,width*.14,height*.085])
                    card(point,width*(.25 if olive else .19),height*(.25 if olive else .23),phase+j*2.39996,rng.uniform(-1.2,1.2),crown)
        for limb in range(6):
            angle=limb*2.39996+variant*.71
            reach=width*(.25 if kind==0 else .29)*(1+rng.uniform(-.16,.12))
            tip=crown+np.array([math.cos(angle)*reach,math.sin(angle)*reach,rng.uniform(-.35,.35)*(1.6 if olive else 1)])
            branch(centers[2+limb%3],tip,radius*.44,1,angle)
    elif kind<3:
        trunk_height=height*(.52 if kind<2 else .42)
        centers=[np.array([0.,0.,-.2])]
        levels=(1,2,3)
        for level in levels:centers.append(np.array([(.1 if kind<2 else .25)*math.sin(level+variant),.1*math.cos(level+variant),trunk_height*level/len(levels)]))
        for a,b in zip(centers,centers[1:]):bark.cylinder(a,b,.18 if kind<2 else .24)
        branches=4
        for branch in range(branches):
            angle=branch*2*np.pi/branches+variant*.6;tip=np.array([math.cos(angle)*width*.25,math.sin(angle)*width*.25,height*.7])
            bark.cylinder(centers[2],tip,.08)
        count=16 if kind!=2 else 13;center=np.array([0,0,height*.75])
        for i in range(count):
            theta=i*2.39996+variant;radius=width*.25*math.sqrt((i+.5)/count)
            c=center+np.array([math.cos(theta)*radius,math.sin(theta)*radius,rng.uniform(-.6,.6)])
            if kind==0:c[2]+=math.sin(theta)*.45
            card(c,width*.47,height*(.33 if kind<2 else .48),theta,rng.uniform(-.7,.7),center)
    elif kind==3 and quality:
        for level in range(5):bark.cylinder([0,0,level*height*.18-.2],[.035,0,(level+1)*height*.18],.13*(1-level*.13),4)
        for level in range(9):
            z=height*(.12+level*.092);radius=width*.33*(1-z/height)**.35
            for j in range(3):
                angle=level*2.39996+j*2.094
                point=[math.cos(angle)*radius*.5,math.sin(angle)*radius*.5,z]
                if j==0:bark.cylinder([0,0,z-.2],point,.035,3)
                card(point,radius*1.3,height*.23,angle,rng.uniform(-.3,.3),[0,0,height*.48])
    elif kind==3:
        bark.cylinder([0,0,-.2],[.05,0,height*.8],.12)
        for i in range(12):
            z=height*(.15+.07*i);radius=width*.5*(1-z/height)**.45
            card([0,0,z],radius*2,height*.37,i*2.39996,rng.uniform(-.2,.2),[0,0,height*.48])
    elif kind==4 and quality:
        for mound in range(4):
            center=np.array([(mound-1.5)*1.6,.23*math.sin(mound+variant),0])
            for i in range(3):
                angle=i*2.4;tip=center+[math.cos(angle)*.35,math.sin(angle)*.35,1.1]
                bark.cylinder(center+[0,0,-.16],tip,.035,3)
            for i in range(8):
                angle=i*2.39996;radius=.58*math.sqrt((i+.5)/8)
                point=center+[math.cos(angle)*radius,math.sin(angle)*radius,1.0+.3*math.sin(angle)]
                card(point,1.9,2.25,angle,rng.uniform(-.7,.7),center+[0,0,.95])
    elif kind==4:
        for i in range(8):
            theta=i*2.4;r=width*.22*(i%3)/2;c=[math.cos(theta)*r,math.sin(theta)*r,height*.53+rng.uniform(-.2,.2)]
            bark.cylinder([0,0,-.12],[c[0],c[1],height*.5],.025,3)
            card(c,width*.78,height*.9,theta,rng.uniform(-.4,.4),[0,0,height*.4])
    else:
        for i in range(4 if kind==5 else 3):card([0,0,height/2-.07],width,height,i*np.pi/3+variant*.2,rng.uniform(-.13,.13),[0,0,height*.3])
    return {'bark':bark,'leaves':leaves}
