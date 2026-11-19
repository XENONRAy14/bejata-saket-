import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from scenery_metrics import compare_views, measure_pixels, polygon_mask, save_measurement


class SceneryMetricsTests(unittest.TestCase):
    def fixture(self):
        beauty=np.full((16,16,3),180,dtype=np.uint8);ids=np.zeros_like(beauty)
        ids[:8,:,0]=255;ids[8:,:8,1]=255
        left=np.zeros((16,16),bool);left[8:,:8]=True
        right=np.zeros_like(left);right[8:,8:]=True
        return beauty,ids,dict(left=left,right=right)

    def test_exact_coverage_and_pale_hillside_exclude_background(self):
        beauty,ids,bands=self.fixture();report,masks=measure_pixels(beauty,ids,bands)
        self.assertEqual(report['coverage']['left']['foliage_share'],1)
        self.assertEqual(report['coverage']['right']['foliage_share'],0)
        self.assertEqual(report['pale_hillside_pixels'],128)
        self.assertEqual(report['pale_hillside_share_of_frame'],.5)
        self.assertEqual(int(masks['foliage'].sum()),64)
        ids[:8]=0
        self.assertEqual(measure_pixels(beauty,ids,bands)[0]['pale_hillside_pixels'],0)

    def test_empty_mismatched_and_bad_projection_are_rejected(self):
        beauty,ids,bands=self.fixture();bands['left'][:]=False
        with self.assertRaises(ValueError):measure_pixels(beauty,ids,bands)
        with self.assertRaises(ValueError):measure_pixels(beauty[:8],ids,bands)
        with self.assertRaises(ValueError):polygon_mask((16,16),[[[0,0],[float('nan'),1],[2,2],[0,2]]])
        self.assertFalse(polygon_mask((16,16),[]).any())

    def test_antialias_coverage_is_measured_in_linear_space(self):
        beauty,ids,bands=self.fixture();ids[8:,:8]=[0,188,0]
        report,_=measure_pixels(beauty,ids,bands)
        self.assertAlmostEqual(report['coverage']['left']['foliage_share'],.5,delta=.005)

    def test_saved_comparison_uses_identical_bands_and_counts_real_occlusion(self):
        beauty,ids,bands=self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            for suffix in ('','_exit_reverse'):
                save_measurement(output,'before'+suffix,beauty,ids,bands,(100,180))
                after=ids.copy();after[:8]=[0,255,0]
                save_measurement(output,'after'+suffix,beauty,after,bands,(100,180))
            report=compare_views(output)
            self.assertEqual(report['summit']['baseline_pale_occluded_by_foliage_share'],1)
            self.assertEqual(report['summit']['baseline_pale_remaining_pixels'],0)
            self.assertEqual(json.loads((output/'after_metrics.json').read_text())['treated_station_interval_m'],[100,180])
            Image.new('L',(16,16)).save(output/'after_left_band.png')
            with self.assertRaises(ValueError):compare_views(output)

    def test_foliage_growth_cannot_hide_unchanged_pale_coverage(self):
        beauty,ids,bands=self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            for suffix in ('','_exit_reverse'):
                save_measurement(output,'before'+suffix,beauty,ids,bands,(100,180))
                after=ids.copy();after[:8]=[255,255,0]
                save_measurement(output,'after'+suffix,beauty,after,bands,(100,180))
            self.assertEqual(compare_views(output)['summit']['baseline_pale_occluded_by_foliage_pixels'],0)
            for suffix in ('','_exit_reverse'):
                after[:8]=[188,255,0]
                save_measurement(output,'after'+suffix,beauty,after,bands,(100,180))
            report=compare_views(output)['summit']
            self.assertLessEqual(report['baseline_pale_occluded_by_foliage_pixels'],report['baseline_pale_pixels']-report['baseline_pale_remaining_pixels'])


if __name__=='__main__':unittest.main()
