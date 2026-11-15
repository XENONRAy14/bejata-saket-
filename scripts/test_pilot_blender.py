"""Regression test against Blender's real polygon/material-slot behaviour."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from pilot_common import replace_material_slots

class MaterialSlotRegressionTests(unittest.TestCase):
    def make_mesh(self):
        mesh=bpy.data.meshes.new('slot_regression')
        mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0),(2,0,0),(3,0,0),(2,1,0)],[],[(0,1,2),(3,4,5)])
        for name in ('unused','leaf','bark'):mesh.materials.append(bpy.data.materials.new('regression_'+name))
        mesh.polygons[0].material_index=1;mesh.polygons[1].material_index=2
        return mesh
    def test_clear_is_not_safe_for_bake_material_replacement(self):
        mesh=self.make_mesh();mesh.materials.clear()
        self.assertEqual([p.material_index for p in mesh.polygons],[0,0])
        bpy.data.meshes.remove(mesh)
    def test_in_place_replacement_preserves_leaf_and_bark_assignments(self):
        mesh=self.make_mesh();old=list(mesh.materials)
        replace_material_slots(mesh,lambda material:material.copy())
        self.assertEqual([p.material_index for p in mesh.polygons],[1,2])
        self.assertTrue(all(a!=b for a,b in zip(old,mesh.materials)))
        self.assertEqual([len(p.vertices) for p in mesh.polygons],[3,3])
        bpy.data.meshes.remove(mesh)

class CardLodTests(unittest.TestCase):
    def test_shrub_leaves_export_both_sides_without_duplicating_bark(self):
        from pilot_treefx import groups_for_mesh
        mesh=MaterialSlotRegressionTests().make_mesh();mesh.uv_layers.new()
        specs={m.name:dict(textures=dict(txDiffuse=dict(textureName='color.dds'),txNormal=dict(textureName='normal.dds')),preview=dict(kind='foliage' if 'regression_leaf' in m.name else 'simple')) for m in mesh.materials}
        groups=groups_for_mesh(mesh,specs,['color.dds','normal.dds'],double_sided=True)
        self.assertEqual([len(group[2].faces) for group in groups],[2,1])
        self.assertEqual(set(groups[0][2].normals),{(0.,0.,1.),(0.,0.,-1.)})
        bpy.data.meshes.remove(mesh)
    def test_medium_lod_keeps_two_orthogonal_views(self):
        from pilot_treefx import reduce_card_views
        mesh=bpy.data.meshes.new('card_lod_regression')
        mesh.from_pydata([(0,0,0),(1,0,0),(1,0,1),(0,0,1),(2,0,0),(3,0,0),(3,0,1),(2,0,1)],[],[(0,1,2,3),(4,5,6,7)])
        mesh.materials.append(bpy.data.materials.new('PH_test_card'))
        layer=mesh.uv_layers.new(name='UVMap')
        for face in mesh.polygons:
            for loop in face.loop_indices:layer.data[loop].uv=(.25 if face.index==0 else .75,.75)
        reduce_card_views(mesh)
        self.assertEqual(len(mesh.polygons),1)
        self.assertEqual(len(mesh.uv_layers.active.data),4)
        bpy.data.meshes.remove(mesh)

suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(MaterialSlotRegressionTests),unittest.defaultTestLoader.loadTestsFromTestCase(CardLodTests)])
result=unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():raise RuntimeError('Blender material-slot regression')
print('PILOT_BLENDER_REGRESSION_OK',result.testsRun)
