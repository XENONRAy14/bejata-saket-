import copy
import hashlib
import json
from pathlib import Path
import unittest

from scenery_placement import load_zones, plan_sector, RoadClearance, tree_radius
from summit_scenery import hedge_signature, natural_summit
from test_scenery_placement import route

ROOT=Path(__file__).resolve().parents[1]


class NaturalSummitTests(unittest.TestCase):
    def setUp(self):
        self.data=route();self.models=json.loads((ROOT/'data/pilot300/treefx_models.json').read_text())
        self.zones=copy.deepcopy(load_zones()['main']);self.accepted=plan_sector(self.data,self.models,0,300,zones=self.zones)
        wall=copy.deepcopy(self.accepted['edges'][0]);wall['tier']=2;self.accepted['edges'].append(wall)

    def test_pines_are_volumetric_families_irregular_and_hedge_is_unchanged(self):
        before=copy.deepcopy(self.accepted);result=natural_summit(self.data,self.models,self.accepted,self.zones)
        self.assertEqual(before,self.accepted);self.assertEqual(hedge_signature(result),hedge_signature(before))
        self.assertTrue(all(p['tier']<2 for p in result['edges']))
        pines=[p for p in result['trees'] if self.models[p['model']]['kind']!='shrub']
        self.assertTrue(pines);self.assertTrue(all(self.models[p['model']]['kind'] in ('pine','midstory') for p in pines))
        self.assertGreater(len({round(p['scale'],2) for p in pines}),5)
        self.assertTrue(all(RoadClearance(self.data).allows(p['position'],tree_radius(p,self.models),4) for p in pines))
        self.assertTrue(all(b['tree_instances']<=60 for b in result['report']['per_100m']))
        json.dumps(result)
        self.assertEqual(result,natural_summit(self.data,self.models,self.accepted,self.zones))

    def test_empty_excluded_and_missing_models(self):
        empty=dict(trees=[],edges=[],report={});self.assertEqual(natural_summit(self.data,{},empty,{}),empty)
        self.zones['exclusions']=[dict(start_m=0,end_m=400,side='both')]
        result=natural_summit(self.data,self.models,self.accepted,self.zones)
        self.assertTrue(all(self.models[p['model']]['kind']=='shrub' for p in result['trees']))
        shrubs=dict(self.accepted,trees=[p for p in self.accepted['trees'] if self.models[p['model']]['kind']=='shrub'])
        missing={name:spec for name,spec in self.models.items() if spec['kind']!='midstory'}
        with self.assertRaises(ValueError):natural_summit(self.data,missing,shrubs,self.zones)

    def test_committed_hedge_and_archive_match_accepted_lock(self):
        lock=json.loads((ROOT/'data/summit_hedge_lock.json').read_text());folder=ROOT/'out/scenery_qualification/summit'
        signature=hedge_signature(json.loads((folder/'scenery_placements.json').read_text()))
        for key,value in signature.items():self.assertEqual(lock[key],value)
        self.assertEqual(lock['archive_sha256'],hashlib.sha256((folder/'extension/trees/summit_shrub_cluster.bin').read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
