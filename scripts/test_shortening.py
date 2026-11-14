import json
from pathlib import Path
import unittest

import numpy as np

from acdata import plan_empties, road_point
from shortening import active_chainage, canonical_chainage, road_distance, shorten


ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'data/track_layout.json').read_text())


def mountain():
    s=np.arange(0,16001,2,dtype=float)
    z=np.interp(s,[0,3000,4000,6000,12000,14000,16000],[20,150,120,330,40,100,15])
    xy=np.column_stack([s,np.sin(s/1000)*50])
    tangent=np.gradient(xy,axis=0);tangent/=np.linalg.norm(tangent,axis=1)[:,None]
    normal=np.column_stack([-tangent[:,1],tangent[:,0]])
    offsets=np.tile([3.5,3.8,5.3,13.3,21.3,31.3,45.3],(2,len(s),1))
    sides=np.zeros((2,len(s),7,3))
    for side,sign in enumerate((1,-1)):
        sides[side,:,:,:2]=xy[:,None]+normal[:,None]*sign*offsets[side,:,:,None]
        sides[side,:,:,2]=z[:,None]
    return dict(s=s,xy=xy,z=z,raw=z.copy(),filtered=z.copy(),tangent=tangent,normal=normal,width=np.full(len(s),7.),sides=sides,offsets=offsets,guard=np.zeros((2,len(s)),bool),cut=np.zeros((2,len(s)),bool))


class ShorteningTests(unittest.TestCase):
    def test_main_summit_not_secondary(self):
        full=mountain();data,info=shorten(full,CONFIG)
        self.assertEqual(info['canonical_summit_2d_m'],6000)
        self.assertGreater(info['main_descent_drop_m'],250)
        self.assertGreater(info['main_descent_length_3d_m'],5000)
        distance=road_distance(data)
        summit=np.searchsorted(data['source_s'],info['canonical_summit_2d_m'])
        spawn=np.searchsorted(data['s'],float(data['spawn_s']))
        self.assertAlmostEqual(distance[summit]-distance[spawn],1000,places=7)
        self.assertAlmostEqual(distance[spawn],30,places=7)
        self.assertAlmostEqual(float(active_chainage(data,canonical_chainage(data,123))),123)

    def test_retained_arrays_are_exact_suffix(self):
        full=mountain();data,info=shorten(full,CONFIG)
        old=np.flatnonzero(full['s']>info['canonical_cut_2d_m'])
        new=np.searchsorted(data['source_s'],full['s'][old])
        for key in ('xy','z','raw','filtered','width','normal','tangent'):
            np.testing.assert_array_equal(data[key][new],full[key][old])
        for key in ('sides','offsets','guard','cut'):
            np.testing.assert_array_equal(data[key][:,new],full[key][:,old])
        self.assertEqual(data['guard'].dtype,bool)
        self.assertEqual(data['cut'].dtype,bool)
        self.assertGreater(data['source_s'].min(),0)

    def test_grid_on_road_facing_forward_and_gate_order(self):
        data,info=shorten(mountain(),CONFIG);plan=plan_empties(data)
        spawns={e['name']:e for e in plan['empties'] if e['name'].startswith(('AC_START_','AC_PIT_','AC_HOTLAP_START_'))}
        self.assertEqual(len(spawns),9)
        self.assertEqual(spawns['AC_START_0']['chainage_m'],float(data['spawn_s']))
        self.assertEqual(spawns['AC_PIT_0']['chainage_m'],float(data['spawn_s']))
        for spawn in spawns.values():
            _,tangent,_,width=road_point(data,spawn['chainage_m'])
            self.assertLess(abs(spawn['lateral_m'])+1,width/2)
            yaw=np.radians(spawn['yaw_deg'])
            np.testing.assert_allclose([np.sin(yaw),-np.cos(yaw)],tangent,atol=1e-12)
        for prefix in ('AC_PIT_','AC_START_'):
            cars=np.array([spawns[prefix+str(i)]['position_m'] for i in range(4)])
            self.assertTrue((np.linalg.norm(np.diff(cars,axis=0),axis=1)>7).all())
        self.assertGreater(plan['start_gate_m'],float(data['spawn_s']))
        self.assertLess(plan['start_gate_m'],plan['finish_gate_m'])
        self.assertLess(plan['staging_end_m'],100)

    def test_rejects_flat_small_descent_and_bad_config(self):
        full=mountain();full['z'][:]=20
        with self.assertRaisesRegex(ValueError,'No prominent summit'):shorten(full,CONFIG)
        full=mountain()
        with self.assertRaises(ValueError):shorten(full,dict(CONFIG,spawn_before_summit_3d_m=-1))
        with self.assertRaisesRegex(ValueError,'required main descent'):shorten(full,dict(CONFIG,minimum_main_descent_drop_m=500))
        with self.assertRaises(ValueError):shorten(full,dict(CONFIG,spawn_before_summit_3d_m=12000))

    def test_real_canonical_road(self):
        full_path=ROOT/'data/full_centerline.npz'
        if not full_path.exists():self.skipTest('Run build.py centerline for the integration fixture')
        full=np.load(full_path);data,info=shorten(full,CONFIG)
        self.assertAlmostEqual(info['canonical_summit_2d_m'],9591.581,delta=.01)
        self.assertAlmostEqual(info['canonical_spawn_3d_m'],8602.888,delta=.01)
        summit=np.searchsorted(data['source_s'],info['canonical_summit_2d_m'])
        spawn=np.searchsorted(data['s'],float(data['spawn_s']))
        self.assertAlmostEqual(road_distance(data)[summit]-road_distance(data)[spawn],1000,delta=.001)
        old=np.flatnonzero(full['s']>info['canonical_cut_2d_m'])
        new=np.searchsorted(data['source_s'],full['s'][old])
        np.testing.assert_array_equal(data['sides'][:,new],full['sides'][:,old])
        np.testing.assert_array_equal(data['xy'][new],full['xy'][old])
        np.testing.assert_array_equal(data['z'][new],full['z'][old])
        plan=plan_empties(data)
        self.assertLess(plan['staging_end_m'],100)


if __name__=='__main__':unittest.main()
