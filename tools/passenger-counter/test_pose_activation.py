import unittest
from pose_activation import pose_due

class PoseActivationTests(unittest.TestCase):
    def test_gate_uses_current_door_and_approach_not_stale_or_inside_people(self):
        d=(0,0,100,100);opts={'low':.9,'high':1.2,'margin':.1}
        self.assertFalse(pose_due(None,[[20,0,80,110]],opts))
        self.assertTrue(pose_due(d,[[20,0,80,110]],opts))
        self.assertFalse(pose_due(d,[[20,0,80,70],[20,0,80,150],[200,0,300,110]],opts))
        self.assertFalse(pose_due(d,[],opts))
        self.assertTrue(pose_due(None,[],None))
        with self.assertRaises(ValueError):pose_due(d,[],{'high':float('nan')})
if __name__=='__main__':unittest.main()
