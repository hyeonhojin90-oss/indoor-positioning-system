import unittest
from track_bridge import NestedTrackBridge


class BridgeTests(unittest.TestCase):
    def test_sparse_observations_cannot_confirm_alias(self):
        b=NestedTrackBridge();pairs=[(1,(0,0,100,400)),(2,(10,0,90,180))]
        for t in (0,2,4,6):b.update(pairs,t)
        self.assertEqual(b.aliases,{})
    def test_bottom_only_bridge_rejects_lateral_approach(self):
        b=NestedTrackBridge(bottom_approach_high=1.1);door=(0,0,100,450)
        for t in (0,.1,.2,.3):
            b.update([(1,(0,0,100,400)),(2,(10,0,90,180))],t,door)
        self.assertEqual(b.aliases,{})

    def test_bottom_only_bridge_after_approach(self):
        b=NestedTrackBridge(bottom_approach_high=1.1);door=(0,0,100,300)
        for t in (0,.1,.2):
            b.update([(1,(0,0,100,400)),(2,(10,0,90,180))],t,door)
        self.assertEqual(b.update([(2,(10,0,90,180))],.3,door),[(1,(10,0,90,180))])
    def test_nested_partial_continuity_and_full_box_preference(self):
        b=NestedTrackBridge();full=(0,0,100,400);part=(10,0,90,180)
        for t in (0,.1,.2):pairs=b.update([(1,full),(2,part)],t)
        self.assertEqual(pairs,[(1,full)])
        self.assertEqual(b.update([(2,part)],.3),[(1,part)])

    def test_ambiguous_heads_cannot_merge(self):
        b=NestedTrackBridge();pairs=[(1,(0,0,100,400)),(2,(5,0,95,400)),(3,(10,0,90,180))]
        for t in (0,.1,.2,.3):b.update(pairs,t)
        self.assertEqual(b.aliases,{})

    def test_long_loss_and_reset_drop_alias(self):
        b=NestedTrackBridge();full=(0,0,100,400);part=(10,0,90,180)
        for t in (0,.1,.2):b.update([(1,full),(2,part)],t)
        self.assertEqual(b.update([(2,part)],2),[(2,part)])
        b.reset();self.assertEqual(b.aliases,{})
