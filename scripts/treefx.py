"""External TreeFX archives; wire contract and field citations: docs/TREEFX_FORMAT.md."""
import configparser
import ctypes
import ctypes.util
from functools import lru_cache
import io
import json
from pathlib import Path
import struct
import zipfile

import numpy as np

from foliage import SPECIES,TINTS,prototype,coverage_report
from geometry import ROOT
from check_kn5 import inspect_dds


def checksum(blob):
    library=ctypes.CDLL(ctypes.util.find_library('xxhash') or 'libxxhash.so.0')
    function=library.XXH32;function.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32];function.restype=ctypes.c_uint32
    return function(blob,len(blob),0) or 1


def vector_ac(values):
    result=np.asarray(values,float)[:,[0,2,1]].copy();result[:,2]*=-1
    return result


def mesh_blob(groups,textures,radius,height):
    output=io.BytesIO();output.write(struct.pack('<iBi',1,0,len(textures)))
    for name,blob in textures.items():
        encoded=name.encode();output.write(struct.pack('<Ii',checksum(blob),len(encoded))+encoded)
    triangles=vertices=0;trunk=[]
    for diffuse,normal,mesh in groups:
        if not mesh.faces:continue
        indices=np.asarray(mesh.faces,dtype='<u2').ravel();positions=vector_ac(mesh.vertices)/[radius,height,radius]
        normals=vector_ac(mesh.normals);uv=np.asarray(mesh.uv,float).copy();uv[:,1]=1-uv[:,1]
        trunk.extend(positions[(positions[:,1]<.002)&(abs(positions[:,0])<.2)&(abs(positions[:,2])<.2)])
        tangent=np.zeros_like(positions)
        for face in np.asarray(mesh.faces):
            p=positions[face];t=uv[face];d=t[1:]-t[0];edges=p[1:]-p[0];det=np.linalg.det(d)
            if abs(det)>1e-10:np.add.at(tangent,face,(edges[0]*d[1,1]-edges[1]*d[0,1])/det)
        tangent-=normals*np.sum(tangent*normals,axis=1)[:,None]
        for i in range(len(tangent)):
            if np.linalg.norm(tangent[i])<1e-10:
                tangent[i]=np.cross(normals[i],[1,0,0] if abs(normals[i,0])<.9 else [0,1,0])
        tangent/=np.linalg.norm(tangent,axis=1)[:,None]
        output.write(struct.pack('<iii',diffuse,normal,len(indices)));output.write(indices.tobytes());output.write(struct.pack('<i',len(positions)))
        for p,n,t,uv0 in zip(positions,normals,tangent,uv):
            output.write(struct.pack('<8f4B2e4B',*p,*n,*uv0,*np.clip(t*127.5+127.5,0,255).astype(int),0,0,0,255,255,255,0))
        triangles+=len(indices)//3;vertices+=len(positions)
    if trunk:
        points=np.asarray(trunk);width=min(*points[:,[0,2]].max(0),*-points[:,[0,2]].min(0))
        output.write(struct.pack('<iif',-1,4,width))
    return output.getvalue(),dict(triangles=triangles,vertices=vertices)


def read_mesh(blob,textures,geometry=False):
    stream=io.BytesIO(blob)
    def unpack(fmt):
        size=struct.calcsize(fmt);data=stream.read(size)
        if len(data)!=size:raise ValueError('Truncated TreeFX mesh')
        return struct.unpack(fmt,data)
    version,flags,count=unpack('<iBi')
    if (version,flags)!=(1,0) or not 0<count<32:raise ValueError('Invalid TreeFX header')
    for _ in range(count):
        expected,length=unpack('<Ii')
        if not 0<length<256:raise ValueError('Invalid TreeFX texture name')
        name=stream.read(length).decode()
        if name not in textures or checksum(textures[name])!=expected:raise ValueError('TreeFX texture checksum mismatch')
    vertices=triangles=0;positions=[]
    while stream.tell()<len(blob):
        diffuse,=unpack('<i')
        if diffuse==-1:
            size,width=unpack('<if')
            if size!=4 or not np.isfinite(width) or stream.tell()!=len(blob):raise ValueError('Invalid TreeFX trunk width record')
            break
        normal,indices_count=unpack('<ii')
        if not (0<=diffuse<count and 0<=normal<count and 0<indices_count<1000000 and indices_count%3==0):raise ValueError('Invalid TreeFX material/indices')
        data=stream.read(indices_count*2)
        if len(data)!=indices_count*2:raise ValueError('Truncated TreeFX indices')
        indices=np.frombuffer(data,dtype='<u2');vertex_count,=unpack('<i')
        if not 0<vertex_count<65536 or indices.max()>=vertex_count:raise ValueError('Invalid TreeFX vertex index')
        for _ in range(vertex_count):
            values=unpack('<8f4B2e4B')
            if not np.isfinite(values).all() or abs(np.linalg.norm(values[3:6])-1)>.001:raise ValueError('Invalid TreeFX vertex')
            if values[11:]!=(0,0,0,255,255,255,0):raise ValueError('Invalid TreeFX packed defaults')
            if geometry:positions.append(values[:3])
        vertices+=vertex_count;triangles+=indices_count//3
    result=dict(vertices=vertices,triangles=triangles)
    if geometry:result['positions']=np.asarray(positions)
    return result


