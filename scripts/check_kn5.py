"""Read back the KN5 v5 subset written by this exporter; not an AC runtime test.

Layout source: exporter/{kn5_writer,texture_writer,material_writer,node_writer}.py
in https://github.com/moppius/blender-assetto-corsa-tools (see docs/AC_NOTES.md).
"""
import json
import hashlib
import io
from pathlib import Path
import struct
import sys

import numpy as np
from PIL import Image


def inspect_dds(blob):
    if len(blob)<128 or bytes(blob[:4])!=b'DDS ' or struct.unpack_from('<I',blob,4)[0]!=124:
        raise ValueError('Invalid DDS header')
    flags,height,width,_,depth,mips = struct.unpack_from('<6I',blob,8)
    fourcc = bytes(blob[84:88]).decode('ascii')
    pixel_flags=struct.unpack_from('<I',blob,80)[0]
    caps,caps2=struct.unpack_from('<II',blob,108)
    if struct.unpack_from('<I',blob,76)[0]!=32 or not pixel_flags&4 or fourcc not in ('DXT1','DXT5') or depth not in (0,1) or caps2:
        raise ValueError('Only 2D DXT1/DXT5 DDS approved for v2')
    if width<1 or height<1 or width&(width-1) or height&(height-1) or max(width,height)>2048:
        raise ValueError('DDS dimensions must be power-of-two, at most 2K')
    expected_mips = max(width,height).bit_length()
    if flags&0x1007!=0x1007 or not caps&0x1000:
        raise ValueError('DDS is missing required size/format/texture flags')
    if mips!=expected_mips or not flags&0x20000 or (mips>1 and caps&0x400008!=0x400008):
        raise ValueError('DDS requires a complete mip chain')
    block = 8 if fourcc=='DXT1' else 16
    gpu = sum(max(1,(max(1,width>>i)+3)//4)*max(1,(max(1,height>>i)+3)//4)*block for i in range(mips))
    if len(blob)!=128+gpu:
        raise ValueError('DDS payload length does not match dimensions/mip chain')
    return dict(width=width,height=height,format=fourcc,mips=mips,bytes=len(blob),gpu_bytes=gpu)


def mask_mip_error(blob):
    info=inspect_dds(blob);width,height=info['width'],info['height'];offset=128;error=0
    block=8 if info['format']=='DXT1' else 16
    for _ in range(info['mips']):
        size=max(1,(width+3)//4)*max(1,(height+3)//4)*block
        header=bytearray(blob[:128]);struct.pack_into('<II',header,12,height,width);struct.pack_into('<I',header,28,1)
        with Image.open(io.BytesIO(header+bytes(blob[offset:offset+size]))) as image:
            pixels=np.asarray(image.convert('RGBA'))[::max(1,height//64),::max(1,width//64)].astype(float)/255
            error=max(error,abs(float(pixels.sum(2).mean())-1))
        offset+=size;width=max(1,width//2);height=max(1,height//2)
    return error


def inspect_kn5(path, geometry=False, texture_data=False):
    data = memoryview(Path(path).read_bytes())
    offset = 0
    def take(size):
        nonlocal offset
        if size < 0 or offset+size > len(data):
            raise ValueError('Truncated KN5')
        value = data[offset:offset+size]
        offset += size
        return value
    def number(fmt='I'):
        return struct.unpack('<'+fmt,take(struct.calcsize('<'+fmt)))[0]
    def string():
        return bytes(take(number())).decode('utf-8')
    if bytes(take(6)) != b'sc6969' or number() != 5:
        raise ValueError('Expected KN5 v5 header')
    textures = []
    texture_formats = {}
    texture_info = {}
    texture_blobs = {}
    for _ in range(number()):
        if number() != 1:
            raise ValueError('Inactive embedded texture')
        name = string()
        blob = take(number())
        if not len(blob):
            raise ValueError('Empty embedded texture')
        textures.append(name)
        signature = bytes(blob[:8])
        texture_formats[name] = 'PNG' if signature == b'\x89PNG\r\n\x1a\n' else ('DDS' if signature[:4] == b'DDS ' else 'UNKNOWN')
        if texture_formats[name]=='DDS':
            texture_info[name] = inspect_dds(blob)
            if texture_data:texture_blobs[name]=blob
        elif texture_formats[name]=='PNG' and len(blob)>=24:
            width,height = struct.unpack_from('>II',blob,16)
            texture_info[name] = dict(width=width,height=height,format='PNG',bytes=len(blob),gpu_bytes=width*height*4,mips=1)
        if name in texture_info:
            texture_info[name]['sha256'] = hashlib.sha256(blob).hexdigest()
    materials = []
    for _ in range(number()):
        name,shader = string(),string()
        blend,alpha_tested,depth = number('B'),number('?'),number()
        properties = {}
        for _ in range(number()):
            key = string()
            properties[key] = number('f')
            take(36)
        mapping = {}
        texture_slots = {}
        for _ in range(number()):
            key = string()
            texture_slots[key] = number()
            texture = string()
            if texture not in textures:
                raise ValueError('Material refers to missing texture')
            mapping[key] = texture
        materials.append(dict(name=name,shader=shader,properties=properties,textures=mapping,texture_slots=texture_slots,blend=blend,alpha_tested=alpha_tested,depth=depth))
    nodes = []
    def node():
        kind,name,children,active = number(),string(),number(),number('?')
        entry = dict(name=name,kind=kind,active=active)
        nodes.append(entry)
        if kind == 1:
            entry['matrix'] = list(struct.unpack('<16f',take(64)))
        elif kind == 2:
            entry['castShadows'],entry['visible'],entry['transparent'] = struct.unpack('<???',take(3))
            vertices = number()
            vertex_data = take(vertices*44)
            indices = number()
            if children or not 0 < vertices <= 65536 or indices%3:
                raise ValueError('Invalid mesh counts')
            index_data = take(indices*2)
            if any(index[0] >= vertices for index in struct.iter_unpack('<H',index_data)):
                raise ValueError('Index outside vertex array')
            material = number()
            if material >= len(materials):
                raise ValueError('Missing material')
            values = np.frombuffer(vertex_data,dtype='<f4').reshape(-1,11)
            normal_lengths=np.linalg.norm(values[:,3:6],axis=1)
            tangent_lengths=np.linalg.norm(values[:,8:11],axis=1)
            entry['tangent_stats']=dict(finite=bool(np.isfinite(values).all()),
                normal_length_error=float(np.max(abs(normal_lengths-1))),
                tangent_length_error=float(np.max(abs(tangent_lengths-1))),
                max_normal_dot_tangent=float(np.max(abs(np.sum(values[:,3:6]*values[:,8:11],axis=1)))))
            take(4+8+16)
            entry.update(vertices=vertices,triangles=indices//3,material=material,renderable=number('?'))
            if geometry:
                positions = np.frombuffer(vertex_data, dtype='<f4').reshape(-1,11)[:,:3]
                entry['bounds'] = (positions.min(axis=0), positions.max(axis=0))
                if geometry=='all' or name.startswith('1ROAD_'):
                    entry['positions'] = positions
                    entry['indices'] = np.frombuffer(index_data, dtype='<u2').reshape(-1,3)
        else:
            raise ValueError(f'Unsupported node class {kind}')
        for _ in range(children):
            node()
    node()
    if offset != len(data):
        raise ValueError('Unexpected trailing KN5 data')
    return dict(bytes=len(data),textures=textures,texture_formats=texture_formats,texture_info=texture_info,texture_blobs=texture_blobs,materials=materials,nodes=nodes)


if __name__ == '__main__':
    result = inspect_kn5(sys.argv[1])
    meshes = [n for n in result['nodes'] if n['kind']==2]
    print('KN5_READBACK_OK',json.dumps(dict(bytes=result['bytes'],textures=len(result['textures']),materials=len(result['materials']),meshes=len(meshes),logical_nodes=len(result['nodes'])-len(meshes),max_vertices=max((n['vertices'] for n in meshes),default=0),triangles=sum(n['triangles'] for n in meshes))))
