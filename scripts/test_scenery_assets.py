from types import SimpleNamespace
import unittest

import numpy as np

from scenery_assets import card_lod_groups, wire_groups
from treefx_wire import mesh_blob, read_mesh


class CardLodTests(unittest.TestCase):
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
