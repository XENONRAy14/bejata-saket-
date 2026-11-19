import configparser
import unittest

from scenery_preview_common import tree_lod


class PreviewLodTests(unittest.TestCase):
    def config(self,distances):
        config=configparser.ConfigParser()
        for i,distance in enumerate(distances):config[f'LOD_{i}']={'DISTANCE':str(distance)}
        return config

    def test_shrub_near_and_mid_lods_do_not_disappear(self):
        config=self.config([20,75,900])
        for distance,lod in [(0,0),(19.99,0),(20,1),(27,1),(74.99,1),(75,2),(99,2),(899,2),(900,None)]:
            self.assertEqual(tree_lod(config,distance),lod)

    def test_midstory_retains_medium_until_110m(self):
        config=self.config([28,110,900])
        self.assertEqual(tree_lod(config,105),1);self.assertEqual(tree_lod(config,110),2)

    def test_two_lod_and_empty_archives(self):
        self.assertEqual(tree_lod(self.config([150,900]),149),0)
        self.assertEqual(tree_lod(self.config([150,900]),150),1)
        self.assertIsNone(tree_lod(self.config([]),0))

    def test_bad_ranges_and_distances_fail(self):
        for distance in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):tree_lod(self.config([20,75]),distance)
        with self.assertRaises(ValueError):tree_lod(self.config([20,10]),25)


if __name__=='__main__':unittest.main()
