"""Portable TreeFX wire routines reused from the validated project exporter.

Contract and citations: docs/TREEFX_FORMAT.md. No geometry-builder dependencies.
"""
import ctypes
import ctypes.util
import io
import struct
import numpy as np


def checksum(blob):
    try:
        import xxhash
    except ImportError:
        library = ctypes.CDLL(ctypes.util.find_library('xxhash') or 'libxxhash.so.0')
        function = library.XXH32
        function.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
        function.restype = ctypes.c_uint32
        return function(blob, len(blob), 0) or 1
    return xxhash.xxh32(blob).intdigest() or 1


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
