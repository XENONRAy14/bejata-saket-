import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
from PIL import Image

from package import package
from validate import EMPTIES, REQUIRED, UI_KEYS, validate


def scene():
    matrix=np.eye(4);matrix[3,1]=1.5
    nodes=[dict(kind=1,name=name,matrix=matrix.ravel().tolist()) for name in sorted(EMPTIES)]
    nodes.append(dict(kind=2,name='DECOR_SEA',vertices=3,triangles=1,material=1,
        positions=np.array([[0,0,0],[0,0,1500],[1500,0,0]]),indices=np.array([[0,1,2]]),
        bounds=(np.zeros(3),np.array([1500,0,1500])),uv_stats=dict(finite=True,extent=[375,375])))
    nodes.append(dict(kind=2,name='1ROAD_000',vertices=3,triangles=1,material=0,
                      positions=np.array([[-1,0,-3.5],[-1,0,3.5],[1,0,-3.5]]),
                      indices=np.array([[0,1,2]]),bounds=(np.zeros(3),np.array([13000,338,8300]))))
    material=dict(name='asphalt',shader='ksPerPixel',textures={'txDiffuse':'road.png'},texture_slots={'txDiffuse':0},properties={'ksDiffuse':.4},blend=0,alpha_tested=False,depth=0)
    return dict(bytes=100,textures=['road.png'],texture_formats={'road.png':'PNG'},texture_info={},materials=[material,dict(material,name='water'),dict(material,name='grass')],nodes=nodes)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)/'bejaia_saket'
        for filename in (*REQUIRED,'bejaia_saket.kn5'):
            path=self.folder/filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
        self.ui=dict.fromkeys(UI_KEYS,'fixture');self.ui.update(pitboxes='4',geotags=[36.75,5.08])
        (self.folder/'ui/ui_track.json').write_text(json.dumps(self.ui),encoding='utf-8')
        (self.folder/'data/surfaces.ini').write_text('[SURFACE_0]\nKEY=ROAD\n')
        (self.folder/'data/map.ini').write_text('[PARAMETERS]\nWIDTH=2\nHEIGHT=3\nX_OFFSET=0\nZ_OFFSET=0\nSCALE_FACTOR=1\nMARGIN=0\nDRAWING_SIZE=10\nMAX_SIZE=3\n')
        Image.new('RGBA',(2,3)).save(self.folder/'map.png')
        (self.folder/'extension/ext_config.ini').write_text('[GRASS_FX]\nGRASS_MATERIALS=grass\n[RAIN_FX]\nPUDDLES_MATERIALS=asphalt\n[INCLUDE: common/materials_track.ini]\n[Material_Water]\nMaterials=water\nType=SEA\n')

    def run_check(self,parsed):
        output=io.StringIO()
        with patch('validate.inspect_kn5',return_value=parsed),contextlib.redirect_stdout(output):
            result=validate(self.folder)
        return result,output.getvalue()

    def test_valid_package(self):
        passed,output=self.run_check(scene())
        self.assertTrue(passed,output)
        self.assertIn('VALIDATION_PASS checks=15 passed=15',output)

    def test_geometry_and_binary_semantic_failures(self):
        mutations={
            'required_empties':lambda p:p['nodes'][0].update(name='ac_bad'),
            'empty_road_clearance':lambda p:p['nodes'][0]['matrix'].__setitem__(13,4),
            'vertex_limits':lambda p:p['nodes'][-1].update(vertices=65537),
            'units_scale_and_road_width':lambda p:p['nodes'][-1].update(bounds=(np.zeros(3),np.ones(3))),
            'mesh_names_and_surfaces':lambda p:p['nodes'][-1].update(name='1MISSING_000'),
            'textures':lambda p:p['texture_formats'].update({'road.png':'UNKNOWN'}),
            'materials_and_shaders':lambda p:p['materials'][0].update(shader='invented'),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                parsed=copy.deepcopy(scene());mutate(parsed)
                passed,output=self.run_check(parsed)
                self.assertFalse(passed);self.assertIn('FAIL '+name,output)

    def test_ui_map_and_extra_file_failures(self):
        for payload in (b'\xff',b'{',b'{}',json.dumps(dict(self.ui,pitboxes='3')).encode()):
            (self.folder/'ui/ui_track.json').write_bytes(payload)
            passed,output=self.run_check(scene())
            self.assertFalse(passed);self.assertIn('FAIL ui_metadata',output)
        Image.new('RGBA',(3,2)).save(self.folder/'map.png')
        (self.folder/'settings.json').write_text('{}')
        passed,output=self.run_check(scene())
        self.assertFalse(passed);self.assertIn('FAIL map_dimensions',output);self.assertIn('FAIL required_files',output)

    def test_csp_unknown_material_and_sea_normals(self):
        path=self.folder/'extension/ext_config.ini'
        path.write_text(path.read_text().replace('PUDDLES_MATERIALS=asphalt','PUDDLES_MATERIALS=missing'))
        passed,output=self.run_check(scene())
        self.assertFalse(passed);self.assertIn('FAIL csp_config',output)
        parsed=scene();parsed['nodes'][-2]['indices']=np.array([[0,2,1]])
        passed,output=self.run_check(parsed)
        self.assertFalse(passed);self.assertIn('FAIL sea_surface',output)

    def test_empty_folder_and_corrupt_kn5(self):
        for folder in (Path(self.temp.name)/'Invalid-Name',self.folder):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate(folder))
            self.assertIn('FAIL kn5_readback',output.getvalue())

    def test_zip_root_contents_and_reproducibility(self):
        with contextlib.redirect_stdout(io.StringIO()):
            archive=package(self.folder);first=archive.read_bytes()
            package(self.folder)
        self.assertEqual(first,archive.read_bytes())
        with zipfile.ZipFile(archive) as zipped:
            self.assertIsNone(zipped.testzip())
            self.assertTrue(all(n.startswith('bejaia_saket/') for n in zipped.namelist()))
            self.assertEqual(zipped.read('bejaia_saket/README.md'),b'fixture')


if __name__=='__main__':
    unittest.main()
