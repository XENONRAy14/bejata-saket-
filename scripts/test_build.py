import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import build


class BuildTests(unittest.TestCase):
    def test_optional_render_dispatch(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(build,'ROOT',Path(folder)),patch('sys.argv',['build.py','render']),patch('materials.render') as render:
            build.main()
            render.assert_called_once()

    def test_default_and_explicit_all_order(self):
        for arguments in (['build.py'],['build.py','all'],['build.py','all','--kn5-vegetation']):
            with self.subTest(arguments=arguments),tempfile.TemporaryDirectory() as folder:
                with patch.object(build,'ROOT',Path(folder)),patch('sys.argv',arguments),patch('build.subprocess.run') as run,patch('build.package') as package,contextlib.redirect_stdout(io.StringIO()):
                    build.main()
                self.assertEqual([c.args[0][2] for c in run.call_args_list[:-1]],['assets','route','dem','centerline','mesh','acdata','decor','materials','landscape','vegetation','csp'])
                self.assertTrue(run.call_args_list[-1].args[0][1].endswith('scripts/validate.py'))
                self.assertTrue(all(c.kwargs['check'] for c in run.call_args_list))
                self.assertTrue(all(('--kn5-vegetation' in c.args[0])==('--kn5-vegetation' in arguments) for c in run.call_args_list[:-1]))
                package.assert_called_once()

    def test_all_stops_on_failure(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(build,'ROOT',Path(folder)),patch('sys.argv',['build.py','all']),patch('build.subprocess.run',side_effect=subprocess.CalledProcessError(1,'route')),patch('build.package') as package:
            with self.assertRaises(subprocess.CalledProcessError):
                build.main()
            package.assert_not_called()

    def test_raw_download_and_extraction_cache(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(build,'ROOT',Path(folder)):
            (Path(folder)/'data').mkdir()
            handler=SimpleNamespace(ways=[],places=[],apply_file=Mock())
            def download(url,path):
                Path(path).write_bytes(b'raw fixture')
            with patch('build.urllib.request.urlretrieve',side_effect=download) as retrieve,patch('build.Extract',return_value=handler):
                first=build.load()
                self.assertEqual(first['ways'],[])
                retrieve.assert_called_once()
                self.assertEqual((Path(folder)/'data/algeria-latest.osm.pbf').read_bytes(),b'raw fixture')
                self.assertFalse((Path(folder)/'data/algeria-latest.osm.pbf.partial').exists())
                self.assertEqual(build.load(),json.loads(json.dumps(first)))
                retrieve.assert_called_once()
                handler.apply_file.assert_called_once()


if __name__=='__main__':
    unittest.main()
