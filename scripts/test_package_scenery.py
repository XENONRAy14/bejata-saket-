import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from package_scenery import package


class SceneryPackageTests(unittest.TestCase):
    def source(self,root):
        source=root/'source';source.mkdir()
        for name in ('bejaia_saket.kn5','data/surfaces.ini','extension/ext_config.ini','extension/trees/trees.txt'):
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
        (source/'ui').mkdir();(source/'ui/ui_track.json').write_text(json.dumps(dict(name='Main',author='Équipe'),ensure_ascii=False),encoding='utf-8')
        (source/'after.png').write_bytes(b'not an install file')
        return source

    def test_separate_consistent_reproducible_install_and_source_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=self.source(root);before={str(p.relative_to(source)):p.read_bytes() for p in source.rglob('*') if p.is_file()}
            result=package(source,root/'install');track=Path(result['folder']);metadata=json.loads((track/'ui/ui_track.json').read_text(encoding='utf-8'))
            self.assertNotEqual(metadata['name'],'Main');self.assertEqual(metadata['author'],'Équipe')
            self.assertIn('FILE='+track.name+'.kn5',(track/'models.ini').read_text());self.assertFalse((track/'after.png').exists())
            with zipfile.ZipFile(result['zip']) as archive:
                self.assertIsNone(archive.testzip())
                for path in track.rglob('*'):
                    if path.is_file():self.assertEqual(archive.read('content/tracks/'+track.name+'/'+path.relative_to(track).as_posix()),path.read_bytes())
            self.assertEqual(before,{str(p.relative_to(source)):p.read_bytes() for p in source.rglob('*') if p.is_file()})
            again=package(source,root/'another')
            self.assertEqual(hashlib.sha256(Path(result['zip']).read_bytes()).digest(),hashlib.sha256(Path(again['zip']).read_bytes()).digest())
            with self.assertRaises(FileExistsError):package(source,root/'install')

    def test_missing_source_invalid_id_and_recursive_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):package(root/'missing',root/'install')
            source=self.source(root)
            with self.assertRaises(ValueError):package(source,root/'install','../main')
            with self.assertRaises(ValueError):package(source,source/'nested')
            self.assertFalse((root/'install').exists())


if __name__=='__main__':unittest.main()
