"""Cached CC0 asset preparation without rebaking or collapsing foliage cards."""
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


def repair_pine_archive(source,destination):
    source=Path(source)
    if not source.stem.startswith(('ph_pine_0','ph_pine_mid_')):
        destination.write_bytes(source.read_bytes());return False
    adult=source.with_name(source.name.replace('ph_pine_mid_','ph_pine_'))
    with zipfile.ZipFile(adult) as archive:
        near=archive.read('LOD0.mesh');names,groups=wire_groups(near)
        textures={name:archive.read(name) for name in names}
    read_mesh(near,textures)
    medium,metrics=mesh_blob(card_lod_groups(groups,names),textures,1,1)
    assert read_mesh(medium,textures)==metrics
    with zipfile.ZipFile(source) as archive,zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as output:
        for entry in archive.infolist():output.writestr(entry,medium if entry.filename=='LOD1.mesh' else archive.read(entry.filename))
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


def dds_blob(image,coverage=False):
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'texture.dds';dds(image,path,coverage=coverage);return path.read_bytes()


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
