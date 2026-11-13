from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import decor
from decor import Terrain, coastal_meshes, coast_chain, scatter


def ribbons():
    s = np.arange(0,1001,10,dtype=float)
    xy = np.column_stack([s,np.zeros(len(s))])
    offsets = np.tile([3.5,3.8,5.3,13.3,21.3,31.3,45.3],(2,len(s),1))
    sides = np.zeros((2,len(s),7,3))
    for side,sign in enumerate((1,-1)):
        sides[side,:,:,0] = s[:,None]
        sides[side,:,:,1] = offsets[side]*sign
        sides[side,:,:,2] = 10+s[:,None]*.01+offsets[side]*.02
    return dict(s=s,xy=xy,z=10+s*.01,sides=sides,offsets=offsets,width=np.full(len(s),7.),normal=np.tile([0.,1.],(len(s),1)),cut=np.zeros((2,len(s)),bool))


class DecorTests(unittest.TestCase):
    def test_exact_terrain_triangle_height_and_clearance(self):
        terrain = Terrain(ribbons())
        point,slope,_ = terrain.sample(123,0,17)
        self.assertAlmostEqual(point[2],10+point[0]*.01+point[1]*.02)
        self.assertAlmostEqual(terrain.height(point[:2]),point[2])
        self.assertAlmostEqual(terrain.clearance(point[:2]),point[1]-3.5)
        self.assertLess(slope,.03)
        self.assertIsNone(terrain.sample(123,0,100))
        self.assertIsNone(terrain.height([500,100]))

    def test_seeded_scatter_and_exclusions(self):
        data = ribbons()
        first = scatter(data,vegetation_count=12)
        second = scatter(data,vegetation_count=12)
        np.testing.assert_array_equal(first,second)
        self.assertGreater(len(first),12)
        terrain = Terrain(data)
        for entry in first:
            self.assertAlmostEqual(terrain.height(entry[2:4]),entry[4])
            required = 8 if entry[0]==5 else (4 if entry[0]<4 else 2)
            self.assertGreaterEqual(entry[12],required)
        data['cut'][:] = True
        self.assertEqual(len(scatter(data,vegetation_count=2)),0)
        with self.assertRaises(ValueError):
            scatter(dict(s=[],sides=np.zeros((2,0,7,3))))

    def test_coastal_geometry_and_sea_height_guard(self):
        data = ribbons()
        coast = np.column_stack([np.arange(0,1001,10),np.full(101,150.)])
        sea,beach,faces,minimum = coastal_meshes(data,coast)
        self.assertEqual(sea[:,2].max(),0)
        self.assertGreater(minimum,0)
        self.assertGreater(len(faces),0)
        self.assertTrue(np.all(beach[:,2]>.1))
        data['sides'][0,0,0,2] = -.1
        with self.assertRaisesRegex(ValueError,'clipping required'):
            coastal_meshes(data,coast)
        with self.assertRaises(ValueError):
            coast_chain(dict(ways=[]),[0,0],data)

    def test_textures_are_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'textures').mkdir()
            with patch.object(decor,'ROOT',root):
                decor.textures()
                first = {p.name:p.read_bytes() for p in (root/'textures').iterdir()}
                decor.textures()
                self.assertEqual(first,{p.name:p.read_bytes() for p in (root/'textures').iterdir()})


if __name__ == '__main__':
    unittest.main()
