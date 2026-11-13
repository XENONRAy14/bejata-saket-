"""AC metadata and placements. Conventions and unresolved claims: docs/AC_NOTES.md."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'out/bejaia_saket'
SURFACE_SOURCE = 'https://site.hagn.io/assettocorsa/modding/tracks/data/surfaces-ini'
MAP_SOURCE = 'https://raw.githubusercontent.com/cj123/assetto-server-manager/master/cmd/server-manager/typescript/src/RaceControl.ts#L491-L497'


def validate(data):
    s = np.asarray(data['s'])
    if len(s) < 2 or not np.isfinite(s).all() or (np.diff(s) <= 0).any():
        raise ValueError('Need increasing finite centerline chainage')
    for key,shape in [('xy',(len(s),2)),('tangent',(len(s),2)),('z',(len(s),)),('width',(len(s),))]:
        value = np.asarray(data[key])
        if value.shape != shape or not np.isfinite(value).all():
            raise ValueError(f'Invalid centerline {key}')
    if (data['width'] <= 0).any():
        raise ValueError('Road width must be positive')


def road_point(data, chainage):
    s = data['s']
    if not s[0] <= chainage <= s[-1]:
        raise ValueError('Placement outside the road')
    xy = np.array([np.interp(chainage,s,data['xy'][:,j]) for j in range(2)])
    tangent = np.array([np.interp(chainage,s,data['tangent'][:,j]) for j in range(2)])
    if np.linalg.norm(tangent) < 1e-8:
        raise ValueError('Missing road direction')
    tangent /= np.linalg.norm(tangent)
    return xy,tangent,float(np.interp(chainage,s,data['z'])),float(np.interp(chainage,s,data['width']))


def plan_empties(data):
    validate(data)
    s = data['s']
    if s[-1]-s[0] < 500:
        raise ValueError('Need room for staging and finish runoff')
    heading = np.unwrap(np.arctan2(data['tangent'][:,1],data['tangent'][:,0]))
    def heading_range(start):
        values = np.interp(np.linspace(start,start+120,121),s,heading)
        return float(np.ptp(values)*180/np.pi)
    start = next((float(a) for a in np.arange(s[0],min(s[0]+1000,s[-1]-220),5) if heading_range(a) <= 3),None)
    if start is None:
        raise ValueError('No reasonably straight 120 m staging section near start')
    seams = np.unique(np.r_[s[0],s[np.searchsorted(s,np.arange(400,s[-1],400))],s[-1]])
    def clear_seam(chainage):
        return chainage+3 if np.min(abs(seams-chainage)) < 2 else chainage
    empties = []
    def place(name,chainage,lateral):
        xy,tangent,z,width = road_point(data,chainage)
        offset = lateral*width
        xy += np.array([-tangent[1],tangent[0]])*offset
        yaw = math.atan2(tangent[0],-tangent[1])
        empties.append(dict(name=name,chainage_m=chainage,position_m=[*xy,z+1.5],yaw_deg=math.degrees(yaw),lateral_m=offset,road_height_m=z,chunk_seam_distance_m=float(np.min(abs(seams-chainage)))))
    for i in range(4):
        place(f'AC_PIT_{i}',clear_seam(start+15+8*i),-.25+(.02 if i%2 else -.02))
    place('AC_START_0',clear_seam(start+63),-.25)
    place('AC_START_1',clear_seam(start+55),-.25)
    place('AC_HOTLAP_START_0',clear_seam(start+70),-.25)
    gate_start = clear_seam(start+80)
    finish = clear_seam(float(s[-1]-50))
    def gate(prefix,chainage):
        for letter,lateral in [('L',.5),('R',-.5)]:
            place(f'{prefix}_{letter}',chainage,lateral)
    gate('AC_AB_START',gate_start)
    gate('AC_AB_FINISH',finish)
    for i,fraction in enumerate((1/3,2/3)):
        gate(f'AC_TIME_{i}',clear_seam(gate_start+(finish-gate_start)*fraction))
    return dict(empties=empties,initial_120m_heading_range_deg=heading_range(float(s[0])),staging_start_m=start,staging_end_m=start+120,staging_heading_range_deg=heading_range(start),start_gate_m=gate_start,finish_gate_m=finish,finish_runoff_m=float(s[-1]-finish),timed_length_m=finish-gate_start,spawn_height_offset_m=1.5,timing_convention='AB start/finish; TIME_0 and TIME_1 internal thirds per docs/AC_NOTES.md section 6; UNVERIFIED in AC')


def map_transform(xy, max_size=1600, padding=20):
    xy = np.asarray(xy)
    if xy.ndim != 2 or xy.shape[1] != 2 or len(xy) < 2 or not np.isfinite(xy).all() or max_size <= 2*padding:
        raise ValueError('Need finite route and usable map size')
    world = xy*np.array([1,-1])
    lower,upper = world.min(axis=0),world.max(axis=0)
    scale = float(np.max(upper-lower)/(max_size-2*padding))
    if scale <= 0:
        raise ValueError('Map route has zero extent')
    size = np.minimum(max_size,np.ceil((upper-lower)/scale+2*padding)).astype(int)
    offset = padding*scale-lower
    return dict(WIDTH=int(size[0]),HEIGHT=int(size[1]),MARGIN=0,SCALE_FACTOR=scale,MAX_SIZE=max_size,X_OFFSET=float(offset[0]),Z_OFFSET=float(offset[1]),DRAWING_SIZE=10)


def map_pixels(xy, transform):
    return (np.asarray(xy)*[1,-1]+[transform['X_OFFSET'],transform['Z_OFFSET']])/transform['SCALE_FACTOR']


def draw_route(xy,size,padding=10,line_width=2):
    xy = np.asarray(xy)
    lower,upper = xy.min(axis=0),xy.max(axis=0)
    scale = min((size[0]-2*padding)/max(upper[0]-lower[0],1e-9),(size[1]-2*padding)/max(upper[1]-lower[1],1e-9))
    points = (xy-(lower+upper)/2)*scale+np.array(size)/2
    image = Image.new('RGBA',(size[0]*3,size[1]*3),(0,0,0,0))
    ImageDraw.Draw(image).line([tuple(p*3) for p in points],fill=(255,255,255,255),width=line_width*3,joint='curve')
    return image.resize(size,Image.Resampling.LANCZOS)


def surfaces_text():
    base = dict(FRICTION='1',DAMPING='0',WAV='',WAV_PITCH='0',FF_EFFECT='NULL',DIRT_ADDITIVE='0',IS_VALID_TRACK='1',BLACK_FLAG_TIME='0',SIN_HEIGHT='0',SIN_LENGTH='0',IS_PITLANE='0',VIBRATION_GAIN='0',VIBRATION_LENGTH='0')
    kerb = dict(base,WAV='kerb.wav',WAV_PITCH='1.3',FF_EFFECT='1',FRICTION='.92',VIBRATION_GAIN='.1',VIBRATION_LENGTH='.2')
    definitions = [('ROAD',base,'ASPHALT example copied; KEY rename to ROAD is project choice.'),('KERB',kerb,'KERB example copied.'),('GRASS',dict(base,FRICTION='.65',DAMPING='.1',DIRT_ADDITIVE='1',IS_VALID_TRACK='0'),'ASPHALT base; friction .65, damping .1, dirt 1 and validity 0 ASSUMED.'),('GRAVEL',dict(base,FRICTION='.75',DAMPING='.05',DIRT_ADDITIVE='1',IS_VALID_TRACK='0'),'ASPHALT base; friction .75, damping .05, dirt 1 and validity 0 ASSUMED.'),('WALL',base,'ASPHALT base ASSUMED for WALL; collision naming is special, rolling parameters UNVERIFIED.')]
    blocks = [f'; Source: {SURFACE_SOURCE}\n; See docs/AC_NOTES.md section 1. Example values, NOT stock defaults.\n; Overrides, sound availability and driving behavior UNVERIFIED in AC.']
    for i,(key,values,note) in enumerate(definitions):
        blocks.append(f'; {note}\n[SURFACE_{i}]\nKEY={key}\n'+'\n'.join(f'{k}={v}' for k,v in values.items()))
    return '\n\n'.join(blocks)+'\n'


def exporter_settings():
    materials = {}
    for name in ('asphalt','grass','gravel','rock','metal','kerb'):
        materials[name] = dict(shaderName='ksPerPixel',alphaBlendMode='Opaque',alphaTested=False,depthMode='DepthNormal',properties={key:dict(valueA=value) for key,value in dict(ksAmbient=.4,ksDiffuse=.4,ksSpecular=.5 if name=='metal' else .1,ksSpecularEXP=20 if name=='metal' else 10).items()},textures=dict(txDiffuse=dict(textureName=f'{name}.png')))
    return dict(materials=materials,nodes={'1*':dict(lodIn=0,lodOut=10000,castShadows=True,visible=True,renderable=True)})


def write_files(data, output=OUTPUT):
    plan = plan_empties(data)
    for folder in ('data','ui','ai','docs'):
        (output/folder).mkdir(parents=True,exist_ok=True)
    (output/'data/surfaces.ini').write_text(surfaces_text(),encoding='utf-8')
    route = json.loads((ROOT/'data/route_info.json').read_text())
    lon,lat = route['start']['coords']
    ui = dict(name='Béjaïa – Saket (RN24)',description='Coastal RN24 from Béjaïa to Saket. Point-to-point mountain road; provisional DSM-derived geometry. © OpenStreetMap contributors; produced using Copernicus WorldDEM-30; see CREDITS.md.',tags=['point-to-point','mountain','coastal'],geotags=[str(lat),str(lon)],country='Algeria',city='Béjaïa',length=f"{data['s'][-1]:.0f}m",width=f"{data['width'].min():.1f}m-{data['width'].max():.1f}m",pitboxes='4',run='Béjaïa → Saket · point-to-point',author='frite',version='0.1',year=2026,url='')
    (output/'ui/ui_track.json').write_text(json.dumps(ui,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ImageOps.fit(Image.open(ROOT/'out/preview/road_70.png').convert('RGB'),(355,200),method=Image.Resampling.LANCZOS).save(output/'ui/preview.png')
    draw_route(data['xy']*[1,-1],(355,200)).save(output/'ui/outline.png')
    transform = map_transform(data['xy'])
    pixels = map_pixels(data['xy'],transform)
    image = Image.new('RGBA',(transform['WIDTH']*3,transform['HEIGHT']*3),(0,0,0,0))
    ImageDraw.Draw(image).line([tuple(p*3) for p in pixels],fill=(255,255,255,255),width=9,joint='curve')
    image.resize((transform['WIDTH'],transform['HEIGHT']),Image.Resampling.LANCZOS).save(output/'map.png')
    (output/'data/map.ini').write_text('; Coordinate formula verified in third-party code: '+MAP_SOURCE+'\n; MARGIN=0 is assumed: padding is already baked into offsets.\n; MAX_SIZE / DRAWING_SIZE from Hagn sample; engine semantics UNVERIFIED.\n[PARAMETERS]\n'+'\n'.join(f'{key}={value}' for key,value in transform.items())+'\n',encoding='utf-8')
    (output/'settings.json').write_text(json.dumps(exporter_settings(),indent=2)+'\n')
    (output/'ai/README.txt').write_text('No AI lines recorded. Empty AI directory is permitted by the basic guide (docs/AC_NOTES.md section 4).\nNo zero-byte fast_lane.ai / pit_lane.ai placeholders. AI driving is unsupported.\n')
    for source in ('CREDITS.md','README.md'):
        shutil.copy2(ROOT/source,output/source)
    shutil.copy2(ROOT/'docs/AC_NOTES.md',output/'docs/AC_NOTES.md')
    plan['map_transform'] = transform
    return plan


def build(blender):
    data = np.load(ROOT/'data/centerline.npz')
    plan = write_files(data)
    (ROOT/'data/acdata_info.json').write_text(json.dumps(plan,indent=2)+'\n')
    env = os.environ.copy()
    runtime = Path('/run/user')/str(os.getuid())
    if not env.get('XDG_RUNTIME_DIR') and runtime.is_dir():
        env['XDG_RUNTIME_DIR'] = str(runtime)
    subprocess.run([blender,'-b',str(ROOT/'blend/bejaia_saket.blend'),'--python-exit-code','1','-P',str(ROOT/'scripts/blender_acdata.py')],check=True,cwd=ROOT,env=env)
    print(f'ACDATA_OK empties={len(plan["empties"])} output={OUTPUT}')


if __name__ == '__main__':
    raise SystemExit('Use scripts/build.py acdata')
