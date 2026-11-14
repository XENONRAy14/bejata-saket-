"""Generate reviewed CSP syntax with exact material names, never wildcards."""
import configparser
import json
from pathlib import Path
from string import Template

ROOT=Path(__file__).resolve().parents[1]
MATERIAL_KEYS={'GRASS_MATERIALS','OCCLUDING_MATERIALS','PUDDLES_MATERIALS',
               'SOAKING_MATERIALS','SMOOTH_MATERIALS','ROUGH_MATERIALS',
               'LINES_MATERIALS','LINES_FILTER_MATERIALS','MATERIALS'}


def config_materials(text):
    config=configparser.ConfigParser(interpolation=None)
    config.read_string(text)
    references=set()
    for section in config.sections():
        for key,value in config[section].items():
            if key.upper() in MATERIAL_KEYS or '_MATERIALS' in key.upper():
                names=[name.strip() for name in value.split(',')]
                if not names or any(not name for name in names):raise ValueError('Empty material selector')
                references.update(names)
    return config,references


def generate(root=ROOT):
    root=Path(root)
    info=json.loads((root/'data/materials_info.json').read_text())
    names=set(info['kn5_materials'])
    if not names:raise ValueError('Empty KN5 material inventory')
    roles={kind:sorted(name for name,spec in info['materials'].items() if spec['preview']['kind']==kind) for kind in ('road','terrain')}
    if not roles['road'] or not roles['terrain']:raise ValueError('Missing road/terrain recipes')
    def selected(values):
        values=sorted(set(values))
        if not values or not set(values)<=names:raise ValueError('Unknown/empty CSP material group')
        return ', '.join(values)
    groups=dict(grass=selected(roles['terrain']),road=selected(roles['road']),
        occluders=selected(roles['road']+['kerb','gravel','rock','sand','plaster','metal']),
        soaking=selected(roles['road']+['kerb','gravel','plaster']),smooth=selected(['metal']+[n for n in ('roadside_signs','marker_red') if n in names]),
        rough=selected(roles['terrain']+['gravel','rock','sand','bark']+[n for n in names if n in ('maquis','olive_foliage','pine_foliage') or n.startswith(('veg_canopy','veg_impostor'))]),
        water=selected(['water']))
    text=Template((root/'scripts/ext_config.ini.template').read_text()).substitute(groups)
    tree_info=root/'data/treefx_info.json'
    if tree_info.exists() and json.loads(tree_info.read_text()).get('mode')=='TreeFX':
        text+='\n; CSP wiki Tracks–Trees:29–69: external model instances.\n[TREES]\nLIST_0 = trees/trees.txt\n'
        text=text.replace('[GRASS_FX]\n','[GRASS_FX]\n; CSP wiki Tracks–Grass-FX:211–255: procedural dry tufts and low maquis.\nTEXTURE = trees/grass.dds\nTEXTURE_GRID = 4, 2\nTEXTURE_GROUP_0_CHANCE = 0.14\n')
        text+='\n; Same GrassFX source; columns start at 1, rows at 0.\n[GRASS_FX_TEXTURE_GROUP_0]\nPIECE_0 = 3, 1\nPIECE_0_SIZE_MULT = 0.8, 1.0\nPIECE_1 = 1, 1\nPIECE_1_CHANCE = 0.3\nPIECE_1_SIZE_MULT = 1.4, 1.7\n'
    _,references=config_materials(text)
    if not references<=names:raise ValueError('Config refers to missing material')
    output=root/'out/bejaia_saket/extension';output.mkdir(parents=True,exist_ok=True)
    (output/'ext_config.ini').write_text(text,encoding='utf-8')
    print(f'CSP_CONFIG_OK materials={len(references)} file={output/"ext_config.ini"}')
    return text
