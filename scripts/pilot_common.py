"""Shared data and PBR preparation for the isolated summit pilot (Blender 3.6)."""
from pathlib import Path
import configparser
import hashlib
import io
import json
import math
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parent
ASSETS=WORK/'assets'
DATA=ROOT/'data/pilot300'
OUT=ROOT/'out/bejaia_saket_pilot300'
TEX=ROOT/'textures/v2'
PREVIEW=ROOT/'out/preview/pilot300'
sys.path[:0]=[str(WORK/'tools/pydeps'),str(WORK/'tools/addons'),str(ROOT/'scripts')]
import numpy as np
from PIL import Image, ImageDraw
from check_kn5 import inspect_dds


def pilot_csp_config(source,guard_material):
    config=configparser.ConfigParser(interpolation=None)
    config.optionxform=str
    config.read_string(source)
    config['GRASS_FX']['GRASS_MATERIALS']='forest_floor'
    for section in ('GRASS_FX_ADJUSTMENT_0','GRASS_FX_CONFIGURATION_A'):
        config.remove_section(section)
    for key,extra in (
        ('SOAKING_MATERIALS',['rock_moss_set_01']),
        ('SMOOTH_MATERIALS',[guard_material]),
        ('ROUGH_MATERIALS',['forest_floor','landcover']),
    ):
        names=[name.strip() for name in config['RAIN_FX'].get(key,'').split(',') if name.strip()]
        config['RAIN_FX'][key]=', '.join(dict.fromkeys(names+extra))
    output=io.StringIO();config.write(output)
    return '; Pilot-specific selectors derived from the main CSP config; see docs/CSP_NOTES.md.\n'+output.getvalue().rstrip()+'\n'


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')


def replace_material_slots(mesh,convert):
    indices=[p.material_index for p in mesh.polygons]
    for index,material in enumerate(tuple(mesh.materials)):
        mesh.materials[index]=convert(material)
    if indices!=[p.material_index for p in mesh.polygons]:
        raise ValueError('Material replacement changed polygon assignments')


def foliage_image_metrics(image):
    pixels=np.asarray(image.convert('RGBA'));mask=pixels[:,:,3]>=128
    coverage=float(mask.mean())
    if not .001<coverage<.99:raise ValueError('Empty or fully opaque foliage image')
    colors=pixels[:,:,:3][mask]
    white_fraction=float(np.mean(np.min(colors,axis=1)>=245))
    if white_fraction>.1:raise ValueError('White foliage bake: material assignment lost')
    return dict(alpha_coverage=coverage,white_fraction=white_fraction,rgb_mean=colors.mean(0).tolist())


def source_data():
    with np.load(ROOT/'data/centerline.npz') as source:
        return {key:source[key].copy() for key in source.files}


def interpolate(values,station,stations,axis=0):
    values=np.moveaxis(np.asarray(values),axis,0)
    shape=np.shape(station)
    result=np.stack([np.interp(station,stations,column) for column in values.reshape(len(stations),-1).T],axis=-1)
    return result.reshape((*shape,*values.shape[1:]))


def select_sector(full):
    stations=full['s3']
    peak=float(stations[int(np.argmax(full['z']))])
    heading=np.unwrap(np.arctan2(full['tangent'][:,1],full['tangent'][:,0]))
    candidates=np.arange(peak-240,peak-59,10)
    def score(start):
        angles=np.interp(np.linspace(start,start+300,151),stations,heading)
        return float(np.abs(np.diff(angles)).sum())-.0002*abs(start+150-peak)
    start=float(max(candidates,key=score));end=start+300
    selected=(stations>start)&(stations<end)
    keep=np.r_[start,stations[selected],end]
    data={}
    for name in ('xy','z','width','normal','tangent','s'):
        data[name]=interpolate(full[name],keep,stations)
    for name in ('sides','offsets'):
        data[name]=np.moveaxis(interpolate(full[name],keep,stations,axis=1),0,1)
    data['source_s']=data['s'].copy()
    data['s']-=data['s'][0]
    data['s3']=keep-start
    data['source_s3']=keep
    actual=np.r_[0,np.cumsum(np.linalg.norm(np.diff(np.column_stack([data['xy'],data['z']]),axis=0),axis=1))]
    assert abs(actual[-1]-300)<1e-6
    native=np.column_stack([full['xy'][selected],full['z'][selected]])
    assert np.array_equal(np.column_stack([data['xy'][1:-1],data['z'][1:-1]]),native)
    meta=dict(length_3d_m=float(actual[-1]),active_start_3d_m=start,active_end_3d_m=end,summit_3d_m=peak,summit_inside_pilot_m=peak-start,turn_degrees=float(np.ptp(np.interp(keep,stations,heading))*180/np.pi),native_centerline_samples_preserved=len(native),spawn_in_pilot_m=12,start_gate_m=15,finish_gate_m=280,main_layout_unchanged=True,tree_species='Scots pine, NOT Aleppo pine',runtime_tested=False)
    DATA.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(DATA/'centerline.npz',**data)
    dump(DATA/'selection.json',meta)
    return data,meta


