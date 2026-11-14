"""Deterministic CC0-derived v2 atlases, meter-scaled detail maps and DDS recipe."""
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import gaussian_filter
from PIL import ImageDraw, ImageOps

from assets import ROOT, acquire, sha256
from check_kn5 import inspect_dds, inspect_kn5

SEED = 24024
ROAD_PERIOD = 140.0
MULTILAYER = 'ksMultilayer_fresnel_nm4'
MULTIMAP = 'ksPerPixelMultiMap'


def channel_mips(pixels):
    pixels=np.asarray(pixels)
    if pixels.ndim!=3 or pixels.shape[2] not in (3,4) or min(pixels.shape[:2])<1:
        raise ValueError('Need nonempty RGB/RGBA pixels')
    while True:
        yield pixels
        height,width=pixels.shape[:2]
        if width==height==1:break
        pixels=np.stack([np.asarray(Image.fromarray(pixels[:,:,c]).resize((max(1,width//2),max(1,height//2)),Image.Resampling.BOX)) for c in range(pixels.shape[2])],axis=2)


def data_mips(pixels,fade=False):
    for i,level in enumerate(channel_mips(pixels)):
        if fade and i>=3:
            mean=level.mean((0,1),keepdims=True)
            level=np.rint(mean+(level.astype(float)-mean)*max(.18,1-(i-2)*.11)).clip(0,255).astype('uint8')
        yield level


def encode_data_dds(pixels,path,fade=False):
    folder=path.parent/'.mips';folder.mkdir(exist_ok=True)
    payloads=[];header=None
    for i,level in enumerate(data_mips(pixels,fade)):
        png=folder/f'{path.stem}_{i}.png';dds=png.with_suffix('.dds')
        Image.fromarray(level).save(png)
        subprocess.run(['convert',str(png),'-define','dds:compression=dxt5','-define','dds:mipmaps=0',str(dds)],check=True)
        blob=dds.read_bytes()
        if header is None:header=bytearray(blob[:128])
        payloads.append(blob[128:])
    struct.pack_into('<I',header,8,struct.unpack_from('<I',header,8)[0]|0x20000)
    struct.pack_into('<I',header,28,len(payloads))
    struct.pack_into('<I',header,108,struct.unpack_from('<I',header,108)[0]|0x400008)
    path.write_bytes(header+b''.join(payloads))


def periodic_noise(size, sigma, seed):
    values = np.random.default_rng(seed).random((size,size)).astype(np.float32)
    values = gaussian_filter(values,sigma,mode='wrap')
    return (values-values.mean())/max(float(values.std()),1e-6)


def grade_diffuse(role, pixels):
    pixels=np.asarray(pixels,dtype=np.float32)
    if pixels.ndim!=3 or pixels.shape[2]!=3 or not pixels.size:
        raise ValueError('Expected nonempty RGB pixels')
    targets=dict(asphalt=(83.6,83.6,83.6),repair=(61.6,61.6,63.36),grass=(80,112,48),dirt=(111,116,79),gravel=(139,137,123),sand=(207,189,139))
    if role not in targets:return pixels
    luminance=pixels.mean(2,keepdims=True)
    variation=np.clip(luminance/max(float(luminance.mean()),.01),.45,1.65)
    return np.clip(variation*np.asarray(targets[role],dtype=np.float32)/255,0,1)


def terrain_mask(size, coverage):
    if size<1 or not 0<coverage<1:raise ValueError('Need positive size and fractional coverage')
    noise=.68*periodic_noise(size,max(1,size*.073),SEED+55)+.32*periodic_noise(size,max(1,size*.019),SEED+56)
    dirt=np.clip(.5+(noise-np.quantile(noise,1-coverage))*.45,0,1)
    mask=np.zeros((size,size,4),dtype=np.float32)
    mask[:,:,0]=1-dirt;mask[:,:,1]=dirt
    return mask


def road_atlas(source, variant=0, size=2048,period_m=ROAD_PERIOD,arrows=()):
    if size < 32 or variant not in (0,1,2):
        raise ValueError('Need a usable atlas size and variant 0..2')
    u = (np.arange(size,dtype=np.float32)+.5)/size
    distance = (np.arange(size,dtype=np.float32)+.5)/size*period_m
    noise = periodic_noise(size,max(2,size/150),SEED+variant)
    macro = np.asarray(source.resize((size,size)).filter(ImageFilter.GaussianBlur(size/100)),dtype=np.float32)/255
    luminance = macro.mean(2)
    rows=((distance%28)/28*size).astype(int)
    tone = 1+.04*(luminance[rows]-luminance.mean())+.008*noise[rows]
    tyre = sum(np.exp(-((u-c)/.026)**2) for c in (.14,.36,.64,.86))
    lane_middle = sum(np.exp(-((u-c)/.05)**2) for c in (.25,.75))
    tone *= (1-.035*tyre+.015*lane_middle)[None,:]
    grooves=sum(np.exp(-((u-c-.006*np.sin(distance[:,None]/21))/.009)**2) for c in (.15,.35,.65,.85))
    tone*=1-.022*grooves
    rgb = np.repeat(tone[:,:,None],3,axis=2)
    for crack in range(5):
        center=.12+crack*.18+.014*np.sin(distance/3+crack)+.008*np.sin(distance*1.7+crack)
        shape=np.exp(-((u[None,:]-center[:,None])/.0009)**2)*np.exp(-((distance[:,None]-(crack+1)*ROAD_PERIOD/6)/1.2)**2)
        rgb*=1-.16*shape[:,:,None]
    edge = np.clip((.085-np.minimum(u,1-u))/.085,0,1)[None,:]
    edge = np.clip(edge*(.6+.15*noise),0,.7)
    patch = np.zeros((size,size),dtype=np.float32)
    rng = np.random.default_rng(SEED+100+variant)
    for _ in range(1):
        center = rng.uniform(.1,.9);chainage = rng.uniform(0,period_m)
        du = abs(u-center)[None,:]
        dv = abs((distance[:,None]-chainage+period_m/2)%period_m-period_m/2)
        radius=np.sqrt((du/rng.uniform(.035,.055))**2+(dv/rng.uniform(.45,.8))**2)
        shape=np.clip((1-radius+.08*noise)*3,0,1)
        patch = np.maximum(patch,shape)
    wear = np.clip(.9+.18*noise,0,1)
    edge_lines = ((u>=24/1024)&(u<38/1024))|((u>=986/1024)&(u<1000/1024))
    center_line = (u>=506/1024)&(u<518/1024)
    dash = (distance%7 < 7*440/1024)[:,None]
    paint = np.maximum(edge_lines[None,:],center_line[None,:]*dash).astype(np.float32)*wear
    for chainage in arrows:
        v=period_m-distance[:,None]-chainage
        shaft=(abs(u[None,:]-.75)<.015)&(v> -2.5)&(v<.5)
        head=(v>=.5)&(v<2)&(abs(u[None,:]-.75)<(2-v)*.055)
        paint=np.maximum(paint,(shaft|head)*wear*.85)
    paint *= np.clip(.9+noise*.2,0,1)
    rgb = rgb*(1-paint[:,:,None])+np.array([.88,.86,.77],dtype=np.float32)*paint[:,:,None]
    weights = np.stack([(1-patch)*(1-edge),patch*(1-edge),np.broadcast_to(edge,patch.shape),np.zeros_like(patch)],axis=2)
    weights *= 1-paint[:,:,None]
    weights[:,:,3] = paint
    return np.clip(rgb,0,1),weights


def packed_maps(roughness, metal=False):
    roughness = np.clip(np.asarray(roughness,dtype=np.float32),0,1)
    if roughness.ndim != 2:
        raise ValueError('Expected a 2D roughness map')
    gloss = 1-roughness
    return np.stack([(.35 if metal else .12)*gloss+.04,.12+.8*gloss**2,
                     (.55 if metal else .08)*gloss+.025],axis=2)


def source_maps(asset):
    if 'archive' in asset['files']:
        with zipfile.ZipFile(ROOT/asset['files']['archive']['path']) as archive:
            def read(suffix):
                name = next(n for n in archive.namelist() if n.endswith(suffix))
                return Image.open(io.BytesIO(archive.read(name))).convert('RGB').copy()
            return read('_Color.png'),read('_NormalGL.png'),read('_Roughness.png').convert('L')
    return tuple(Image.open(ROOT/asset['files'][role]['path']).convert('L' if role=='roughness' else 'RGB') for role in ('diffuse','normal','roughness'))


def material_spec(shader, properties, textures, **preview):
    return dict(shaderName=shader,alphaBlendMode='Opaque',alphaTested=False,depthMode='DepthNormal',
                properties={k:dict(valueA=float(v)) for k,v in properties.items()},
                textures={k:dict(textureName=v) for k,v in textures.items()},preview=preview)


def generate(manifest):
    output = ROOT/'textures/v2'
    output.mkdir(parents=True,exist_ok=True)
    records = {}
    def dds(name, pixels, alpha=False, data_channels=False):
        pixels = np.asarray(pixels)
        if pixels.ndim != 3 or pixels.shape[2] not in (3,4):
            raise ValueError('Expected RGB/RGBA pixels')
        if pixels.dtype != np.uint8:
            pixels = np.rint(np.clip(pixels,0,1)*255).astype('uint8')
        png = output/(name+'.png')
        Image.fromarray(pixels).save(png)
        path = output/(name+'.dds')
        if data_channels:encode_data_dds(pixels,path,fade=name in ('terrain_mask','terrain_mountain_mask'))
        else:subprocess.run(['convert',str(png),'-define','dds:compression='+('dxt5' if alpha else 'dxt1'),str(path)],check=True)
        record = inspect_dds(path.read_bytes())
        record.update(sha256=sha256(path),file=str(path.relative_to(ROOT)))
        records[path.name] = record
        return path.name
    sources = {a['role']:source_maps(a) for a in manifest['assets']}
    maps = {}
    for role,(diffuse,normal,roughness) in sources.items():
        diffuse = np.asarray(diffuse.resize((1024,1024)),dtype=np.float32)/255
        normal = np.asarray(normal.resize((1024,1024)),dtype=np.float32)/255
        roughness = np.asarray(roughness.resize((1024,1024)),dtype=np.float32)/255
        diffuse=grade_diffuse(role,diffuse)
        if role in ('grass','dirt','gravel','rock'):
            broad=periodic_noise(1024,100,SEED+61);fine=periodic_noise(1024,13,SEED+62)
            diffuse*=np.clip(1+.065*broad[:,:,None]+.025*fine[:,:,None],.77,1.22)
        if role=='rock':
            strata=np.sin(np.arange(1024)[:,None]/15+periodic_noise(1024,65,SEED+63)*.4)
            moss=np.clip(periodic_noise(1024,24,SEED+64)-.6,0,1)*.22
            diffuse=diffuse*(1-.04*strata[:,:,None])*(1-moss[:,:,None])+np.array([.26,.31,.16])*moss[:,:,None]
        if role=='plaster':
            diffuse = .86+.12*(diffuse-diffuse.mean(axis=(0,1)))
        if role=='metal':
            spangle = periodic_noise(1024,6,SEED+75)
            diffuse = np.clip(.57+(diffuse-diffuse.mean())*.25+spangle[:,:,None]*.025,0,1)
            roughness = np.clip(.4+roughness*.3,0,1)
        strength = .35 if role in ('asphalt','repair','metal') else .65
        normal[:,:,:2] = .5+(normal[:,:,:2]-.5)*strength
        normal[:,:,2] = np.sqrt(np.maximum(0,1-np.sum((normal[:,:,:2]*2-1)**2,axis=2)))*.5+.5
        normal[:,:,1] = 1-normal[:,:,1]
        alpha = np.ones((*roughness.shape,1),dtype=np.float32)
        alpha_detail = role in ('asphalt','repair','gravel','grass','dirt')
        diffuse_pixels = np.concatenate([diffuse,.25+.45*(1-roughness[:,:,None])],axis=2) if alpha_detail else diffuse
        maps[role] = dict(diffuse=dds(role+'_diffuse',diffuse_pixels,alpha_detail,alpha_detail),
                          normal=dds(role+'_normal',np.concatenate([normal,alpha],axis=2),True),
                          maps=dds(role+'_maps',packed_maps(roughness,role=='metal')))
    white = dds('white',np.ones((16,16,3),dtype=np.float32))
    flat = dds('flat_normal',np.tile(np.array([.5,.5,1,1]),(16,16,1)),True)
    base = dict(ksAmbient=.4,ksDiffuse=.6,ksSpecular=.12,ksSpecularEXP=24,
                fresnelC=.015,fresnelEXP=5,fresnelMaxLevel=.12,isAdditive=0,useDetail=0,detailUVMultiplier=1)
    specs = {}
    for role in ('gravel','rock','sand','plaster','bark','metal'):
        props = dict(base)
        if role=='metal':props.update(ksSpecular=.5,ksSpecularEXP=65,fresnelC=.12,fresnelMaxLevel=.6)
        specs[role] = material_spec(MULTIMAP,props,dict(txDiffuse=maps[role]['diffuse'],txNormal=maps[role]['normal'],txMaps=maps[role]['maps'],txDetail=white),kind='simple',tile_m=dict(gravel=2,rock=6,sand=4,plaster=3,bark=2,metal=1)[role],roughness=.65 if role!='metal' else .45)
    kerb_color = np.asarray(sources['plaster'][0].resize((1024,1024)),dtype=np.float32)/255
    kerb_color = np.clip(.55+(kerb_color-kerb_color.mean())*.5,0,1)
    specs['kerb'] = material_spec(MULTIMAP,base,dict(txDiffuse=dds('kerb_diffuse',kerb_color),txNormal=maps['plaster']['normal'],txMaps=maps['plaster']['maps'],txDetail=white),kind='simple',tile_m=2,roughness=.8)
    layer_props = dict(ksAmbient=.4,ksDiffuse=.6,ksSpecularEXP=28,fresnelC=.012,
                       fresnelEXP=5,fresnelMaxLevel=.16,tarmacSpecularMultiplier=.16,
                       magicMult=1,multTilingFix=0,tilingFixR=0,tilingFixG=0,tilingFixB=0,tilingFixA=0,
                       extColoredReflection=0,extColoredReflectionNorm=0,extLocalAO=0,detailNMMult=1)
    for variant in range(3):
        color,mask = road_atlas(sources['asphalt'][0],variant)
        textures = dict(txDiffuse=dds(f'road_{variant}_macro',color),txMask=dds(f'road_{variant}_mask',mask,True,True))
        textures.update({f'txDetail{c}':maps[r]['diffuse'] for c,r in zip('RGB',('asphalt','repair','gravel'))})
        textures['txDetailA']=white
        textures.update({f'txNormal{c}':maps[r]['normal'] for c,r in zip('RGB',('asphalt','repair','gravel'))})
        textures['txNormalA']=flat
        props = dict(layer_props,**{f'mult{c}':1/1.75 for c in 'RGBA'})
        specs['asphalt' if variant==0 else f'asphalt_v{variant}'] = material_spec(MULTILAYER,props,textures,kind='road',period_m=ROAD_PERIOD,roughness=.84)
    from road_arrows import select_junctions
    centerline=np.load(ROOT/'data/centerline.npz');origin=json.loads((ROOT/'data/geo_origin.json').read_text())
    junctions=select_junctions(centerline,json.loads((ROOT/'data/area_cache.json').read_text())['ways'],np.array([origin['easting_m'],origin['northing_m']]))
    for i,junction in enumerate(junctions):
        name=f'asphalt_junction_{i}'
        color,mask=road_atlas(sources['asphalt'][0],junction['chunk']%3,period_m=400,arrows=[junction['chainage_m']%400])
        textures=dict(specs['asphalt']['textures']);textures={k:v['textureName'] for k,v in textures.items()}
        textures.update(txDiffuse=dds(name+'_macro',color),txMask=dds(name+'_mask',mask,True,True))
        specs[name]=material_spec(MULTILAYER,dict(props),textures,kind='road',period_m=400,roughness=.84)
        junction['material']=name
    size = 2048
    noise = periodic_noise(size,150,SEED+55)
    mask = terrain_mask(size,.35)
    medium=periodic_noise(size,28,SEED+57);fine=periodic_noise(size,6,SEED+58)
    tint = np.repeat(np.clip(.9+.045*noise+.025*medium+.012*fine,.72,1)[:,:,None],3,axis=2)
    textures = dict(txDiffuse=dds('terrain_macro',tint),txMask=dds('terrain_mask',mask,True,True))
    textures.update({f'txDetail{c}':maps[r]['diffuse'] for c,r in zip('RGBA',('grass','dirt','grass','dirt'))})
    textures.update({f'txNormal{c}':maps[r]['normal'] for c,r in zip('RGBA',('grass','dirt','grass','dirt'))})
    props = dict(layer_props,**{f'mult{c}':1/4 for c in 'RGBA'})
    props.update(fresnelMaxLevel=.04,tarmacSpecularMultiplier=.03)
    specs['grass'] = material_spec(MULTILAYER,props,textures,kind='terrain',period_m=256,roughness=.95)
    mountain_textures=dict(textures,txMask=dds('terrain_mountain_mask',terrain_mask(size,.25),True,True))
    specs['grass_mountain']=material_spec(MULTILAYER,props,mountain_textures,kind='terrain',period_m=256,roughness=.95)
    used = {v['textureName'] for spec in specs.values() for v in spec['textures'].values()}
    records = {k:v for k,v in records.items() if k in used}
    info = dict(version=2,seed=SEED,normal_format='DXT5, DirectX green; RGB XYZ, no BC5',materials=specs,textures=records,junction_arrows=junctions,
                dds_gpu_bytes=sum(v['gpu_bytes'] for v in records.values()))
    (ROOT/'data/materials_info.json').write_text(json.dumps(info,indent=2)+'\n')
    print(f'MATERIAL_TEXTURES_OK used_dds={len(records)} gpu_bytes={info["dds_gpu_bytes"]}')
    return info


def build(blender):
    generate(acquire())
    export(blender)


def export_report():
    info=json.loads((ROOT/'data/materials_info.json').read_text())
    parsed=inspect_kn5(ROOT/'out/bejaia_saket/bejaia_saket.kn5')
    meshes=[n for n in parsed['nodes'] if n['kind']==2]
    objects=len({n['name'] for n in meshes})
    report=dict(file='out/bejaia_saket/bejaia_saket.kn5',bytes=parsed['bytes'],
                seconds=info['export_seconds'],sha256=info['kn5_sha256'],warnings=info['warnings'],
                mesh_objects=objects,export_meshes=len(meshes),vertex_limit_splits=len(meshes)-objects,
                max_exported_vertices=max(n['vertices'] for n in meshes),
                triangles=sum(n['triangles'] for n in meshes),materials=len(parsed['materials']),
                textures=len(parsed['textures']),material_recipe='data/materials_info.json')
    (ROOT/'data/kn5_export_info.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def export(blender):
    env = os.environ.copy()
    runtime = Path('/run/user')/str(os.getuid())
    if not env.get('XDG_RUNTIME_DIR') and runtime.is_dir():env['XDG_RUNTIME_DIR']=str(runtime)
    subprocess.run([blender,'-b',str(ROOT/'blend/bejaia_saket.blend'),'--python-exit-code','1','-P',str(ROOT/'scripts/blender_materials.py')],check=True,cwd=ROOT,env=env)
    export_report()
    package_output()


def package_output():
    for name in ('README.md','CREDITS.md'):shutil.copy2(ROOT/name,ROOT/'out/bejaia_saket'/name)
    from csp import generate as generate_csp
    generate_csp()
    from package import package
    package()


def render(blender, views=None):
    comparison=ROOT/'out/preview'/('csp_material_fixes' if views else 'v2_materials')
    comparison.mkdir(parents=True,exist_ok=True)
    baseline=comparison/'v1.blend'
    if views:
        (comparison/'before').mkdir(exist_ok=True)
        for name in views:shutil.copy2(ROOT/'out/preview/v2_materials/before'/(name+'.png'),comparison/'before'/(name+'.png'))
    else:
        with baseline.open('wb') as output:
            subprocess.run(['git','show','v1:blend/bejaia_saket.blend'],cwd=ROOT,stdout=output,check=True)
    scenes=(('after',ROOT/'blend/bejaia_saket.blend'),) if views else (('before',baseline),('after',ROOT/'blend/bejaia_saket.blend'))
    for label,scene in scenes:
        subprocess.run([blender,'-b',str(scene),'--python-exit-code','1','-P',str(ROOT/'scripts/blender_material_preview.py'),'--',label,*(views or [])],check=True,cwd=ROOT,env=dict(os.environ,BS_COMPARISON_DIR=str(comparison)))
    names=views or ('road_10','road_40','road_70','road_95','decor_town','decor_saket')
    canvas = Image.new('RGB',(1536,len(names)*454),(25,25,25))
    draw = ImageDraw.Draw(canvas)
    for i,name in enumerate(names):
        for j,label in enumerate(('before','after')):
            image = Image.open(comparison/label/(name+'.png')).convert('RGB')
            canvas.paste(ImageOps.fit(image,(768,432)),(j*768,i*454+22))
            draw.text((j*768+8,i*454+5),name+' / '+label+' (Cycles CPU approximation)',fill='white')
    canvas.save(comparison/'side_by_side.jpg',quality=92)
    ImageOps.fit(Image.open(comparison/'after'/('road_70.png' if 'road_70' in names else names[0]+'.png')).convert('RGB'),(355,200),method=Image.Resampling.LANCZOS).save(ROOT/'out/bejaia_saket/ui/preview.png')
    baseline.unlink(missing_ok=True)
    package_output()
