import io
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pilot_common as common
from pilot_common import np,Image,dds,source_data,select_sector,interpolate,frame,ground
from check_kn5 import inspect_dds
from treefx_wire import checksum,vector_ac,mesh_blob,read_mesh
from pilot_scenery import edge_layout, vista_open


class PilotGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        cls.full=source_data()
        with patch.object(common,'DATA',Path(cls.temporary.name)):
            cls.data,cls.meta=select_sector(cls.full)
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()
    def test_300_meters(self):
        points=np.column_stack([self.data['xy'],self.data['z']]);self.assertAlmostEqual(np.linalg.norm(np.diff(points,axis=0),axis=1).sum(),300,places=7)
    def test_contains_actual_summit(self):
        self.assertGreater(self.meta['summit_inside_pilot_m'],0);self.assertLess(self.meta['summit_inside_pilot_m'],300)
    def test_native_road_shape_preserved(self):
        np.testing.assert_array_equal(self.data['xy'],interpolate(self.full['xy'],self.data['source_s3'],self.full['s3']))
    def test_native_altitudes_preserved(self):
        np.testing.assert_array_equal(self.data['z'],interpolate(self.full['z'],self.data['source_s3'],self.full['s3']))
    def test_axis_interpolation(self):
        v=np.arange(24).reshape(2,4,3)
        np.testing.assert_array_equal(interpolate(v,1.5,[0,1,2,3],axis=1),(v[:,1]+v[:,2])/2)
    def test_frame_is_orthonormal(self):
        for station in (0,12,150,280,300):
            p,t,n=frame(self.data,station);self.assertAlmostEqual(float(t@n),0);self.assertAlmostEqual(float(t@t),1);self.assertAlmostEqual(float(n@n),1)
    def test_ground_at_native_verge(self):
        for side in (0,1):
            point=self.data['sides'][side,20,2];distance=float(np.linalg.norm(point[:2]-self.data['xy'][20]))
            np.testing.assert_allclose(ground(self.data,float(self.data['s3'][20]),side,distance),point,atol=1e-7)
    def test_real_interesting_bend(self):self.assertGreater(self.meta['turn_degrees'],20)


class PilotDDSTests(unittest.TestCase):
    def write_image(self,image,coverage=False):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.dds';dds(image,path,coverage);return path.read_bytes()
    def test_bc3_full_mip_chain(self):
        result=inspect_dds(self.write_image(Image.new('RGBA',(32,16),(80,100,50,255))))
        self.assertEqual((result['format'],result['mips']),( 'DXT5',6))
    def test_smallest_levels_have_blocks(self):self.assertEqual(inspect_dds(self.write_image(Image.new('RGBA',(4,4),(80,90,50,255))))['mips'],3)
    def test_alpha_silhouette_retained(self):
        array=np.zeros((64,64,4),dtype='uint8');array[:,:,:3]=(80,100,50);array[12:52,12:52,3]=255
        blob=self.write_image(Image.fromarray(array),True);pixels=np.asarray(Image.open(io.BytesIO(blob)))
        self.assertEqual(int(pixels[0,0,3]),0);self.assertGreater(int(pixels[30,30,3]),240)
    def test_non_power_of_two_rejected(self):
        with self.assertRaises(ValueError):self.write_image(Image.new('RGBA',(19,17)))


class FoliageBakeTests(unittest.TestCase):
    def image(self,color):
        pixels=np.zeros((32,32,4),dtype='uint8');pixels[4:28,4:28,:]=color
        return Image.fromarray(pixels)
    def test_white_impostor_rejected(self):
        with self.assertRaises(ValueError):common.foliage_image_metrics(self.image((255,255,255,255)))
    def test_empty_impostor_rejected(self):
        with self.assertRaises(ValueError):common.foliage_image_metrics(Image.new('RGBA',(32,32)))
    def test_valid_colored_alpha_silhouette(self):
        metrics=common.foliage_image_metrics(self.image((60,85,35,255)))
        self.assertEqual(metrics['white_fraction'],0)
        self.assertGreater(metrics['alpha_coverage'],.1)
    def test_transparent_white_background_is_not_a_white_tree(self):
        pixels=np.full((32,32,4),255,dtype='uint8');pixels[:,:,3]=0;pixels[4:28,4:28,:]=(60,85,35,255)
        self.assertEqual(common.foliage_image_metrics(Image.fromarray(pixels))['white_fraction'],0)


class PilotWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.textures={'a.dds':b'deterministic texture','n.dds':b'deterministic normal'}
        cls.part=SimpleNamespace(vertices=[(-1,0,0),(1,0,0),(1,0,2),(-1,0,2)],normals=[(0,-1,0)]*4,uv=[(0,0),(1,0),(1,1),(0,1)],faces=[(0,1,2),(0,2,3)])
        cls.blob,cls.metrics=mesh_blob([(0,1,cls.part)],cls.textures,1,2)
    def test_checksum_known_vector(self):self.assertEqual(checksum(b''),0x02cc5d05)
    def test_coordinate_mapping(self):np.testing.assert_array_equal(vector_ac([[2,3,4]]),[[2,4,-3]])
    def test_coordinate_mapping_does_not_mutate(self):
        values=np.array([[2.,3.,4.]]);copy=values.copy();vector_ac(values);np.testing.assert_array_equal(values,copy)
    def test_round_trip(self):self.assertEqual(read_mesh(self.blob,self.textures),{'vertices':4,'triangles':2})
    def test_bad_texture_checksum_rejected(self):
        with self.assertRaises(ValueError):read_mesh(self.blob,{'a.dds':b'bad','n.dds':self.textures['n.dds']})
    def test_truncated_mesh_rejected(self):
        with self.assertRaises(ValueError):read_mesh(self.blob[:-8],self.textures)


class PilotSceneryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        with patch.object(common,'DATA',Path(cls.temporary.name)):
            cls.data,_=select_sector(source_data())
        cls.sea=int(np.argmin(cls.data['sides'][:,:,6,2].mean(axis=1)))
        cls.layout=edge_layout(cls.data,cls.sea)
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()
    def test_deterministic_layout(self):
        self.assertEqual(self.layout,edge_layout(self.data,self.sea))
    def test_canopies_do_not_encroach_on_shoulder(self):
        for p in self.layout:
            half=float(np.interp(p['station'],self.data['s3'],self.data['width']))/2
            self.assertGreaterEqual(p['offset']-p['width']/2,half+2.49)
            self.assertLess(p['offset']+p['width']/2,half+40)
    def test_vista_is_not_filled_by_screens(self):
        self.assertFalse(any(vista_open(p['station'],300,p['side'],self.sea) for p in self.layout))
    def test_two_understory_tiers_and_geometry_budget(self):
        self.assertEqual({p['tier'] for p in self.layout},{0,1})
        self.assertLess(len(self.layout)*8,3000)
    def test_native_ground_anchors(self):
        for p in self.layout:
            np.testing.assert_array_equal(p['position'],ground(self.data,p['station'],p['side'],p['offset']))
    def test_belts_cover_horizontally_without_filling_vista(self):
        for side in (0,1):
            for tier in (0,1):
                plants=[p for p in self.layout if p['side']==side and p['tier']==tier]
                for station in np.arange(8,292,1):
                    if side==self.sea and 198<station<255:continue
                    self.assertTrue(any(abs(p['station']-station)<=p['width']/2 for p in plants))


if __name__=='__main__':unittest.main()