def frame(data,station):
    stations=data['s3']
    point=interpolate(np.column_stack([data['xy'],data['z']]),station,stations)
    tangent=interpolate(data['tangent'],station,stations)
    tangent/=np.linalg.norm(tangent)
    return point,np.array([*tangent,0.]),np.array([-tangent[1],tangent[0],0.])


def ground(data,station,side,distance):
    grid=interpolate(data['sides'][side],station,data['s3'])
    center,_,_=frame(data,station)
    offset=np.linalg.norm(grid[:,:2]-center[:2],axis=1)
    vector=grid[0,:2]-center[:2];vector/=np.linalg.norm(vector)
    xy=center[:2]+vector*distance
    z=float(np.interp(distance,offset,grid[:,2]))
    return np.array([*xy,z])


def dds(image,path,coverage=False):
    image=image.convert('RGBA')
    base=np.asarray(image)
    target=float(np.mean(base[:,:,3]>=128))
    chunks=[];header=None;level=0
    while True:
        array=np.array(image)
        if coverage and level and image.width>=16 and 0<target<1:
            alpha=array[:,:,3].astype(float);lo,hi=0.,12.
            for _ in range(18):
                mid=(lo+hi)/2
                if np.mean(alpha*mid>=128)<target:lo=mid
                else:hi=mid
            scale=min((1.,lo,hi),key=lambda v:abs(float(np.mean(alpha*v>=128))-target))
            array[:,:,3]=np.clip(alpha*scale,0,255).astype('uint8')
        stream=io.BytesIO();Image.fromarray(array).save(stream,format='DDS',pixel_format='DXT5')
        blob=stream.getvalue()
        if header is None:header=bytearray(blob[:128])
        chunks.append(blob[128:])
        if image.size==(1,1):break
        image=image.resize((max(1,image.width//2),max(1,image.height//2)),Image.Resampling.BOX)
        level+=1
    struct.pack_into('<I',header,8,struct.unpack_from('<I',header,8)[0]|0x20000)
    struct.pack_into('<I',header,28,len(chunks))
    struct.pack_into('<I',header,108,struct.unpack_from('<I',header,108)[0]|0x400008)
    blob=bytes(header)+b''.join(chunks)
    inspect_dds(blob)
    path.write_bytes(blob)
    return path.name


def image_pixels(image_or_path,mode='RGB',size=1024):
    import bpy
    image=image_or_path if hasattr(image_or_path,'pixels') else None
    if image is not None and image.packed_file:
        try:
            result=Image.open(io.BytesIO(image.packed_file.data)).convert(mode)
            return result.resize((size,size),Image.Resampling.LANCZOS)
        except OSError:pass
    path=Path(bpy.path.abspath(image.filepath)) if image else Path(image_or_path)
    if path.exists() and path.suffix.lower()!='.exr':
        with Image.open(path) as source:return source.convert(mode).resize((size,size),Image.Resampling.LANCZOS)
    loaded=image or bpy.data.images.load(str(path),check_existing=True)
    loaded.colorspace_settings.name='Non-Color'
    width,height=loaded.size
    pixels=np.empty(width*height*4,dtype=np.float32);loaded.pixels.foreach_get(pixels)
    array=(pixels.reshape(height,width,4)[::-1]*255).clip(0,255).astype('uint8')
    return Image.fromarray(array).convert(mode).resize((size,size),Image.Resampling.LANCZOS)


def properties(**values):return {key:dict(valueA=float(value)) for key,value in values.items()}


def pbr_material(name,diffuse,normal=None,roughness=None,alpha=None,metal=False,foliage=False):
    stem='PH_'+''.join(c if c.isalnum() else '_' for c in name)
    color=image_pixels(diffuse,'RGBA')
    rough=image_pixels(roughness,'L') if roughness is not None else Image.new('L',color.size,155)
    if alpha is not None:color.putalpha(image_pixels(alpha,'L'))
    diffuse_name=dds(color,TEX/(stem+'_diff.dds'),coverage=foliage)
    if normal is not None:
        array=np.asarray(image_pixels(normal,'RGB')).copy();array[:,:,1]=255-array[:,:,1]
        normal_name=dds(Image.fromarray(array),TEX/(stem+'_normal.dds'))
    else:normal_name='flat_normal.dds'
    r=np.asarray(rough,dtype=np.float32)/255;gloss=1-r
    packed=np.stack([(.35 if metal else .12)*gloss+.04,.12+.8*gloss**2,(.55 if metal else .08)*gloss+.025],axis=2)
    maps_name=dds(Image.fromarray(np.uint8(np.clip(packed*255,0,255))),TEX/(stem+'_maps.dds'))
    textures=dict(txDiffuse=dict(textureName=diffuse_name),txNormal=dict(textureName=normal_name),txMaps=dict(textureName=maps_name),txDetail=dict(textureName='white.dds'))
    spec=dict(shaderName='ksPerPixelMultiMap',alphaBlendMode='Opaque',alphaTested=False,depthMode='DepthNormal',properties=properties(ksAmbient=.4,ksDiffuse=.6,ksSpecular=.5 if metal else .12,ksSpecularEXP=65 if metal else 24,fresnelC=.12 if metal else .015,fresnelEXP=5,fresnelMaxLevel=.6 if metal else .12,isAdditive=0,useDetail=0,detailUVMultiplier=1),textures=textures,preview=dict(kind='simple',tile_m=1,roughness=float(r.mean())))
    if foliage:
        spec.update(shaderName='ksPerPixelAT',alphaBlendMode='AlphaToCoverage',alphaTested=True)
        spec['preview']['kind']='foliage'
    return spec


def tree_palette(prototypes,info):
    for material in set(m for o in prototypes for m in o.data.materials if m):
        images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
        def find(fragment):return next((i for i in images if fragment in Path(i.filepath).stem.lower()),None)
        diffuse=find('_diff')
        if diffuse is None:raise ValueError('Missing CC0 diffuse: '+material.name)
        alpha=find('_alpha');foliage=alpha is not None
        spec=pbr_material(material.name,diffuse,find('_nor_gl'),find('_rough'),alpha=alpha,foliage=foliage)
        info['materials'][material.name]=spec
    return info


def asphalt(info):
    folder=ASSETS/'worn_asphalt_4k.blend/textures'
    color=image_pixels(folder/'worn_asphalt_diff_4k.jpg','RGB')
    normal=image_pixels(folder/'worn_asphalt_nor_gl_4k.exr','RGB')
    rough=image_pixels(folder/'worn_asphalt_rough_4k.exr','L')
    rgb=np.asarray(color,dtype=float)/255
    # Use the existing asphalt luminance target; retain photographic fine detail.
    luminance=rgb.mean(axis=2,keepdims=True)
    rgb=np.clip(luminance/max(float(luminance.mean()),.01),.45,1.65)*(83.6/255)
    r=np.asarray(rough,dtype=float)/255
    pixels=np.concatenate([np.repeat(rgb,3,axis=2),(.25+.45*(1-r))[:,:,None]],axis=2)
    diff=dds(Image.fromarray(np.uint8(np.clip(pixels*255,0,255))),TEX/'PH_worn_asphalt_diff.dds')
    nm=np.asarray(normal,dtype=float)/255
    nm[:,:,:2]=.5+(nm[:,:,:2]-.5)*.35
    nm[:,:,2]=np.sqrt(np.maximum(0,1-np.sum((nm[:,:,:2]*2-1)**2,axis=2)))*.5+.5
    nm[:,:,1]=1-nm[:,:,1]
    norm=dds(Image.fromarray(np.uint8(np.clip(nm*255,0,255))),TEX/'PH_worn_asphalt_normal.dds')
    for name,spec in info['materials'].items():
        if not name.startswith('asphalt'):continue
        spec['textures']['txDetailR']['textureName']=diff
        spec['textures']['txNormalR']['textureName']=norm
        spec['properties']['multR']['valueA']=.5
        spec['preview']['roughness']=float(r.mean())


def mesh_counts(report):
    meshes=[node for node in report['nodes'] if 'vertices' in node]
    return dict(vertices=sum(n['vertices'] for n in meshes),triangles=sum(n['triangles'] for n in meshes),meshes=len(meshes),max_mesh_vertices=max(n['vertices'] for n in meshes))
