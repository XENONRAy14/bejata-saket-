import configparser
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np
from PIL import Image

from acdata import exporter_settings, map_pixels, map_transform, plan_empties, road_point, surfaces_text, write_files
from check_kn5 import inspect_kn5


def straight_data():
    s = np.arange(0,1001,2,dtype=float)
    return dict(s=s,xy=np.column_stack([s,np.zeros(len(s))]),tangent=np.tile([1.,0],(len(s),1)),z=s*.01,width=np.full(len(s),7.))


class ACDataTests(unittest.TestCase):
    def test_kn5_reader_normal_empty_and_truncated(self):
        def string(value):
            value = value.encode()
            return struct.pack('<I',len(value))+value
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'test.kn5'
            node = struct.pack('<I',1)+string('BlenderFile')+struct.pack('<I?',0,True)+struct.pack('<16f',*np.eye(4).ravel())
            path.write_bytes(b'sc6969'+struct.pack('<3I',5,0,0)+node)
            parsed = inspect_kn5(path)
            self.assertEqual(parsed['textures'],[])
            self.assertEqual(parsed['nodes'][0]['name'],'BlenderFile')
            for content in (b'',b'sc6969'+struct.pack('<I',5),b'wrong header'):
                path.write_bytes(content)
                with self.assertRaises(ValueError):
                    inspect_kn5(path)

    def test_spawns_and_gates(self):
        data = straight_data()
        plan = plan_empties(data)
        self.assertEqual(len(plan['empties']),15)
        self.assertEqual(len({e['name'] for e in plan['empties']}),15)
        self.assertEqual(plan['finish_runoff_m'],50)
        self.assertEqual(plan['staging_heading_range_deg'],0)
        for e in plan['empties']:
            self.assertEqual(e['name'],e['name'].upper())
            self.assertAlmostEqual(e['position_m'][2]-e['road_height_m'],1.5)
            self.assertEqual(e['yaw_deg'],90)
            self.assertGreaterEqual(e['chunk_seam_distance_m'],2)
            if e['name'].startswith(('AC_PIT_','AC_START_','AC_HOTLAP_START_')):
                self.assertLess(e['lateral_m'],0)
            elif e['name'].endswith('_L'):
                self.assertEqual(e['position_m'][1],3.5)
            else:
                self.assertEqual(e['position_m'][1],-3.5)
        gates = [e['chainage_m'] for e in plan['empties'] if e['name'].startswith('AC_TIME_')]
        self.assertTrue(all(plan['start_gate_m'] < s < plan['finish_gate_m'] for s in gates))

    def test_invalid_and_unavailable_layout(self):
        data = straight_data()
        data['s'] = np.array([])
        with self.assertRaises(ValueError):
            plan_empties(data)
        data = straight_data()
        data['tangent'] = np.column_stack([np.cos(data['s']/20),np.sin(data['s']/20)])
        with self.assertRaises(ValueError):
            plan_empties(data)
        data = straight_data()
        with self.assertRaises(ValueError):
            road_point(data,-1)
        data['z'][10] = np.nan
        with self.assertRaises(ValueError):
            plan_empties(data)

    def test_map_world_coordinate_transform(self):
        xy = np.array([[-100.,200.],[400.,800.],[100.,-200.]])
        frame = map_transform(xy)
        pixels = map_pixels(xy,frame)
        self.assertEqual(max(frame['WIDTH'],frame['HEIGHT']),1600)
        self.assertGreaterEqual(pixels.min(),19.999)
        self.assertLessEqual(pixels[:,0].max(),frame['WIDTH']-19.999)
        self.assertLessEqual(pixels[:,1].max(),frame['HEIGHT']-19.999)
        reconstructed = pixels*frame['SCALE_FACTOR']-[frame['X_OFFSET'],frame['Z_OFFSET']]
        np.testing.assert_allclose(reconstructed,xy*[1,-1])
        self.assertLess(pixels[1,1],pixels[0,1])
        self.assertEqual(map_pixels(np.empty((0,2)),frame).shape,(0,2))
        for points in ([],[[1,1],[1,1]],[[0,0],[float('nan'),1]]):
            with self.assertRaises(ValueError):
                map_transform(points)

    def test_surface_and_material_configuration(self):
        config = configparser.ConfigParser()
        config.read_string(surfaces_text())
        self.assertEqual({config[s]['KEY'] for s in config.sections()},{'ROAD','KERB','GRASS','GRAVEL','WALL'})
        self.assertEqual(config['SURFACE_0'].getfloat('FRICTION'),1)
        self.assertEqual(config['SURFACE_1'].getfloat('FRICTION'),.92)
        settings = exporter_settings()
        self.assertEqual(len(settings['materials']),6)
        for name,value in settings['materials'].items():
            self.assertEqual(value['shaderName'],'ksPerPixel')
            self.assertEqual(value['textures']['txDiffuse']['textureName'],name+'.png')
        self.assertTrue(settings['nodes']['1*']['castShadows'])

    def test_write_package(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'bejaia_saket'
            plan = write_files(straight_data(),output)
            ui = json.loads((output/'ui/ui_track.json').read_text(encoding='utf-8'))
            self.assertEqual(ui['name'],'Béjaïa – Saket (RN24)')
            self.assertEqual(ui['pitboxes'],'4')
            self.assertEqual(ui['length'],'1000m')
            for name in ('preview','outline'):
                with Image.open(output/f'ui/{name}.png') as image:
                    self.assertEqual(image.size,(355,200))
                    if name=='outline':
                        self.assertEqual(image.mode,'RGBA')
                        self.assertEqual(image.getextrema()[-1],(0,255))
            with Image.open(output/'map.png') as image:
                self.assertEqual(image.size,(plan['map_transform']['WIDTH'],plan['map_transform']['HEIGHT']))
            self.assertEqual(list((output/'ai').iterdir()),[output/'ai/README.txt'])
            self.assertFalse((output/'data/cameras.ini').exists())
            self.assertTrue((output/'docs/AC_NOTES.md').is_file())


if __name__ == '__main__':
    unittest.main()
