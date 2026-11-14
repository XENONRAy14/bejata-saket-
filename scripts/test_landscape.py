import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import shapely
from shapely.geometry import box,Polygon,LineString
from landscape import triangulate_domain,edge_height,height_field


class LandscapeTests(unittest.TestCase):
    def test_conforming_multiresolution_and_hairpin_hole(self):
        xx,yy=np.meshgrid(np.arange(0,101,10),np.arange(0,101,10))
        points=np.column_stack([xx.ravel(),yy.ravel()])
        coarse=np.array([[-30,-30],[130,-30],[130,130],[-30,130]])
        hole=Polygon([(20,10),(35,10),(35,70),(65,70),(65,10),(80,10),(80,85),(20,85)])
        domain=box(0,0,100,100).difference(hole)
        xy,faces=triangulate_domain(np.vstack([points,coarse]),domain)
        polygons=shapely.polygons(xy[faces])
        self.assertAlmostEqual(shapely.area(polygons).sum(),domain.area,places=5)
        self.assertLess(shapely.area(shapely.intersection(polygons,hole)).sum(),1e-6)
        edges=np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1)
        edges,count=np.unique(edges,axis=0,return_counts=True)
        boundary=xy[edges[count==1]].mean(1)
        self.assertLess(shapely.distance(shapely.points(boundary),domain.boundary).max(),1e-6)

    def test_edge_height_interpolation_and_caps(self):
        segments=np.array([[[0,0,10],[10,0,20]],[[10,0,20],[10,10,30]]])
        distance,z=edge_height(np.array([[3,1],[11,7]]),segments)
        np.testing.assert_allclose(distance,[1,1]);np.testing.assert_allclose(z,[13,27])

    def test_empty_or_invalid_domain(self):
        for points,domain in ((np.empty((0,2)),box(0,0,1,1)),(np.array([[0,0],[1,0],[0,1]]),Polygon())):
            with self.assertRaises(ValueError):triangulate_domain(points,domain)

    def test_exact_nearest_segment_not_nearest_midpoint(self):
        segments=np.array([[[-100,0,10],[100,0,30]]]+[[[89,4+i*.1,100],[91,4+i*.1,100]] for i in range(10)])
        distance,z=edge_height(np.array([[90,1]]),segments)
        np.testing.assert_allclose(distance,[1]);np.testing.assert_allclose(z,[29])

    def test_beach_support_and_empty_beach(self):
        class FlatDEM:
            def sample(self,points):return np.zeros(len(points))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            beach=np.array([[-2,-2,5],[2,-2,5],[0,2,5]])
            points=np.array([[0,0],[10,0]])
            for faces,expected in ((np.array([[0,1,2]]),[4.985,0]),(np.empty((0,3),int),[0,0])):
                np.savez(root/'data/decor_plan.npz',beach=beach,beach_faces=faces)
                with patch('landscape.ROOT',root):
                    z=height_field(points,{'xy':np.array([[0,0]])},FlatDEM(),box(-100,-100,100,100),LineString([[-100,-100],[-100,100]]),np.array([[[-100,-100,0],[100,-100,0]]]))
                np.testing.assert_allclose(z,expected)
