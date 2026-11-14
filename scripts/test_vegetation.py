from pathlib import Path
import tempfile
import unittest

import numpy as np

from foliage import atlas_pixels,coverage_mips,encode_coverage_dds,coverage_report,prototype,tile_uv
from vegetation import Terrain
from check_kn5 import inspect_dds
from treefx import checksum,mesh_blob,read_mesh,vector_ac


class FoliageTests(unittest.TestCase):
    def test_twig_extraction_removes_opaque_uv_gutters(self):
        from PIL import Image,ImageDraw
        from foliage import extract_twig
        source=Image.new('RGBA',(1024,1024));draw=ImageDraw.Draw(source)
        draw.rectangle((0,0,25,474),fill=(0,0,0,255));draw.ellipse((60,70,220,440),fill=(55,95,48,255))
        result=np.asarray(extract_twig(source))
        self.assertEqual(result[100,0,3],0);self.assertEqual(result[200,140,3],255)
        self.assertEqual(np.asarray(extract_twig(Image.new('RGBA',(1024,1024))))[:,:,3].max(),0)
    def test_photographic_twig_input_and_soft_edges(self):
        from PIL import Image,ImageDraw
        twig=Image.new('RGBA',(1024,1024));ImageDraw.Draw(twig).ellipse((60,70,220,440),fill=(55,95,48,255))
        pixels=atlas_pixels(256,twig=twig)
        self.assertGreater(pixels[:128,:64,3].max(),200)
        self.assertTrue(((pixels[:,:,3]>0)&(pixels[:,:,3]<255)).any())
    def test_branched_treefx_models_keep_variants(self):
        for kind in range(4):
            for variant in range(3):
                small=prototype(kind,variant,quality=True)
                if kind<3:self.assertGreater(len(small['bark'].faces),200)
                self.assertIn('bark',small)
                for mesh in small.values():self.assertTrue(np.isfinite(mesh.vertices).all())
    def test_treefx_wire_round_trip_and_corruption(self):
        self.assertEqual(checksum(b''),0x02cc5d05)
        for kind in range(7):
            groups=prototype(kind,0);textures={'diffuse.dds':b'example diffuse','normal.dds':b'example normal'}
            blob,expected=mesh_blob([(0,1,m) for m in groups.values()],textures,5,10)
            self.assertEqual(read_mesh(blob,textures),expected)
            with self.assertRaises(ValueError):read_mesh(blob[:-1],textures)
            with self.assertRaises(ValueError):read_mesh(blob,dict(textures,**{'normal.dds':b'bad'}))
        np.testing.assert_equal(vector_ac([[1,2,3]]),[[1,3,-2]])
        with self.assertRaises(ValueError):read_mesh(b'',{})

    def test_all_species_variants_and_two_sided_lods(self):
        for kind in range(7):
            for variant in range(3):
                for lod in (0,1):
                    parts=prototype(kind,variant,lod)
                    leaves=parts['leaves'];p=np.asarray(leaves.vertices)
                    self.assertTrue(np.isfinite(p).all());self.assertTrue(len(leaves.faces)>0)
                    np.testing.assert_allclose(np.linalg.norm(leaves.normals,axis=1),1,atol=1e-7)
                    np.testing.assert_allclose(p[:4],p[4:8])
                    self.assertEqual(leaves.faces[2],(4,6,5))
                    self.assertTrue(np.all(np.asarray(leaves.uv)>=tile_uv(kind).min(0)))
                    self.assertTrue(np.all(np.asarray(leaves.uv)<=tile_uv(kind).max(0)))
                    if lod:self.assertEqual(len(leaves.faces),8)

    def test_atlas_determinism_and_coverage_mips(self):
        p=atlas_pixels(64)
        np.testing.assert_array_equal(p,atlas_pixels(64))
        self.assertGreater(np.mean(p[:,:,3]>128),.1)
        self.assertLess(np.mean(p[:,:,3]>128),.5)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'leaves.dds';encode_coverage_dds(p,path)
            info=inspect_dds(path.read_bytes());self.assertEqual((info['format'],info['mips']),('DXT5',7))
            coverage=np.asarray(coverage_report(path.read_bytes()))
            self.assertLess(abs(coverage[1]-coverage[0]).max(),.15)

    def test_invalid_atlas_and_prototype(self):
        with self.assertRaises(ValueError):atlas_pixels(0)
        with self.assertRaises(ValueError):prototype(7,0)
        with self.assertRaises(ValueError):list(coverage_mips(np.empty((0,0,4))))

    def test_actual_triangle_height_normal_and_empty_hits(self):
        triangles=np.array([[[0,0,0],[10,0,1],[0,10,2]],[[0,0,-1],[10,0,0],[0,10,1]]])
        terrain=Terrain(triangles)
        height,normal=terrain.sample(np.array([[2,3],[20,20]]))
        self.assertAlmostEqual(height[0],.8);self.assertTrue(np.isneginf(height[1]))
        self.assertGreater(normal[0,2],.9)
        height,normal=terrain.sample(np.empty((0,2)));self.assertEqual(len(height),0)
        with self.assertRaises(ValueError):Terrain(np.empty((0,3,3)))
