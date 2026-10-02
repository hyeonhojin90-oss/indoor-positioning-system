import unittest
import numpy as np
from appearance_runtime import ObservedAppearanceRuntime,create,validate


class Features:
    def __init__(self):self.calls=0
    def extract(self,frame,boxes):
        self.calls+=1
        values=np.zeros((len(boxes),512),np.float32)
        values[:,0]=1
        return values


class AppearanceRuntimeTests(unittest.TestCase):
    def test_disabled_option_does_not_load_a_model(self):
        self.assertIsNone(create({'enabled':False,'model_root':'missing'}))
        for config in [{'enabled':1},{'enabled':True},{'unexpected':True}]:
            with self.assertRaises(ValueError):validate(config)

    def test_lost_door_never_extracts_or_retains_identity_votes(self):
        features=Features();runtime=ObservedAppearanceRuntime(features)
        pair=[(1,(0,0,100,200))]
        runtime.update(None,pair,0,(0,0,100,200),1,0)
        runtime.bridge.aliases[2]=1
        self.assertEqual(runtime.update(None,pair,.1,None,1,1),pair)
        self.assertEqual(features.calls,1)
        self.assertFalse(runtime.bridge.gallery)
        self.assertFalse(runtime.bridge.aliases)

    def test_new_door_generation_cannot_merge_with_previous_bus(self):
        features=Features();runtime=ObservedAppearanceRuntime(features)
        runtime.update(None,[(1,(0,0,100,200))],0,(0,0,100,200),1,0)
        current=[(2,(0,0,100,200))]
        for i in range(1,5):
            self.assertEqual(runtime.update(None,current,i*.1,(0,0,100,200),2,i),current)
        self.assertFalse(runtime.links)
        self.assertNotIn(1,runtime.bridge.gallery)


if __name__=='__main__':unittest.main()