@lru_cache(maxsize=8)
def validate_foliage_texture(data):
    info=inspect_dds(data)
    if (info['width'],info['height'],info['format'],info['mips'])!=(1024,1024,'DXT5',11):raise ValueError('Invalid external foliage atlas')
    coverage=np.asarray(coverage_report(data))
    if np.max(abs(coverage[:7]-coverage[0]))>=.13:raise ValueError('External foliage mip coverage lost')


def validate_model(path,geometry=False):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():raise ValueError('Invalid TreeFX archive CRC')
        config=configparser.ConfigParser();config.read_string(archive.read('tree.ini').decode())
        if min(config.getfloat('BASIC','HEIGHT'),config.getfloat('BASIC','WIDTH'))<=0:raise ValueError('Invalid tree size')
        textures={n:archive.read(n) for n in archive.namelist() if n.endswith('.dds')}
        for name,data in textures.items():
            inspect_dds(data)
            if name.startswith('veg_'):validate_foliage_texture(data)
        lods=[]
        for s in config.sections():
            if not s.startswith('LOD_'):continue
            result=read_mesh(archive.read(config[s]['MODEL']),textures,geometry)
            if geometry:result['positions']*=np.array([config.getfloat('BASIC','WIDTH')/2,config.getfloat('BASIC','HEIGHT'),config.getfloat('BASIC','WIDTH')/2])
            if config.getfloat(s,'DISTANCE')!=(150 if s=='LOD_0' else 600):raise ValueError('Wrong TreeFX LOD range')
            lods.append(result)
        return lods


def generate(root=ROOT):
    root=Path(root);folder=root/'out/bejaia_saket/extension/trees';folder.mkdir(parents=True,exist_ok=True)
    plants=np.load(root/'data/vegetation.npz')['plants'];lines=[];models={};texture_folder=root/'textures/v2'
    for plant in plants:
        kind,variant=int(plant[0]),int(plant[1]);tint=int(plant[7])
        if kind==6:continue
        name=f'{SPECIES[kind]}_{variant}{TINTS[tint]}.bin'
        if name not in models:
            lods=[prototype(kind,variant,lod,quality=True) for lod in (0,1)]
            points=vector_ac(np.concatenate([m.vertices for parts in lods for m in parts.values() if m.vertices]))
            radius=float(np.max(abs(points[:,[0,2]])));height=float(points[:,1].max())
            config=f'[BASIC]\nHEIGHT={height:.9g}\nWIDTH={radius*2:.9g}\n[SHADING]\nSPECULAR=1\nSUBSCATTERING=1\nREFLECTIVITY=1\nBRIGHTNESS=1\nUSE_AO_CHANNEL=0\n[NORMALS]\nBOOST=0.9\nSPHERE=1\n[LEAVES]\nMULT=20\nOFFSET=0\n[FAKE_SHADOW]\nSIZE=1\nOPACITY=1\n'
            payloads={};expected=[]
            for lod,parts in enumerate(lods):
                names=['bark_diffuse.dds','bark_normal.dds',('veg_impostor' if lod else 'veg_canopy')+TINTS[tint]+'.dds','flat_normal.dds']
                textures={n:(texture_folder/n).read_bytes() for n in names}
                groups=[(0,1,parts['bark']),(2,3,parts['leaves'])]
                blob,metrics=mesh_blob(groups,textures,radius,height);expected.append(metrics);payloads[f'LOD{lod}.mesh']=blob;payloads.update(textures)
                config+=f'[LOD_{lod}]\nMODEL=LOD{lod}.mesh\nDISTANCE={150 if lod==0 else 600}\n'
            payloads['tree.ini']=config.encode()
            with zipfile.ZipFile(folder/name,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for filename,blob in sorted(payloads.items()):
                    entry=zipfile.ZipInfo(filename,date_time=(1980,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(entry,blob)
            if validate_model(folder/name)!=expected:raise ValueError('TreeFX round-trip mismatch')
            models[name]=expected
        x,y,z=plant[2:5];angle=-np.degrees(plant[5]);scale=plant[6]
        lines.append(f'tree: {name}; pos={x:.9g}, {z:.9g}, {-y:.9g}; angle={angle:.9g}; size={scale:.9g}; width=1; color=1, 1, 1')
    if not lines:raise ValueError('No external trees')
    (folder/'trees.txt').write_text('\n'.join(lines)+'\n')
    (folder/'grass.dds').write_bytes((texture_folder/'veg_canopy.dds').read_bytes())
    for path in folder.glob('*.bin'):
        if path.name not in models:path.unlink()
    summary=dict(mode='TreeFX',instances=len(lines),models=len(models),model_lod_metrics=models,grassfx_replaced_instances=int(np.sum(plants[:,0]==6)),human_conversion_required=False)
    (root/'data/treefx_info.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(f'TREEFX_EXPORT_OK models={len(models)} instances={len(lines)} round_trip=True human_conversion_required=False')
    return summary
