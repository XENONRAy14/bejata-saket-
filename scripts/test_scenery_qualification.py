import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from qualify_scenery import legacy_foliage, parse_tree, qualify, station_selector
from scenery_kn5 import assign_material, clone_material, mesh, nodes, protected, read, string, subset, uint, validate_lock, write
from scenery_assets import ground_mask


def model():
    values=np.zeros((3,11),dtype='<f4');values[:,:3]=[[0,0,0],[1,0,0],[0,0,1]]
    node=mesh('1ROAD_test',values,[[0,1,2]],0)
    matrix=np.eye(4,dtype='<f4').tobytes()
    root=dict(kind=1,name='ROOT',matrix=matrix,raw=uint(1)+string('ROOT')+uint(1)+b'\x01'+matrix,children=[node])
    return dict(textures=[],materials=[dict(name='road',raw=string('road')+string('ksPerPixel')+b'\x00\x00'+uint(0)*3)],root=root)


class QualificationTests(unittest.TestCase):
    def test_binary_roundtrip_and_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            a=Path(directory)/'a.kn5';b=Path(directory)/'b.kn5';write(a,model());parsed=read(a);write(b,parsed)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertTrue(validate_lock(a,b)['all_checksums_identical'])
            node=parsed['root']['children'][0];node['raw']=node['raw'][:-1]+b'\x00';write(b,parsed)
            with self.assertRaisesRegex(ValueError,'1ROAD_test'):validate_lock(a,b)

    def test_empty_transform_parent_and_guard_are_locked(self):
        original=model();node=copy.deepcopy(original['root']);node.update(name='AC_START_0',children=[])
        node['raw']=uint(1)+string(node['name'])+uint(0)+b'\x01'+node['matrix']
        original['root']['children'].append(node)
        guard=copy.deepcopy(original['root']['children'][0]);guard['name']='DETAIL_GUARD_test';original['root']['children'].append(guard)
        for target in (node,guard):
            before=protected(original);target['raw']+=b'x';self.assertNotEqual(before,protected(original));target['raw']=target['raw'][:-1]
        before=protected(original);original['root']['matrix']=bytes(64)
        self.assertNotEqual(before,protected(original))

    def test_visual_changes_do_not_change_lock(self):
        original=model();before=protected(original);node=copy.deepcopy(original['root']['children'][0]);node['name']='LAND_test'
        original['root']['children'].append(node);self.assertEqual(before,protected(original))
        self.assertIsNone(subset(node,[False]))
        result=subset(node,[True],name='FLOOR',material=0,forest_uv=True)
        np.testing.assert_equal(np.frombuffer(result['vertices'],dtype='<f4').reshape(-1,11)[:,:3],
                                np.frombuffer(node['vertices'],dtype='<f4').reshape(-1,11)[:,:3])

    def test_grass_material_only_exception_keeps_geometry_flags_names_locked(self):
        original=model();original['materials']*=5;node=original['root']['children'][0];node['name']='1GRASS_test'
        before=protected(original);assign_material(node,4)
        self.assertEqual(before,protected(original))
        for offset in (0,-1,-40):
            raw=node['raw'];data=bytearray(raw);data[offset]^=1;node['raw']=bytes(data)
            self.assertNotEqual(before,protected(original));node['raw']=raw
        node['name']='1ROAD_test';before=protected(original);assign_material(node,0)
        self.assertNotEqual(before,protected(original))

    def test_material_clone_changes_only_name_and_selected_texture(self):
        material=dict(name='old',shader='ksPerPixel',properties={},textures={'txDiffuse':'old.dds'},
            raw=string('old')+string('ksPerPixel')+bytes(6)+uint(0)+uint(1)+string('txDiffuse')+uint(3)+string('old.dds'))
        cloned=clone_material(material,'new',dict(txDiffuse='new.dds'))
        self.assertIn(uint(3)+string('new.dds'),cloned['raw']);self.assertEqual(cloned['textures']['txDiffuse'],'new.dds')
        with self.assertRaises(ValueError):clone_material(material,'bad',dict(unknown='bad'))

    def test_ground_mask_does_not_paint_outside_sector_or_uv_aliases(self):
        values=np.zeros((4,11),'<f4');values[:,:3]=[[0,0,0],[1,0,0],[1,0,1],[0,0,1]];values[:,6:8]=values[:,[0,2]]
        node=mesh('1GRASS_test',values,[[0,1,2],[0,2,3]],0)
        select=lambda p:(p[:,0]>.5)&(p[:,0]<2)
        mask=ground_mask(node,select,16);self.assertEqual(int(mask.sum()),128);self.assertFalse(mask[:,:8].any())
        duplicate=values.copy();duplicate[:,0]+=10
        alias=mesh('1GRASS_test',np.concatenate([values,duplicate]),[[0,1,2],[0,2,3],[4,5,6],[4,6,7]],0)
        self.assertFalse(ground_mask(alias,select,16).any())
        self.assertFalse(ground_mask(node,lambda p:np.zeros(len(p),bool),16).any())

    def test_truncation_and_invalid_counts_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.kn5';path.write_bytes(b'bad')
            with self.assertRaises(ValueError):read(path)
        with self.assertRaises(ValueError):mesh('bad',np.zeros((3,11)),[[0,1,9]],0)

    def test_sector_tree_selection_and_nonfoliage(self):
        data=dict(xy=np.array([[0,0],[100,0],[200,0]]),s3=np.array([0,100,200]),width=np.full(3,7))
        mask=station_selector(data,50,150)(np.array([[100,3,0],[0,3,0],[100,3,-200]]))
        self.assertEqual(mask.tolist(),[True,False,False])
        tree=parse_tree('tree: pine.bin; pos=1, 3, -2; angle=-90; size=1; width=1; color=1, 1, 1')
        np.testing.assert_equal(tree['position'],[1,2,3])
        self.assertTrue(legacy_foliage('DECOR_002_pine_foliage'))
        for name in ('DECOR_002_bark','DECOR_002_plaster','DETAIL_GUARD_000','1WALL_test'):
            self.assertFalse(legacy_foliage(name))

    def test_unqualified_sector_and_main_output_are_rejected(self):
        with self.assertRaises(ValueError):qualify('sea_view')
        from qualify_scenery import ROOT
        with self.assertRaises(ValueError):qualify(output=ROOT/'out/bejaia_saket')

    def test_cached_build_without_visual_ground_is_explicitly_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'out/bejaia_saket';pilot=root/'out/bejaia_saket_pilot300'
            (source/'extension/trees').mkdir(parents=True);pilot.mkdir(parents=True)
            (source/'ui').mkdir();(source/'ui/ui_track.json').write_text('{}')
            (root/'data/pilot300').mkdir(parents=True)
            baseline=source/'bejaia_saket.kn5';write(baseline,model());original=baseline.read_bytes()
            prototype=model();prototype['materials'][0]['raw']=string('forest_edge')+string('ksPerPixelAT')+b'\x00\x00'+uint(0)*3
            write(pilot/'bejaia_saket_pilot300.kn5',prototype)
            for name in ('CREDITS.md','LICENSES.json'):(pilot/name).write_text('{}')
            (pilot/'CREDITS.md').write_bytes(b'credit\r\n')
            (source/'extension/trees/trees.txt').write_text('')
            (source/'extension/ext_config.ini').write_text('; preserve this exactly\n')
            (root/'data/pilot300/treefx_models.json').write_text('{}')
            np.savez(root/'data/centerline.npz',xy=[[0,0],[100,0]],s3=[0,100],width=[7,7])
            zones=dict(report_sectors=[dict(name='summit',start_m=0,end_m=100)],main={})
            with patch('qualify_scenery.ROOT',root),patch('qualify_scenery.BASE_SHA',hashlib.sha256(original).hexdigest()),patch('qualify_scenery.load_zones',return_value=zones),patch('qualify_scenery.plan_sector',return_value=dict(trees=[],edges=[],report={})):
                output=qualify()
                report=json.loads((output/'scenery_report.json').read_text())
                self.assertFalse(report['qualification_complete']);self.assertFalse(report['forest_floor_applied'])
                self.assertTrue(report['physics_lock']['all_checksums_identical'])
                self.assertIn('FILE=bejaia_saket.kn5',(output/'models.ini').read_text())
                self.assertIn('qualification',json.loads((output/'ui/ui_track.json').read_text())['name'])
                self.assertEqual((output/'PILOT_ASSET_CREDITS.md').read_bytes(),b'credit\n')
                self.assertEqual((output/'extension/ext_config.ini').read_bytes(),(source/'extension/ext_config.ini').read_bytes())
                self.assertEqual(baseline.read_bytes(),original)
                with self.assertRaises(FileExistsError):qualify()


if __name__=='__main__':unittest.main()
