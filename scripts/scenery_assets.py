"""Cached CC0 asset preparation without rebaking or collapsing foliage cards."""
import configparser
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import zipfile

import numpy as np
from PIL import Image

from scenery_kn5 import Reader
from treefx_wire import mesh_blob, read_mesh
from pilot_common import dds


def foliage_tint(image,tint=(.55,.70,.50)):
    tint=np.asarray(tint,float)
    if tint.shape!=(3,) or not np.isfinite(tint).all() or (tint<0).any():raise ValueError('Invalid foliage tint')
    pixels=np.array(image.convert('RGBA'));rgb=pixels[:,:,:3]/255
    linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)*tint
    rgb=np.where(linear<=.0031308,linear*12.92,1.055*np.maximum(linear,0)**(1/2.4)-.055)
    pixels[:,:,:3]=np.uint8(np.clip(np.rint(rgb*255),0,255))
    return Image.fromarray(pixels)


def litter_texture(image,seed=24031):
    pixels=np.array(foliage_tint(image,(.28,.30,.16)));rng=np.random.default_rng(seed)
    coarse=np.asarray(Image.fromarray(np.uint8(rng.uniform(0,255,(8,8)))).resize(image.size,Image.Resampling.BICUBIC))/255-.5
    fine=np.asarray(Image.fromarray(np.uint8(rng.uniform(0,255,(64,64)))).resize(image.size,Image.Resampling.BICUBIC))/255-.5
    patch=coarse*.65+fine*.22
    pixels[:,:,:3]=np.uint8(np.clip(pixels[:,:,:3]*(1+patch[:,:,None])*np.stack([1-patch*.15,1+patch*.15,np.ones_like(patch)],axis=2),0,255))
    return Image.fromarray(pixels)


