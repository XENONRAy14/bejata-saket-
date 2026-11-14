import copy
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from assets import acquire
from check_kn5 import inspect_dds, mask_mip_error
from materials import channel_mips, packed_maps, road_atlas, grade_diffuse, terrain_mask, ROAD_PERIOD


class AssetTests(unittest.TestCase):
    def test_download_cache_and_checksum_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            payload=b'CC0 fixture'
            entry=dict(path='data/asset_cache/test/map.png',url='https://example.invalid/map.png',sha256=hashlib.sha256(payload).hexdigest())
            manifest=dict(version=1,assets=[dict(id='fixture',license='CC0-1.0',files={'diffuse':entry})])
            def download(url,target):
                target.parent.mkdir(parents=True);partial=target.with_suffix('.partial');partial.write_bytes(payload);return partial
            with patch('assets.download',side_effect=download) as fetch:
                acquire(folder,manifest);acquire(folder,manifest);fetch.assert_called_once()
                (Path(folder)/entry['path']).write_bytes(b'corrupt')
                with self.assertRaisesRegex(ValueError,'Corrupt cached'):acquire(folder,manifest)
            bad=copy.deepcopy(manifest);bad['assets'][0]['license']='paid'
            with self.assertRaisesRegex(ValueError,'CC0'):acquire(folder,bad)
            bad=copy.deepcopy(manifest);bad['assets'][0]['files']['diffuse']['path']='../secret'
            with self.assertRaisesRegex(ValueError,'outside'):acquire(folder,bad)

    def test_empty_manifest(self):
        with self.assertRaises(ValueError):acquire(manifest={'version':1,'assets':[]})


class TextureTests(unittest.TestCase):
    def test_neutral_grades_and_green_terrain(self):
        pixels=np.random.default_rng(5).uniform(.1,.8,(64,64,3)).astype('float32')
        for role,target in [('asphalt',(95,95,95)),('repair',(70,70,72)),('gravel',(139,137,123))]:
            mean=grade_diffuse(role,pixels).mean((0,1))*255
            np.testing.assert_allclose(mean,target,atol=1)
        grass=grade_diffuse('grass',pixels).mean((0,1))
        self.assertGreater(grass[1],grass[0]*1.3)
        for coverage in (.25,.35):
            mask=terrain_mask(128,coverage)
            self.assertAlmostEqual(float((mask[:,:,1]>.5).mean()),coverage,places=3)
            np.testing.assert_allclose(mask.sum(2),1)
        for pixels in (np.empty((0,0,3)),np.zeros((3,3))):
            with self.assertRaises(ValueError):grade_diffuse('asphalt',pixels)
        with self.assertRaises(ValueError):terrain_mask(0,.3)

    def test_repairs_are_small_and_occasional(self):
        self.assertTrue(100<=ROAD_PERIOD<=200)
        _,mask=road_atlas(Image.new('RGB',(64,64),(95,95,95)),size=512)
        self.assertGreater(mask[:,:,1].max(),.5)
        self.assertLess(float((mask[:,:,1]>.1).mean()),.003)

    def test_mips_keep_zero_alpha_data_channels(self):
        pixels=np.zeros((8,8,4),dtype='uint8');pixels[:,:,0]=153;pixels[:,:,1]=102
        levels=list(channel_mips(pixels))
        self.assertEqual([v.shape[0] for v in levels],[8,4,2,1])
        for level in levels:
            np.testing.assert_array_equal(level.sum(2),255)
            self.assertTrue((level[:,:,3]==0).all())
        with self.assertRaises(ValueError):list(channel_mips(np.empty((0,0,4))))

    def test_atlas_worn_markings_weights_and_variants(self):
        source=Image.new('RGB',(64,64),(80,82,85))
        color,mask=road_atlas(source,size=256)
        self.assertEqual(color.shape,(256,256,3))
        np.testing.assert_allclose(mask.sum(2),1,atol=1e-6)
        self.assertGreater(mask[:,:,3].max(),.5)
        self.assertGreater(np.ptp(mask[:,:,3]),.5)
        self.assertTrue(np.isfinite(color).all())
        self.assertFalse(np.array_equal(mask,road_atlas(source,1,size=256)[1]))
        np.testing.assert_array_equal(color,road_atlas(source,size=256)[0])
        with self.assertRaises(ValueError):road_atlas(source,size=0)

    def test_roughness_packing(self):
        packed=packed_maps(np.array([[0,1]],dtype=float))
        self.assertEqual(packed.shape,(1,2,3))
        self.assertTrue(np.all(packed[:,0]>packed[:,1]))
        self.assertTrue(np.isfinite(packed_maps(np.array([[-1,2]]))).all())
        with self.assertRaises(ValueError):packed_maps(np.array([]))

    def test_dds_complete_chain_and_rejections(self):
        blob=bytearray(128+48);blob[:4]=b'DDS '
        for offset,value in ((4,124),(8,0x21007),(12,4),(16,4),(28,3),(76,32),(80,4),(108,0x401008)):
            struct.pack_into('<I',blob,offset,value)
        blob[84:88]=b'DXT5'
        self.assertEqual(inspect_dds(blob)['gpu_bytes'],48)
        for bad in (b'',blob[:-1]):
            with self.assertRaises(ValueError):inspect_dds(bad)
        blob[84:88]=b'DX10'
        with self.assertRaises(ValueError):inspect_dds(blob)
        blob[84:88]=b'DXT5';struct.pack_into('<I',blob,28,1)
        with self.assertRaisesRegex(ValueError,'mip'):inspect_dds(blob)

    def test_mask_mip_decoder_detects_lost_rgb_weights(self):
        header=bytearray(128);header[:4]=b'DDS '
        for offset,value in ((4,124),(8,0x21007),(12,4),(16,4),(28,3),(76,32),(80,4),(108,0x401008)):
            struct.pack_into('<I',header,offset,value)
        header[84:88]=b'DXT5'
        red=struct.pack('<BB6sHHI',0,0,b'\0'*6,0xf800,0xf800,0)
        self.assertEqual(mask_mip_error(header+red*3),0)
        self.assertEqual(mask_mip_error(header+red*2+b'\0'*16),1)
        with self.assertRaises(ValueError):mask_mip_error(b'')


if __name__=='__main__':unittest.main()
