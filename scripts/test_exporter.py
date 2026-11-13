"""Run with Blender -b --python-exit-code 1 -P scripts/test_exporter.py."""
import json
import os
from pathlib import Path
import shutil
import bpy

root = Path(__file__).resolve().parents[1]
source = Path(os.environ.get('AC_ADDON_SOURCE', str(Path.home() / 'tools/blender-assetto-corsa-tools')))
addons = Path(bpy.utils.user_resource('SCRIPTS', path='addons', create=True))
target = addons / 'blender_assetto_corsa_tools'
shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git'))
bpy.utils.refresh_script_paths()
bpy.ops.preferences.addon_enable(module=target.name)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
bpy.ops.mesh.primitive_plane_add(size=10)
bpy.context.object.name = '1ROAD'
material = bpy.data.materials.new('Road')
material.use_nodes = True
image = bpy.data.images.new('road.png', width=2, height=2)
image.filepath_raw = str(root / 'out/road.png')
image.file_format = 'PNG'
image.save()
image = bpy.data.images.load(image.filepath_raw, check_existing=False)
texture = material.node_tree.nodes.new('ShaderNodeTexImage')
texture.image = image
texture.show_texture = True
bpy.context.object.data.materials.append(material)
bpy.ops.object.empty_add()
bpy.context.object.name = 'AC_START_0'
output = root / 'out/exporter_smoke'
output.mkdir(parents=True, exist_ok=True)
(output / 'settings.json').write_text(json.dumps({}))
bpy.ops.wm.save_as_mainfile(filepath=str(root / 'blend/exporter_smoke.blend'))
result = bpy.ops.exporter.kn5(filepath=str(output / 'smoke.kn5'))
path = output / 'smoke.kn5'
assert result == {'FINISHED'} and path.is_file() and path.stat().st_size > 0
assert path.read_bytes().startswith(b'sc6969')
print(f'KN5_SMOKE_OK Blender={bpy.app.version_string} bytes={path.stat().st_size} file={path}')
