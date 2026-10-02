import unittest
from unittest.mock import patch
import numpy as np
from motion_head_bridge import MotionHeadBridge,HeadState,head_region

class HeadAliasTests(unittest.TestCase):
    def test_reappearing_parent_does_not_duplicate_canonical_id(self):
        b=MotionHeadBridge();box=[10,10,60,100];b.aliases={2:1}
        b.states={1:HeadState(head_region(box),np.empty((0,1,2),np.float32),0)}
        frame=np.zeros((120,120,3),np.uint8)
        with patch.object(b,'_seed',return_value=np.empty((0,1,2),np.float32)):
            out=b.update(frame,[(1,box),(2,box)],.04)
        self.assertEqual([i for i,_ in out],[1,2]);self.assertEqual(b.aliases,{})
        self.assertEqual(b.audit[0]['action'],'revoked')
    def test_two_old_aliases_reappear_without_parent(self):
        b=MotionHeadBridge();box=[10,10,60,100];b.aliases={2:1,3:1}
        b.states={1:HeadState(head_region(box),np.empty((0,1,2),np.float32),0)}
        with patch.object(b,'_seed',return_value=np.empty((0,1,2),np.float32)):
            out=b.update(np.zeros((120,120,3),np.uint8),[(2,box),(3,box)],.04)
        self.assertEqual([i for i,_ in out],[2,3]);self.assertEqual(b.aliases,{})
    def test_inactive_first_seen_records_do_not_accumulate_forever(self):
        b=MotionHeadBridge();b.first_seen={100:0}
        b.update(np.zeros((20,20,3),np.uint8),[],1)
        self.assertFalse(b.first_seen)

if __name__=='__main__':unittest.main()
