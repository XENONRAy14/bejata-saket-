import unittest

import numpy as np
from rasterio.transform import from_origin

from geometry import DEM, FORWARD, boundary_crossings, frames, nearest_on_polyline, resample, runs, safe_ribbon, safe_sections, smooth_elevation, smooth_xy, width_from_tags


class GeometryTests(unittest.TestCase):
    def test_resample_endpoints(self):
        p,s = resample([[0,0],[0,0],[10,0]],2)
        self.assertEqual(len(p),6)
        np.testing.assert_allclose(p[[0,-1]],[[0,0],[10,0]])
        self.assertLessEqual(np.diff(s).max(),2)

    def test_empty_and_degenerate(self):
        for points in ([], [[0,0]], [[0,0],[0,0]], [[0,0],[float('nan'),0]]):
            with self.assertRaises(ValueError):
                resample(points)
        for spacing in (0,-1,float('nan')):
            with self.assertRaises(ValueError):
                resample([[0,0],[1,0]],spacing)

    def test_smoothing_deviation(self):
        p,_ = resample([[0,0],[10,0],[10,10]],.5)
        q = smooth_xy(p)
        np.testing.assert_allclose(q[[0,-1]],p[[0,-1]])
        self.assertLessEqual(np.linalg.norm(q-nearest_on_polyline(q,p),axis=1).max(),2.800001)
        with self.assertRaises(ValueError):
            smooth_xy([])

    def test_grade_and_vertical_curvature(self):
        s = np.arange(1000)*2.
        raw = np.sin(s/40)*40
        raw[300] += 200
        z = smooth_elevation(raw,s)
        grade = np.diff(z)/2
        self.assertLessEqual(abs(grade).max(),.120001)
        self.assertLessEqual(abs(np.diff(grade)).max()/2,.001001)
        with self.assertRaises(ValueError):
            smooth_elevation(np.array([1.,float('nan')]),np.array([0,1]))
        for raw,s in (([],[]),([1,2],[0,0]),([1,2],[0,float('nan')])):
            with self.assertRaises(ValueError):
                smooth_elevation(raw,s)

    def test_widths(self):
        self.assertEqual(width_from_tags(dict(width='8 m', lanes='2')),8)
        self.assertEqual(width_from_tags(dict(width='unknown',lanes='2')),6.5)
        self.assertEqual(width_from_tags(dict(highway='primary_link')),7)
        self.assertEqual(width_from_tags({}),6)

    def test_frames_and_runs(self):
        p = np.column_stack([np.arange(100),np.zeros(100)])
        t,n,c = frames(p,np.arange(100))
        np.testing.assert_allclose(n,np.tile([0,1],(100,1)))
        np.testing.assert_allclose(c,0)
        mask = np.zeros(130,dtype=bool)
        mask[5:35] = True
        mask[40:80] = True
        mask[110:115] = True
        out = runs(mask,np.arange(130))
        self.assertTrue(out[35:40].all())
        self.assertFalse(out[110:115].any())
        self.assertFalse(runs(np.zeros(100,dtype=bool),np.arange(100)).any())
        self.assertEqual(len(runs([],np.array([]))),0)
        for points in ([],[[0,0],[0,0]],[[0,0],[1,0],[0,0]]):
            with self.assertRaises(ValueError):
                frames(points,np.arange(len(points)))

    def test_bilinear_dem_and_errors(self):
        dem = DEM.__new__(DEM)
        dem.origin = np.array([0,0])
        transform = from_origin(4,37,.5,.5)
        bounds = type('Bounds',(),dict(left=4,right=5,bottom=36,top=37))()
        dem.tiles = [(np.array([[10.,20.],[30.,40.]]),transform,bounds,-9999)]
        point = np.array([FORWARD.transform(4.5,36.5)])
        np.testing.assert_allclose(dem.sample(point),[25],atol=1e-6)
        self.assertEqual(len(dem.sample(np.empty((0,2)))),0)
        with self.assertRaises(ValueError):
            dem.sample(np.array([FORWARD.transform(1,1)]))
        dem.tiles[0][0][0,0] = -9999
        with self.assertRaises(ValueError):
            dem.sample(point)

    def test_sharp_sections_do_not_fold(self):
        xy,s = resample([[0,0],[30,0],[12,3],[12,30]],.5)
        xy = smooth_xy(xy)
        s = np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        _,normal,_ = frames(xy,s)
        for sign in (1,-1):
            cols,p = safe_sections(xy,normal,np.full(len(s),7.),np.full(len(s),44.),sign)
            a,b,c,d = p[:-1,:-1],p[1:,:-1],p[1:,1:],p[:-1,1:]
            cross = lambda u,v: u[...,0]*v[...,1]-u[...,1]*v[...,0]
            self.assertTrue((cross(b-a,c-a)*sign > 0).all())
            self.assertTrue((cross(c-a,d-a)*sign > 0).all())
            self.assertTrue((np.diff(cols,axis=1) > 0).all())
        with self.assertRaises(ValueError):
            safe_sections(xy,normal,np.ones(len(s)),np.zeros(len(s)),1)
        with self.assertRaises(ValueError):
            safe_sections(np.empty((0,2)),np.empty((0,2)),np.array([]),np.array([]),1)

        sections = safe_ribbon(xy,normal,np.full(len(s),7.),np.full((len(s),2),44.))
        for column in range(7):
            outline = np.concatenate([sections[0][1][:,column],sections[1][1][::-1,column]])
            self.assertEqual(len(boundary_crossings(outline)),0)

    def test_boundary_crossings(self):
        self.assertEqual(len(boundary_crossings([[0,0],[1,1],[0,1],[1,0]])),1)
        self.assertEqual(len(boundary_crossings([[0,0],[1,0],[1,1],[0,1]])),0)
        self.assertEqual(len(boundary_crossings([])),0)
        with self.assertRaises(ValueError):
            boundary_crossings([[0,0],[1,0]])


if __name__ == '__main__':
    unittest.main()
