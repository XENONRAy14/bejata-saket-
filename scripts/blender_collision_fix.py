"""Rebuild only full-route guardrails and invisible collision walls in the existing art scene."""
import configparser
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from blender_mesh import guardrail_meshes


def main():
    data = np.load(ROOT / 'data/centerline.npz')
    previous = [
        obj for obj in bpy.data.objects
        if obj.type == 'MESH' and obj.name.startswith(('1WALL_GUARD_', 'DETAIL_GUARD_'))
    ]
    if not previous:
        raise RuntimeError('Expected original guardrail meshes in the saved development scene')
    material = next((mat for obj in previous for mat in obj.data.materials), None)
    if material is None:
        raise RuntimeError('Original guardrail material is missing')

    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and obj.name.startswith((
            '1WALL_GUARD_', 'DETAIL_GUARD_', '1WALL_COLLIDER_GUARD_',
        )):
            bpy.data.objects.remove(obj, do_unlink=True)

    s = data['s']
    chunk_ends = np.unique(np.r_[
        0, np.searchsorted(s, np.arange(400, s[-1], 400)), len(s) - 1,
    ]).tolist()
    for chunk, (a, b) in enumerate(zip(chunk_ends, chunk_ends[1:])):
        for side, letter in enumerate(('L', 'R')):
            guardrail_meshes(data, a, b, side, chunk, letter, material)

    visuals = {
        obj.name for obj in bpy.data.objects
        if obj.type == 'MESH' and obj.name.startswith('DETAIL_GUARD_')
    }
    colliders = {
        obj.name for obj in bpy.data.objects
        if obj.type == 'MESH' and obj.name.startswith('1WALL_COLLIDER_GUARD_')
    }
    if not visuals or colliders != {
        name.replace('DETAIL_GUARD_', '1WALL_COLLIDER_GUARD_', 1)
        for name in visuals
    }:
        raise AssertionError('Visual and physical guardrail sections do not match')

    settings_path = ROOT / 'blend/settings.json'
    settings = json.loads(settings_path.read_text(encoding='utf-8'))
    nodes = settings.setdefault('nodes', {})
    nodes['DETAIL_GUARD_*'] = dict(
        lodIn=0, lodOut=10000, castShadows=True, visible=True, renderable=True,
    )
    nodes['1WALL_COLLIDER_GUARD_*'] = dict(
        lodIn=0, lodOut=10000, castShadows=False, visible=False, renderable=False,
    )
    settings_path.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )

    physical_keys = {
        match[1] for obj in bpy.data.objects
        if obj.type == 'MESH' and (match := re.match(r'^\d+([A-Z]+)', obj.name))
    }
    surfaces = configparser.ConfigParser()
    surfaces.read(ROOT / 'out/bejaia_saket/data/surfaces.ini', encoding='utf-8')
    assert physical_keys == {
        surfaces[section]['KEY'] for section in surfaces.sections()
    }, 'Exported physical mesh prefixes must match surfaces.ini'

    source = Path(os.environ.get(
        'AC_ADDON_SOURCE', str(Path.home() / 'tools/blender-assetto-corsa-tools'),
    ))
    addons = Path(bpy.utils.user_resource('SCRIPTS', path='addons', create=True))
    target = addons / 'blender_assetto_corsa_tools'
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
    bpy.utils.refresh_script_paths()
    bpy.ops.preferences.addon_enable(module=target.name)
    exporter = importlib.import_module(target.name + '.exporter')
    utilities = importlib.import_module(target.name + '.exporter.exporter_utils')
    for mat in bpy.data.materials:
        if mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    node.show_texture = True
            assert utilities.get_active_material_texture_slot(mat), (
                'Material needs an active texture slot: ' + mat.name
            )

    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'blend/bejaia_saket.blend'))
    output = ROOT / 'out/bejaia_saket/bejaia_saket.kn5'
    partial = ROOT / 'blend/bejaia_saket.kn5.partial'
    warnings = []
    started = time.perf_counter()
    try:
        with partial.open('wb') as stream:
            exporter.KN5FileWriter(
                stream, bpy.context, settings, warnings,
            ).write()
        with partial.open('rb') as stream:
            if stream.read(6) != b'sc6969':
                raise AssertionError('KN5 signature check failed')
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)

    report = {
        'file': str(output.relative_to(ROOT)),
        'bytes': output.stat().st_size,
        'seconds': time.perf_counter() - started,
        'blender': bpy.app.version_string,
        'warnings': warnings,
        'visual_guard_sections': len(visuals),
        'collision_guard_sections': len(colliders),
        'collision_renderable': False,
        'collision_height_m': .95 - (-.08),
        'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    (ROOT / 'data/kn5_export_info.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8',
    )
    print('GUARDRAIL_COLLISION_EXPORT_OK ' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
