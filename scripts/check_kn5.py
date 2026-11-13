"""Read back the KN5 v5 subset written by this exporter; not an AC runtime test.

Layout source: exporter/{kn5_writer,texture_writer,material_writer,node_writer}.py
in https://github.com/moppius/blender-assetto-corsa-tools (see docs/AC_NOTES.md).
"""
import json
from pathlib import Path
import struct
import sys

import numpy as np


def inspect_kn5(path, geometry=False):
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
    materials = []
    for _ in range(number()):
        name,shader = string(),string()
        take(6)
        properties = {}
        for _ in range(number()):
            key = string()
            properties[key] = number('f')
            take(36)
        mapping = {}
        for _ in range(number()):
            key = string()
            number()
            texture = string()
            if texture not in textures:
                raise ValueError('Material refers to missing texture')
            mapping[key] = texture
        materials.append(dict(name=name,shader=shader,properties=properties,textures=mapping))
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
            take(4+8+16)
            entry.update(vertices=vertices,triangles=indices//3,material=material,renderable=number('?'))
            if geometry:
                positions = np.frombuffer(vertex_data, dtype='<f4').reshape(-1,11)[:,:3]
                entry['bounds'] = (positions.min(axis=0), positions.max(axis=0))
                if name.startswith('1ROAD_'):
                    entry['positions'] = positions
                    entry['indices'] = np.frombuffer(index_data, dtype='<u2').reshape(-1,3)
        else:
            raise ValueError(f'Unsupported node class {kind}')
        for _ in range(children):
            node()
    node()
    if offset != len(data):
        raise ValueError('Unexpected trailing KN5 data')
    return dict(bytes=len(data),textures=textures,texture_formats=texture_formats,materials=materials,nodes=nodes)


if __name__ == '__main__':
    result = inspect_kn5(sys.argv[1])
    meshes = [n for n in result['nodes'] if n['kind']==2]
    print('KN5_READBACK_OK',json.dumps(dict(bytes=result['bytes'],textures=len(result['textures']),materials=len(result['materials']),meshes=len(meshes),logical_nodes=len(result['nodes'])-len(meshes),max_vertices=max((n['vertices'] for n in meshes),default=0),triangles=sum(n['triangles'] for n in meshes))))
