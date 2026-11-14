import json
from pathlib import Path
import tempfile
import unittest
from csp import ROOT,generate,config_materials


class CspTests(unittest.TestCase):
    def test_generate_and_reject_missing_materials(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir();(root/'scripts').mkdir()
            (root/'scripts/ext_config.ini.template').write_text((ROOT/'scripts/ext_config.ini.template').read_text())
            names=['asphalt','asphalt_v1','asphalt_v2','grass','grass_mountain','kerb','gravel','rock','sand','plaster','metal','bark','maquis','olive_foliage','pine_foliage','water']
            info=dict(kn5_materials=names,materials={n:dict(preview=dict(kind='road' if n.startswith('asphalt') else 'terrain')) for n in names[:5]})
            path=root/'data/materials_info.json';path.write_text(json.dumps(info))
            text=generate(root);config,refs=config_materials(text)
            self.assertEqual(text,generate(root));self.assertEqual(config['Material_Water']['Materials'],'water')
            self.assertEqual(set(config['GRASS_FX']['GRASS_MATERIALS'].split(', ')),{'grass','grass_mountain'})
            self.assertNotIn('LINES_MATERIALS',config['RAIN_FX']);self.assertTrue(refs<=set(names))
            info['kn5_materials']=[];path.write_text(json.dumps(info))
            with self.assertRaises(ValueError):generate(root)
            info['kn5_materials']=names[:-1];path.write_text(json.dumps(info))
            with self.assertRaises(ValueError):generate(root)

    def test_empty_and_invalid_selectors(self):
        for text in ('[GRASS_FX]\nGRASS_MATERIALS=','[GRASS_FX]\nGRASS_MATERIALS=grass,'):
            with self.assertRaises(ValueError):config_materials(text)
