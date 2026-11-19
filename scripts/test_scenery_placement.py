import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from scenery_placement import (RoadClearance, edge_batches, edge_layout, load_zones,
    main_tree_layout, pilot_tree_layout, plan_sector, plan_sectors, sea_sides,
    sector_seed, tree_radius, vista_open, zone_contains)

ROOT=Path(__file__).resolve().parents[1]


def route():
    s=np.arange(0.,401.,2.)
    xy=np.column_stack([s,np.zeros(len(s))]);z=np.zeros(len(s))
    sides=np.zeros((2,len(s),7,3))
    for side,sign in enumerate((1,-1)):
        sides[side,:,:,:2]=xy[:,None,:]+np.array([0,sign])*np.linspace(3.5,60,7)[None,:,None]
        sides[side,:,:,2]=side*5
    return dict(s3=s,s=s,xy=xy,z=z,width=np.full(len(s),7.),
                tangent=np.tile([1.,0.],(len(s),1)),sides=sides)


class PilotPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with np.load(ROOT/'data/pilot300/centerline.npz') as source:cls.data=dict(source)
        cls.models=json.loads((ROOT/'data/pilot300/treefx_models.json').read_text())
        cls.sea=int(np.argmin(cls.data['sides'][:,:,6,2].mean(axis=1)))

    def compare(self,actual,filename):
        expected=json.loads((ROOT/'data/pilot300'/filename).read_text())
        self.assertEqual(len(actual),len(expected))
        for a,b in zip(actual,expected):
            self.assertEqual(a.keys(),b.keys())
            for key in a:
                if isinstance(a[key],str):self.assertEqual(a[key],b[key])
                else:np.testing.assert_allclose(a[key],b[key],rtol=0,atol=1e-6,err_msg=key)

    def test_pilot_trees_match_pre_refactor_placements(self):
        self.compare(pilot_tree_layout(self.data,self.models,self.sea),'plants.json')

    def test_pilot_edges_match_pre_refactor_placements(self):
        self.compare(edge_layout(self.data,self.sea),'edge_layout.json')

    def test_edge_batches_keep_original_lod_counts(self):
        layout=edge_layout(self.data,self.sea)
        for distant,triangles in ((False,2616),(True,1308)):
            batches=edge_batches(self.data,layout,distant=distant)
            self.assertEqual(len(batches),16)
            self.assertEqual(sum(len(v[1])*2 for v in batches.values()),triangles)


class SectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models=json.loads((ROOT/'data/pilot300/treefx_models.json').read_text())

    def setUp(self):
        self.data=route();self.zones=copy.deepcopy(load_zones()['main'])
        self.zones.update(vista_openings=[],exclusions=[])

    def test_sector_rebuild_is_independent_of_other_sectors(self):
        first=plan_sector(self.data,self.models,0,200,zones=self.zones)
        plan_sector(self.data,self.models,200,400,zones=self.zones)
        self.assertEqual(first,plan_sector(self.data,self.models,0,200,zones=self.zones))
        self.assertNotEqual(sector_seed(0),sector_seed(200))
        self.assertTrue(first['trees']);self.assertTrue(first['edges'])
        json.dumps(first)

    def test_local_sides_are_smoothed_and_can_switch(self):
        self.data['sides'][0,:100,-1,2]=10
        self.data['sides'][0,100:,-1,2]=0
        sea=sea_sides(self.data)
        self.assertEqual(sea(30),1);self.assertEqual(sea(370),0)
        self.data['sides'][0,20,-1,2]=-100
        self.assertEqual(sea_sides(self.data)(40),1)

    def test_vistas_use_absolute_intervals_and_local_side(self):
        self.zones['vista_openings']=[dict(start_m=120,end_m=180,side='sea')]
        self.assertTrue(vista_open(150,400,0,0,zones=self.zones))
        self.assertFalse(vista_open(150,400,1,0,zones=self.zones))
        plants=main_tree_layout(self.data,self.models,100,200,self.zones)
        self.assertFalse(any(120<p['station']<180 and p['side']==0 for p in plants))

    def test_all_layers_obey_exclusions_including_footprints(self):
        self.zones['exclusions']=[dict(start_m=100,end_m=200,side='both')]
        result=plan_sector(self.data,self.models,0,400,zones=self.zones)
        for kind in ('trees','edges'):
            for p in result[kind]:
                radius=tree_radius(p,self.models) if kind=='trees' else p['width']/2
                self.assertFalse(zone_contains(p['station'],p['side'],0,self.zones,'exclusions','edge',radius))

    def test_all_road_legs_and_between_sample_segments_have_clearance(self):
        data=route()
        data['xy']=np.array([[0.,0.],[100,0],[100,15],[0,15]])
        data['width']=np.full(4,7.)
        road=RoadClearance(data)
        self.assertFalse(road.allows([50,14,0],1,4))
        self.assertFalse(road.allows([50,0,0],1,4))
        self.assertTrue(road.allows([50,-12,0],1,4))
        result=plan_sector(self.data,self.models,0,400,zones=self.zones)
        road=RoadClearance(self.data)
        for kind in ('trees','edges'):
            for p in result[kind]:
                radius=tree_radius(p,self.models) if kind=='trees' else p['width']/2
                self.assertTrue(road.allows(p['position'],radius,4))

    def test_sector_and_full_route_budget(self):
        reports=plan_sectors(self.data,self.models,[dict(name='a',start_m=0,end_m=200),dict(name='b',start_m=200,end_m=400)],zones=self.zones)
        for result in reports.values():
            self.assertLessEqual(result['report']['tree_instances_per_100m'],51)
            self.assertTrue(result['report']['budget_passed'])
            self.assertLessEqual(result['report']['full_route_budget_ceiling'],8000)
        self.assertLessEqual(sum(v['report']['tree_instances'] for v in reports.values()),204)
        self.zones['max_tree_instances_total']=20
        self.assertLessEqual(plan_sector(self.data,self.models,0,400,zones=self.zones)['report']['tree_instances'],20)

    def test_empty_excluded_sector_and_submetre_sector(self):
        self.zones['exclusions']=[dict(start_m=-1,end_m=401,side='both')]
        result=plan_sector(self.data,self.models,0,400,zones=self.zones)
        self.assertEqual(result['trees'],[]);self.assertEqual(result['edges'],[])
        self.assertIsNone(result['report']['minimum_all_road_leg_clearance_m'])
        self.assertEqual(plan_sector(self.data,self.models,0,.1,zones=self.zones)['trees'],[])

    def test_invalid_intervals_budgets_and_models(self):
        for a,b in ((0,0),(-1,100),(100,500),(np.nan,100)):
            with self.subTest(a=a,b=b),self.assertRaises(ValueError):plan_sector(self.data,self.models,a,b,zones=self.zones)
        with self.assertRaises(ValueError):plan_sector(self.data,{},0,100,zones=self.zones)
        self.zones['max_tree_instances_per_100m']=52
        with self.assertRaises(ValueError):plan_sector(self.data,self.models,0,100,zones=self.zones)
        with self.assertRaises(ValueError):plan_sectors(self.data,self.models,[dict(name='a',start_m=0,end_m=200),dict(name='b',start_m=100,end_m=400)])

    def test_malformed_zone_configuration_is_rejected(self):
        config=load_zones();config['main']['exclusions']=[dict(start_m=20,end_m=10)]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'zones.json';path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):load_zones(path)


if __name__=='__main__':unittest.main()
