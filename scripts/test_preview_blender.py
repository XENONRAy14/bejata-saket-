import io
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_scenery_preview import material


class PreviewTextureTests(unittest.TestCase):
    def test_changed_same_named_texture_never_reuses_old_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            images=[]
            for name,color in [('old',(255,0,0)),('new',(0,255,0))]:
                data=io.BytesIO();Image.new('RGB',(8,8),color).save(data,format='PNG')
                mat=material(name,('same.png',data.getvalue()),Path(directory))
                images.append(next(n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE'))
            self.assertNotEqual(images[0].filepath,images[1].filepath)
            self.assertGreater(images[0].pixels[0],.99);self.assertGreater(images[1].pixels[1],.99)
            empty=material('empty',None,Path(directory));self.assertFalse(any(n.type=='TEX_IMAGE' for n in empty.node_tree.nodes))
            with self.assertRaises(ValueError):material('bad',('bad.png',b'invalid'),Path(directory))


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PreviewTextureTests)
    if not unittest.TextTestRunner().run(suite).wasSuccessful():sys.exit(1)