def canopy_atlas(images,seed=24032):
    sources=[]
    for image in images:
        image=image.convert('RGBA');box=image.getchannel('A').getbbox()
        if box:
            image=image.crop(box);sources.append(image.crop((0,0,image.width,max(1,int(image.height*.62)))))
    if not sources:raise ValueError('No cached pine canopies')
    rng=np.random.default_rng(seed);atlas=Image.new('RGBA',(1024,1024))
    for variant in range(4):
        tile=Image.new('RGBA',(512,512))
        for y in (180,280,390,500,610):
            for x in (-80,60,200,340,480,620):
                source=sources[int(rng.integers(len(sources)))].copy();size=int(rng.integers(240,350))
                source.thumbnail((size,size));tile.alpha_composite(source,(x-size//2+int(rng.integers(-25,26)),y-size//2+int(rng.integers(-25,26))))
        atlas.alpha_composite(tile,((variant%2)*512,(variant//2)*512))
    return foliage_tint(atlas,(.12,.20,.10))


def back_pine_atlas(path):
    with zipfile.ZipFile(path) as archive:
        return canopy_atlas([Image.open(io.BytesIO(archive.read(name))).convert('RGBA') for name in archive.namelist() if '_impostor_' in name and name.endswith('.dds')])


def archive_radius(path):
    with zipfile.ZipFile(path) as archive:
        config=configparser.ConfigParser();config.read_string(archive.read('tree.ini').decode())
        width=config.getfloat('BASIC','WIDTH');radius=0.
        for section in config:
            if not section.startswith('LOD_'):continue
            _,groups=wire_groups(archive.read(config[section]['MODEL']))
            radius=max(radius,max(np.linalg.norm(np.asarray(part.vertices)[:,:2],axis=1).max()*width/2 for _,_,part in groups))
    return float(radius)


def shrub_cluster(source,destination):
    centers=(-1.8,0.,1.8);metrics=[];source_radius=archive_radius(source)
    with zipfile.ZipFile(source) as archive:
        config=configparser.ConfigParser();config.optionxform=str;config.read_string(archive.read('tree.ini').decode())
        height=config.getfloat('BASIC','HEIGHT')*2;width=config.getfloat('BASIC','WIDTH');radius=max(abs(x) for x in centers)+source_radius*2
        config['BASIC']['HEIGHT']=str(height);config['BASIC']['WIDTH']=str(radius*2);config['LOD_0']['DISTANCE']='12'
        payloads={name:archive.read(name) for name in archive.namelist() if name.endswith('.dds')}
        for lod in range(3):
            names,original=wire_groups(archive.read(config[f'LOD_{lod}']['MODEL']));groups=[]
            textures={name:payloads[name] for name in names}
            for x in centers:
                for diffuse,normal,part in original:
                    positions=np.asarray(part.vertices)*[width,width,height]+[x,0,0]
                    groups.append((diffuse,normal,SimpleNamespace(vertices=positions.tolist(),normals=part.normals,uv=part.uv,faces=part.faces)))
            payload,metric=mesh_blob(groups,textures,radius,height);assert read_mesh(payload,textures)==metric
            payloads[config[f'LOD_{lod}']['MODEL']]=payload;metrics.append(metric)
        stream=io.StringIO();config.write(stream);payloads['tree.ini']=stream.getvalue().encode('utf-8')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,payload in payloads.items():archive.writestr(zipfile.ZipInfo(name,(2020,1,1,0,0,0)),payload,compress_type=zipfile.ZIP_DEFLATED)
    return dict(kind='shrub',file=destination.name,height=height,width=radius*2,bytes=destination.stat().st_size,lods=metrics,
        clearance_spheres=[[x,0,source_radius*2] for x in centers],source_crowns=3)


def card_lod_groups(groups,names):
    result=[]
    for diffuse,normal,part in groups:
        faces=np.asarray(part.faces,dtype=int)
        if not len(faces):continue
        if '_card_' in names[diffuse]:faces=faces[np.asarray(part.uv)[faces][...,0].mean(axis=1)<.5]
        if not len(faces):continue
        used,inverse=np.unique(faces,return_inverse=True)
        result.append((diffuse,normal,SimpleNamespace(vertices=np.asarray(part.vertices)[used].tolist(),
            normals=np.asarray(part.normals)[used].tolist(),uv=np.asarray(part.uv)[used].tolist(),faces=inverse.reshape(-1,3).tolist())))
    return result


def wire_groups(blob):
    reader=Reader(blob);reader.take(5);names=[]
    for _ in range(reader.number()):reader.take(4);names.append(reader.text())
    groups=[]
    while reader.offset<len(blob):
        diffuse=reader.number('i')
        if diffuse==-1:break
        normal=reader.number();faces=np.frombuffer(reader.take(reader.number()*2),'<u2').reshape(-1,3).copy()
        values=np.frombuffer(reader.take(reader.number()*44),dtype=np.dtype([('v','<f4',(8,)),('tail','u1',(12,))]))['v'].copy()
        positions=values[:,:3][:,[0,2,1]]*[1,-1,1];normals=values[:,3:6][:,[0,2,1]]*[1,-1,1]
        uv=values[:,6:8]*[1,-1]+[0,1]
        groups.append((diffuse,normal,SimpleNamespace(vertices=positions.tolist(),normals=normals.tolist(),uv=uv.tolist(),faces=faces.tolist())))
    return names,groups


def repair_pine_archive(source,destination,impostor_distance=None):
    if impostor_distance is not None and (not np.isfinite(impostor_distance) or impostor_distance<150):raise ValueError('Pine impostors must start at 150 m or farther')
    source=Path(source)
    if not source.stem.startswith(('ph_pine_0','ph_pine_mid_')):
        destination.write_bytes(source.read_bytes());return False
    adult=source.with_name(source.name.replace('ph_pine_mid_','ph_pine_'))
    with zipfile.ZipFile(adult) as archive:
        near=archive.read('LOD0.mesh');names,groups=wire_groups(near)
        textures={name:archive.read(name) for name in names}
    read_mesh(near,textures)
    medium,metrics=(near,read_mesh(near,textures)) if impostor_distance is not None else mesh_blob(card_lod_groups(groups,names),textures,1,1)
    assert read_mesh(medium,textures)==metrics
    with zipfile.ZipFile(source) as archive,zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as output:
        for entry in archive.infolist():
            payload=medium if entry.filename=='LOD1.mesh' else archive.read(entry.filename)
            if entry.filename=='tree.ini' and impostor_distance is not None:
                config=configparser.ConfigParser();config.optionxform=str;config.read_string(payload.decode())
                config['LOD_1']['DISTANCE']=str(impostor_distance)
                stream=io.StringIO();config.write(stream);payload=stream.getvalue().encode('utf-8')
            output.writestr(entry,payload)
    return metrics


def edge_atlas(path,pilot=None,seed=24028):
    with zipfile.ZipFile(path) as archive:textures={n:archive.read(n) for n in archive.namelist() if n.endswith('.dds')}
    sources=[]
    for name in sorted(textures):
        if '_twig_' not in name or '_card_diff' not in name:continue
        image=Image.open(io.BytesIO(textures[name])).convert('RGBA');w,h=image.size
        for x,y in ((0,0),(1,0),(0,1),(1,1)):
            tile=image.crop((x*w//2,y*h//2,(x+1)*w//2,(y+1)*h//2));box=tile.getchannel('A').getbbox()
            if box:sources.append(tile.crop(box))
    if not sources:raise ValueError('Cached twig cards missing')
    rng=np.random.default_rng(seed);atlas=Image.new('RGBA',(1024,1024))
    for variant in range(4):
        tile=Image.new('RGBA',(512,512))
        if pilot is not None:
            blob=next(t['blob'] for t in pilot['textures'] if t['name']=='PH_forest_edge_diff.dds')
            shrubs=Image.open(io.BytesIO(blob)).convert('RGBA')
            for _ in range(12):
                index=int(rng.integers(4));shrub=shrubs.crop(((index%2)*512,(index//2)*512,(index%2+1)*512,(index//2+1)*512))
                size=int(rng.integers(110,190));shrub.thumbnail((size,size))
                tile.alpha_composite(shrub,(int(rng.integers(60,450))-size//2,int(rng.integers(170,450))-size//2))
        for _ in range(22):
            twig=sources[int(rng.integers(len(sources)))].copy()
            size=int(rng.integers(130,240));twig.thumbnail((size,size));twig=twig.rotate(float(rng.uniform(-160,160)),resample=Image.Resampling.BICUBIC,expand=True)
            x=int(rng.integers(80,430))-twig.width//2;y=int(rng.integers(140,460))-twig.height//2
            tile.alpha_composite(twig,(x,y))
        atlas.alpha_composite(tile,((variant%2)*512,(variant//2)*512))
    return atlas


def dds_blob(image,coverage=False,data=False):
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'texture.dds';dds(image,path,coverage=coverage,data=data);return path.read_bytes()


def ground_mask(node,select,size=1024):
    values=np.frombuffer(node['vertices'],'<f4').reshape(-1,11);faces=np.frombuffer(node['indices'],'<u2').reshape(-1,3)
    inside=np.zeros((size,size),bool);outside=inside.copy()
    for face in faces:
        uv=values[face,6:8]*size;xy=values[face,:3]
        matrix=np.column_stack([uv[1]-uv[0],uv[2]-uv[0]])
        if abs(np.linalg.det(matrix))<1e-8:continue
        lo=np.floor(uv.min(0)).astype(int);hi=np.ceil(uv.max(0)).astype(int)
        x,y=np.meshgrid(np.arange(lo[0],hi[0]),np.arange(lo[1],hi[1]));points=np.c_[x.ravel()+.5,y.ravel()+.5]
        bary=(points-uv[0])@np.linalg.inv(matrix).T
        valid=(bary>=0).all(1)&(bary.sum(1)<=1)
        if not valid.any():continue
        bary=bary[valid];world=xy[0]+bary[:,0,None]*(xy[1]-xy[0])+bary[:,1,None]*(xy[2]-xy[0])
        selected=select(world);u=x.ravel()[valid]%size;v=y.ravel()[valid]%size
        inside[v[selected],u[selected]]=True;outside[v[~selected],u[~selected]]=True
    return inside&~outside
