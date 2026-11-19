from types import SimpleNamespace
import io
import struct
import unittest

import numpy as np
from PIL import Image

from scenery_assets import card_lod_groups, dds_blob, wire_groups
from pilot_common import resize_channels
from treefx_wire import mesh_blob, read_mesh


class CardLodTests(unittest.TestCase):
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
