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
        soaking=selected(roles['road']+['kerb','gravel','plaster']),smooth=selected(['metal']),
        rough=selected(roles['terrain']+['gravel','rock','sand','bark','maquis','olive_foliage','pine_foliage']),
        water=selected(['water']))
    text=Template((root/'scripts/ext_config.ini.template').read_text()).substitute(groups)
    _,references=config_materials(text)
    if not references<=names:raise ValueError('Config refers to missing material')
    output=root/'out/bejaia_saket/extension';output.mkdir(parents=True,exist_ok=True)
    (output/'ext_config.ini').write_text(text,encoding='utf-8')
    print(f'CSP_CONFIG_OK materials={len(references)} file={output/"ext_config.ini"}')
    return text
