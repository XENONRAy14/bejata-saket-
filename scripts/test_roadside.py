import unittest
import numpy as np

from roadside import Mesh, plan, sign_atlas, sign_spec
from vegetation import Terrain


class RoadsideTests(unittest.TestCase):
    def test_box_and_board_geometry(self):
        mesh=Mesh();mesh.box([3,4,5],[4,2,2],[0,1])
        vertices=np.asarray(mesh.vertices)
        np.testing.assert_allclose(vertices.min(0),[2,2,4]);np.testing.assert_allclose(vertices.max(0),[4,6,6])
        self.assertEqual(len(mesh.faces),12);self.assertEqual(len(mesh.uv),24)
        tri=vertices[np.asarray(mesh.faces)]
        self.assertTrue((np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)>0).all())

    def test_procedural_atlas_and_recipe(self):
        a=np.asarray(sign_atlas(256));np.testing.assert_array_equal(a,sign_atlas(256))
        self.assertEqual(a.shape,(256,256,3));self.assertGreater(a.std(),20)
        self.assertEqual(sign_spec()['shaderName'],'ksPerPixel')
        for size in (0,255):
            with self.assertRaises(ValueError):sign_atlas(size)

    def test_plan_empty_houses_and_unavailable_terrain(self):
        s=np.arange(0,3001,10);xy=np.column_stack([s,np.zeros(len(s))]);sides=np.zeros((2,len(s),3,3))
        for side,sign in enumerate((1,-1)):
            sides[side,:,2,:2]=xy+[0,5*sign];sides[side,:,2,2]=10
        data=dict(s=s,z=np.full(len(s),10.),xy=xy,sides=sides,tangent=np.tile([1.,0],(len(s),1)),cut=np.zeros((2,len(s)),bool),guard=np.zeros((2,len(s)),bool))
        terrain=Terrain(np.array([[[-100,-100,10],[4000,-100,10],[4000,100,10]],[[-100,-100,10],[4000,100,10],[-100,100,10]]]))
        batches,info=plan(data,np.empty((0,14)),terrain)
        self.assertEqual(info['counts']['bus_stops'],2);self.assertEqual(info['counts']['speed_signs'],4)
        self.assertEqual(info['counts']['fences'],0);self.assertGreater(len(batches),0)
        far=Terrain(np.array([[[-100,-100,10],[-90,-100,10],[-90,-90,10]]]))
        batches,info=plan(data,np.empty((0,14)),far)
        self.assertFalse(batches);self.assertEqual(sum(info['counts'].values()),0)
        with self.assertRaises(ValueError):plan(dict(s=[]),np.empty((0,14)),terrain)


if __name__=='__main__':unittest.main()
