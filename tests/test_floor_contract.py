import unittest
from asset_director.core import DirectorError
from asset_director.floor_contract import validate
from asset_director.pose_contract import validate as validate_pose


class FloorContractTests(unittest.TestCase):
    def setUp(self):
        self.options=dict(size=[10,12],location=[0,0,0],color=[.2]*3,grid_color=[.22]*3,tile_size=1,roughness=.8)

    def test_valid(self):
        validate(self.options)

    def test_rejects_invalid_geometry_and_budget(self):
        for key,value in [('size',[-1,1]),('location',[0,0,float('nan')]),('tile_size',.01),
                          ('roughness',2),('color',[-.1,0,0]),('script','anything')]:
            with self.subTest(key=key),self.assertRaises(DirectorError):
                validate({**self.options,key:value})

    def test_ground_contract(self):
        base=dict(rotation=[1,0,0,0,1,0,0,0,1],translation_bone='hips',translation_scale=1,target_origin=[0,0,1])
        ground=dict(mesh='person',vertex_groups=['sole'],height=0,max_correction=.1)
        validate_pose({**base,'ground_contact':ground})
        for key,value in [('vertex_groups',[]),('max_correction',5),('height',float('inf')),('mesh','')]:
            with self.subTest(key=key),self.assertRaises(DirectorError):
                validate_pose({**base,'ground_contact':{**ground,key:value}})
