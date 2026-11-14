"""Material/UV-only v2 pass and KN5 export, without preview rendering."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

import bpy
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from check_kn5 import inspect_kn5


def geometry_digest():
    digest = hashlib.sha256()
    for obj in sorted(bpy.data.objects,key=lambda o:o.name):
        if obj.type not in ('MESH','EMPTY'):continue
        digest.update(obj.name.encode())
        digest.update(np.asarray(obj.matrix_world,dtype='<f4').tobytes())
        if obj.type=='MESH':
            digest.update(np.asarray([v.co[:] for v in obj.data.vertices],dtype='<f4').tobytes())
            for poly in obj.data.polygons:
                digest.update(np.asarray(poly.vertices[:],dtype='<i4').tobytes())
    return digest.hexdigest()


def material_nodes(mat, spec):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes;nodes.clear()
    links = mat.node_tree.links
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Roughness'].default_value = spec['preview']['roughness']
    if mat.name=='metal':shader.inputs['Metallic'].default_value=.65
    output = nodes.new('ShaderNodeOutputMaterial');links.new(shader.outputs['BSDF'],output.inputs['Surface'])
    textures = {}
    for slot,entry in spec['textures'].items():
        node = nodes.new('ShaderNodeTexImage')
        node.image = bpy.data.images.load(str(ROOT/'textures/v2'/entry['textureName']),check_existing=True)
        node.image.alpha_mode = 'CHANNEL_PACKED'
        node.image.colorspace_settings.name = 'Non-Color' if ('Normal' in slot or slot in ('txMaps','txMask')) else 'sRGB'
        node.assettoCorsa.shaderInputName = slot
        node.show_texture = True
        textures[slot] = node
    def math_node(operation,a,b):
        n=nodes.new('ShaderNodeMath');n.operation=operation
        for socket,value in zip(n.inputs,(a,b)):
            if isinstance(value,(int,float)):socket.default_value=value
            else:links.new(value,socket)
        return n.outputs[0]
    def color_mix(a,b,fac=None,operation='MIX'):
        n=nodes.new('ShaderNodeMixRGB');n.blend_type=operation
        if fac is None:n.inputs[0].default_value=1
        else:links.new(fac,n.inputs[0])
        links.new(a,n.inputs[1]);links.new(b,n.inputs[2]);return n.outputs[0]
    if spec['preview']['kind'] in ('road','terrain'):
        geometry=nodes.new('ShaderNodeNewGeometry');split=nodes.new('ShaderNodeSeparateXYZ')
        links.new(geometry.outputs['Position'],split.inputs[0])
        vector=nodes.new('ShaderNodeCombineXYZ')
        scale=spec['properties']['multR']['valueA']
        links.new(math_node('MULTIPLY',split.outputs['X'],scale),vector.inputs['X'])
        links.new(math_node('MULTIPLY',split.outputs['Y'],-scale),vector.inputs['Y'])
        mask=nodes.new('ShaderNodeSeparateRGB');links.new(textures['txMask'].outputs['Color'],mask.inputs[0])
        weights=[mask.outputs[c] for c in 'RGB']+[textures['txMask'].outputs['Alpha']]
        combined=[]
        for prefix in ('txDetail','txNormal'):
            total=None
            for channel,weight in zip('RGBA',weights):
                node=textures[prefix+channel];links.new(vector.outputs[0],node.inputs['Vector'])
                scaled=nodes.new('ShaderNodeMixRGB');scaled.blend_type='MULTIPLY';scaled.inputs[0].default_value=1
                links.new(node.outputs['Color'],scaled.inputs[1]);links.new(weight,scaled.inputs[2])
                total=scaled.outputs[0] if total is None else color_mix(total,scaled.outputs[0],operation='ADD')
            combined.append(total)
        links.new(color_mix(textures['txDiffuse'].outputs['Color'],combined[0],operation='MULTIPLY'),shader.inputs['Base Color'])
        normal_color=combined[1]
    else:
        links.new(textures['txDiffuse'].outputs['Color'],shader.inputs['Base Color'])
        normal_color=textures['txNormal'].outputs['Color']
    separate=nodes.new('ShaderNodeSeparateRGB');links.new(normal_color,separate.inputs[0])
    combine=nodes.new('ShaderNodeCombineRGB')
    links.new(separate.outputs['R'],combine.inputs['R']);links.new(math_node('SUBTRACT',1,separate.outputs['G']),combine.inputs['G']);links.new(separate.outputs['B'],combine.inputs['B'])
    normal=nodes.new('ShaderNodeNormalMap');links.new(combine.outputs[0],normal.inputs['Color']);links.new(normal.outputs[0],shader.inputs['Normal'])
    mat.assettoCorsa.alphaBlendMode='0';mat.assettoCorsa.alphaTested=False;mat.assettoCorsa.depthMode='0'


def apply(info):
    original = geometry_digest()
    specs = info['materials']
    for name,spec in specs.items():
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        material_nodes(mat,spec)
    for obj in bpy.data.objects:
        if obj.type!='MESH':continue
        if obj.name.startswith('1ROAD_'):
            chunk=int(obj.name.split('_')[1]);variant=chunk%3
            obj.data.materials.clear();obj.data.materials.append(bpy.data.materials['asphalt' if variant==0 else f'asphalt_v{variant}'])
            uv=obj.data.uv_layers.active
            previous=float(obj.data.get('road_uv_period_m',7))
            period=specs['asphalt']['preview']['period_m']
            for loop in uv.data:loop.uv.y *= previous/period
            obj.data['road_uv_period_m']=period
        else:
            if obj.name.startswith('1GRASS_') and obj.name.endswith('_L'):
                obj.data.materials.clear();obj.data.materials.append(bpy.data.materials['grass_mountain'])
            for poly in obj.data.polygons:
                mat=obj.data.materials[poly.material_index]
                if mat.name not in specs:continue
                spec=specs[mat.name]
                scale=spec['preview'].get('tile_m',spec['preview'].get('period_m',1))
                normal=np.abs(poly.normal)
                for index in poly.loop_indices:
                    co=obj.matrix_world@obj.data.vertices[obj.data.loops[index].vertex_index].co
                    uv=(co.x,-co.y) if spec['preview']['kind']=='terrain' or normal[2]>=max(normal[0],normal[1]) else ((co.y,co.z) if normal[0]>normal[1] else (co.x,co.z))
                    obj.data.uv_layers.active.data[index].uv=(uv[0]/scale,uv[1]/scale)
    assert geometry_digest()==original,'Geometry or transforms changed during material pass'
    return original


def main():
    source=Path(os.environ.get('AC_ADDON_SOURCE',str(Path.home()/'tools/blender-assetto-corsa-tools')))
    addons=Path(bpy.utils.user_resource('SCRIPTS',path='addons',create=True));target=addons/'blender_assetto_corsa_tools'
    shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git'))
    bpy.utils.refresh_script_paths();bpy.ops.preferences.addon_enable(module=target.name)
    info=json.loads((ROOT/'data/materials_info.json').read_text())
    original=apply(info)
    settings=json.loads((ROOT/'blend/settings.json').read_text())
    for name,spec in info['materials'].items():settings['materials'][name]={k:v for k,v in spec.items() if k!='preview'}
    (ROOT/'blend/settings.json').write_text(json.dumps(settings,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'blend/bejaia_saket.blend'))
    exporter=importlib.import_module(target.name+'.exporter')
    original_writer=exporter.NodeWriter
    original_texture_writer=exporter.TextureWriter
    class MaterialTextureWriter(original_texture_writer):
        def _get_image_data_from_texture(self,texture):
            source=Path(bpy.path.abspath(texture.image.filepath))
            if source.suffix.lower()=='.dds':
                blob=source.read_bytes()
                assert blob[:4]==b'DDS '
                return blob
            return super()._get_image_data_from_texture(texture)
    class MaterialNodeWriter(original_writer):
        def _split_object_by_materials(self,obj):
            meshes=super()._split_object_by_materials(obj)
            names={v:k for k,v in self.material_writer.material_positions.items()}
            for mesh in meshes:
                name=names[mesh.material_id]
                if name not in info['materials']:continue
                positions=np.asarray([v.co[:] for v in mesh.vertices],dtype=float)
                uv=np.asarray([v.uv[:] for v in mesh.vertices],dtype=float)
                faces=np.asarray(mesh.indices).reshape(-1,3)
                edges=positions[faces[:,1:]]-positions[faces[:,0,None]]
                delta=uv[faces[:,1:]]-uv[faces[:,0,None]]
                determinant=delta[:,0,0]*delta[:,1,1]-delta[:,1,0]*delta[:,0,1]
                tangents=np.zeros((len(faces),3));valid=abs(determinant)>1e-12
                tangents[valid]=(edges[valid,0]*delta[valid,1,1,None]-edges[valid,1]*delta[valid,0,1,None])/determinant[valid,None]
                accumulated=np.zeros((len(mesh.vertices),3))
                np.add.at(accumulated,faces.ravel(),np.repeat(tangents,3,axis=0))
                for i,vertex in enumerate(mesh.vertices):
                    normal=Vector(vertex.normal).normalized()
                    if info['materials'][name]['preview']['kind'] in ('road','terrain'):
                        tangent=Vector((1,0,0))
                        if abs(normal.dot(tangent))>.999:tangent=Vector((0,0,1))
                    else:
                        tangent=Vector(accumulated[i])
                    tangent-=normal*tangent.dot(normal)
                    if tangent.length_squared<1e-12:
                        axis=Vector((1,0,0)) if abs(normal.x)<.9 else Vector((0,0,1))
                        tangent=axis-normal*axis.dot(normal)
                    vertex.tangent=tangent.normalized()
            return meshes
    exporter.NodeWriter=MaterialNodeWriter
    exporter.TextureWriter=MaterialTextureWriter
    path=ROOT/'out/bejaia_saket/bejaia_saket.kn5';partial=path.with_suffix('.kn5.partial')
    warnings=[];started=time.monotonic()
    try:
        with partial.open('wb') as stream:exporter.KN5FileWriter(stream,bpy.context,settings,warnings).write()
    finally:
        exporter.NodeWriter=original_writer
        exporter.TextureWriter=original_texture_writer
    parsed=inspect_kn5(partial)
    actual={m['name']:m for m in parsed['materials']}
    for name,spec in info['materials'].items():
        mat=actual[name]
        assert mat['shader']==spec['shaderName']
        assert mat['textures']=={k:v['textureName'] for k,v in spec['textures'].items()}
        assert mat['texture_slots']=={k:i for i,k in enumerate(spec['textures'])}
        assert (mat['blend'],mat['alpha_tested'],mat['depth'])==(0,False,0)
        assert mat['properties'].keys()==spec['properties'].keys()
        for k,v in spec['properties'].items():assert np.isclose(mat['properties'][k],v['valueA'])
    for name,expected in info['textures'].items():assert parsed['texture_info'][name]['sha256']==expected['sha256'],name
    partial.replace(path)
    info.update(geometry_sha256_before_and_after=original,kn5_bytes=parsed['bytes'],kn5_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),export_seconds=time.monotonic()-started,warnings=warnings,
                embedded_texture_count=len(parsed['textures']),texture_gpu_bytes=sum(t['gpu_bytes'] for t in parsed['texture_info'].values()),embedded_textures=parsed['texture_info'])
    (ROOT/'data/materials_info.json').write_text(json.dumps(info,indent=2)+'\n')
    ui_path=path.parent/'ui/ui_track.json';ui=json.loads(ui_path.read_text());ui['version']='0.2';ui_path.write_text(json.dumps(ui,ensure_ascii=False,indent=2)+'\n')
    print(f'MATERIAL_EXPORT_OK materials={len(actual)} textures={len(parsed["textures"])} bytes={parsed["bytes"]} geometry_unchanged=True')
    print('MATERIAL_WARNINGS',json.dumps(warnings))


if __name__=='__main__':main()
