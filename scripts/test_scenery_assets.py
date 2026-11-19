from types import SimpleNamespace
import io
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
import configparser

import numpy as np
from PIL import Image

from scenery_assets import canopy_atlas, card_lod_groups, dds_blob, foliage_tint, litter_texture, repair_pine_archive, shrub_cluster, wire_groups
from scenery_preview_common import tree_lod
from pilot_common import resize_channels
from treefx_wire import mesh_blob, read_mesh


class CardLodTests(unittest.TestCase):
    def test_qualification_pines_keep_volume_until_150m(self):
        root=Path(__file__).resolve().parents[1]/'out/bejaia_saket_pilot300/extension/trees'
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'pine.bin'
            for name in ('ph_pine_01.bin','ph_pine_mid_01.bin'):
                repair_pine_archive(root/name,target,impostor_distance=150)
                with zipfile.ZipFile(target) as archive:
                    config=configparser.ConfigParser();config.read_string(archive.read('tree.ini').decode())
                    for distance in (0,27.99,28,149.99,150):
                        lod=tree_lod(config,distance);_,groups=wire_groups(archive.read(config[f'LOD_{lod}']['MODEL']))
                        triangles=sum(len(p.faces) for _,_,p in groups)
                        if distance<150:self.assertEqual(triangles,20000)
                        else:self.assertEqual(triangles,16)
            for distance in (149,float('nan')):
                with self.assertRaises(ValueError):repair_pine_archive(root/'ph_pine_01.bin',target,impostor_distance=distance)

    def test_three_crown_cluster_preserves_source_triangles_and_group_limits(self):
        source=Path(__file__).resolve().parents[1]/'out/bejaia_saket_pilot300/extension/trees/ph_shrub_01.bin'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'cluster.bin';spec=shrub_cluster(source,path)
            self.assertEqual(len(spec['clearance_spheres']),3)
            with zipfile.ZipFile(path) as archive,zipfile.ZipFile(source) as original:
                for lod in range(3):
                    _,groups=wire_groups(archive.read(f'LOD{lod}.mesh'));_,old=wire_groups(original.read(f'LOD{lod}.mesh'))
                    self.assertEqual(sum(len(p.faces) for _,_,p in groups),3*sum(len(p.faces) for _,_,p in old))
                    self.assertTrue(all(len(p.vertices)<65536 for _,_,p in groups))
            self.assertLessEqual(spec['lods'][1]['triangles'],9003)

    def test_tinted_foliage_preserves_cutout_and_litter_is_dark_and_varied(self):
        source=Image.new('RGBA',(128,128),(160,140,100,37))
        tinted=np.asarray(foliage_tint(source));self.assertTrue((tinted[:,:,3]==37).all())
        self.assertTrue((tinted[:,:,:3]<np.asarray(source)[:,:,:3]).all())
        litter=np.asarray(litter_texture(source));self.assertLess(litter[:,:,:3].mean(),100);self.assertGreater(litter[:,:,1].std(),2)
        np.testing.assert_array_equal(litter,litter_texture(source))
        with self.assertRaises(ValueError):foliage_tint(source,[1,float('nan'),1])
        with self.assertRaises(ValueError):canopy_atlas([])
        with self.assertRaises(ValueError):canopy_atlas([Image.new('RGBA',(16,16))])
        atlas=canopy_atlas([Image.new('RGBA',(64,64),(100,130,70,255))])
        self.assertEqual(atlas.size,(1024,1024));self.assertTrue(np.asarray(atlas)[:,:,3].any())

    def test_weight_resize_retains_rgb_when_fourth_weight_is_zero(self):
        image=Image.new('RGBA',(16,16),(20,60,175,0))
        resized=resize_channels(image,(7,7),Image.Resampling.BICUBIC)
        np.testing.assert_array_equal(np.asarray(resized),np.tile([20,60,175,0],(7,7,1)))

    def test_weight_dds_keeps_litter_in_every_mip_with_zero_fourth_weight(self):
        blob=dds_blob(Image.new('RGBA',(16,16),(0,0,255,0)),data=True)
        count=struct.unpack_from('<I',blob,28)[0];size=16;offset=128
        for _ in range(count):
            length=max(1,(size+3)//4)**2*16;header=bytearray(blob[:128])
            struct.pack_into('<2I',header,12,size,size);struct.pack_into('<I',header,28,1)
            mip=np.asarray(Image.open(io.BytesIO(header+blob[offset:offset+length])).convert('RGBA'))
            self.assertTrue((mip[:,:,2]>=248).all());self.assertFalse(mip[:,:,3].any())
            offset+=length;size=max(1,size//2)
        self.assertEqual(offset,len(blob))
        with self.assertRaises(ValueError):dds_blob(Image.new('RGBA',(4,4)),data=True,coverage=True)

    def test_medium_lod_only_removes_whole_atlas_views(self):
        part=SimpleNamespace(vertices=[[0,0,0],[1,0,0],[1,0,1],[0,0,0],[1,0,0],[1,0,1]],
            normals=[[0,-1,0]]*6,uv=[[0,0],[.4,0],[.4,.4],[.6,0],[1,0],[1,.4]],faces=[[0,1,2],[3,4,5]])
        groups=card_lod_groups([(0,0,part)],['pine_card_diff.dds'])
        self.assertEqual(groups[0][2].faces,[[0,1,2]])
        self.assertEqual(groups[0][2].vertices,part.vertices[:3]);self.assertEqual(groups[0][2].uv,part.uv[:3])
        self.assertEqual(len(card_lod_groups([(0,0,part)],['bark.dds'])[0][2].faces),2)
        textures={'pine_card_diff.dds':b'texture'}
        blob,metrics=mesh_blob(groups,textures,1,1);self.assertEqual(read_mesh(blob,textures),metrics)
        names,decoded=wire_groups(blob);np.testing.assert_allclose(decoded[0][2].uv,groups[0][2].uv,atol=1e-7)

    def test_empty_card_groups_are_skipped(self):
        part=SimpleNamespace(vertices=[],normals=[],uv=[],faces=[])
        self.assertEqual(card_lod_groups([],[]),[])
        self.assertEqual(card_lod_groups([(0,0,part)],['bark.dds']),[])


if __name__=='__main__':unittest.main()
