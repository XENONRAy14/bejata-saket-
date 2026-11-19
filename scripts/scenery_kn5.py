"""Lossless KN5 v5 record editing for isolated visual qualification builds.

Wire layout: the project's check_kn5.py and pinned Assetto Corsa exporter.
Untouched mesh/empty records are emitted verbatim, not re-exported by Blender.
"""
import hashlib
from pathlib import Path
import struct

import numpy as np


def uint(value):return struct.pack('<I',value)


def string(value):
    encoded=value.encode();return uint(len(encoded))+encoded


def parse_tree(line):
    fields=[field.strip() for field in line.strip().split(';')]
    if not fields[0].startswith('tree: '):raise ValueError('Invalid TreeFX placement')
    values=dict(field.split('=',1) for field in fields[1:])
    position=np.array([float(v) for v in values['pos'].split(',')])
    return dict(model=fields[0][6:],position=position[[0,2,1]]*[1,-1,1],
        angle=-np.radians(float(values['angle'])),scale=float(values['size']),width=float(values['width']))


class Reader:
    def __init__(self,blob):self.blob=blob;self.offset=0
    def take(self,count):
        if count<0 or self.offset+count>len(self.blob):raise ValueError('Truncated KN5 record')
        result=self.blob[self.offset:self.offset+count];self.offset+=count;return result
    def number(self,fmt='I'):return struct.unpack('<'+fmt,self.take(struct.calcsize('<'+fmt)))[0]
    def text(self):return self.take(self.number()).decode()


def read(path):
    reader=Reader(Path(path).read_bytes())
    if reader.take(10)!=b'sc6969'+uint(5):raise ValueError('Expected KN5 v5')
    textures=[]
    for _ in range(reader.number()):
        start=reader.offset
        if reader.number()!=1:raise ValueError('Inactive texture')
        name=reader.text();blob=reader.take(reader.number())
        textures.append(dict(name=name,blob=blob,raw=reader.blob[start:reader.offset]))
    materials=[]
    for _ in range(reader.number()):
        start=reader.offset;name=reader.text();shader=reader.text();reader.take(6)
        properties={}
        for _ in range(reader.number()):
            key=reader.text();properties[key]=struct.unpack('<10f',reader.take(40))
        mapping={}
        for _ in range(reader.number()):
            slot=reader.text();reader.number();mapping[slot]=reader.text()
        materials.append(dict(name=name,shader=shader,properties=properties,textures=mapping,raw=reader.blob[start:reader.offset]))
    def node():
        start=reader.offset;kind=reader.number();name=reader.text();count=reader.number();reader.take(1)
        result=dict(kind=kind,name=name)
        if kind==1:
            result['matrix']=reader.take(64)
        elif kind==2:
            result['flags']=reader.take(3)
            result['vertices']=reader.take(reader.number()*44)
            result['indices']=reader.take(reader.number()*2)
            result['material']=reader.number();result['tail']=reader.take(29)
            if count:raise ValueError('Mesh children unsupported')
        else:raise ValueError('Unsupported KN5 node kind')
        result['raw']=reader.blob[start:reader.offset]
        result['children']=[node() for _ in range(count)]
        return result
    root=node()
    if reader.offset!=len(reader.blob):raise ValueError('Unexpected trailing KN5 bytes')
    return dict(textures=textures,materials=materials,root=root)


def nodes(model):
    def walk(node):
        yield node
        for child in node['children']:yield from walk(child)
    return list(walk(model['root']))


def encode_node(node):
    if node['kind']==2:return node['raw']
    return (uint(1)+string(node['name'])+uint(len(node['children']))+node['raw'][-65:-64]
            +node['matrix']+b''.join(encode_node(child) for child in node['children']))


def write(path,model):
    Path(path).write_bytes(b'sc6969'+uint(5)+uint(len(model['textures']))
        +b''.join(t['raw'] for t in model['textures'])+uint(len(model['materials']))
        +b''.join(m['raw'] for m in model['materials'])+encode_node(model['root']))


def mesh(name,vertices,indices,material,*,flags=b'\x01\x01\x00',tail=None):
    vertices=np.asarray(vertices,dtype='<f4').reshape(-1,11)
    indices=np.asarray(indices,dtype='<u2').reshape(-1,3)
    if not 0<len(vertices)<65000 or len(indices)==0 or int(indices.max())>=len(vertices):raise ValueError('Invalid mesh indices/vertex limit')
    if tail is None:
        positions=vertices[:,:3];center=(positions.max(0)+positions.min(0))/2
        tail=struct.pack('<I2f4f?',0,0,5000,*center,float(np.linalg.norm(positions-center,axis=1).max()),True)
    raw=uint(2)+string(name)+uint(0)+b'\x01'+flags+uint(len(vertices))+vertices.tobytes()+uint(indices.size)+indices.tobytes()+uint(material)+tail
    return dict(kind=2,name=name,flags=flags,vertices=vertices.tobytes(),indices=indices.tobytes(),material=material,tail=tail,raw=raw,children=[])


def subset(node,mask,*,name=None,material=None,forest_uv=False):
    values=np.frombuffer(node['vertices'],dtype='<f4').reshape(-1,11)
    faces=np.frombuffer(node['indices'],dtype='<u2').reshape(-1,3)[mask]
    if not len(faces):return None
    used,inverse=np.unique(faces,return_inverse=True);values=values[used].copy()
    if forest_uv:values[:,6:8]=values[:,[0,2]]/4
    return mesh(name or node['name'],values,inverse.reshape(-1,3),node['material'] if material is None else material,flags=node['flags'],tail=node['tail'])


def protected(model):
    result={}
    def walk(node,parents):
        if node['name'][:1].isdigit() or node['name'].startswith(('AC_','DETAIL_GUARD_')):
            blob=b''.join(parents)+node['raw']
            if node['kind']==2:blob+=model['materials'][node['material']]['raw']
            if node['name'] in result:raise ValueError('Duplicate protected node')
            result[node['name']]=hashlib.sha256(blob).hexdigest()
        for child in node['children']:walk(child,parents+([node['matrix']] if node['kind']==1 else []))
    walk(model['root'],[])
    return result


def validate_lock(reference,candidate):
    before,after=protected(read(reference)),protected(read(candidate))
    changed=sorted(name for name in before.keys()|after.keys() if before.get(name)!=after.get(name))
    if changed:raise ValueError('Physics/empty/guard lock mismatch: '+', '.join(changed))
    return dict(physical_meshes=sum(name[:1].isdigit() for name in before),
        spawn_gate_empties=sum(name.startswith('AC_') for name in before),
        guard_visuals=sum(name.startswith('DETAIL_GUARD_') for name in before),
        all_checksums_identical=True,reference_sha256=hashlib.sha256(Path(reference).read_bytes()).hexdigest())
