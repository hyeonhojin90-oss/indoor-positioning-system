import unittest
from multi_anchor_counter import DualAnchorCounter

class DualAnchorTests(unittest.TestCase):
    def test_exit_ankle_conflict_is_optional_and_does_not_block_subsequent_boarding(self):
        d=(0,0,100,100)
        settings=dict(low=.95,high=1.05,confirm=1,geometry='doorway',outside_margin=.6)
        guarded=DualAnchorCounter(settings,exit_ankle_guard=True)
        baseline=DualAnchorCounter(settings)
        for c in (guarded,baseline):
            c.update(1,(30,0,70,90),None,d,0)
        self.assertIsNone(guarded.update(1,(30,0,70,110),(50,101),d,.04))
        self.assertEqual(baseline.update(1,(30,0,70,110),(50,101),d,.04)['direction'],'out')
        self.assertEqual(guarded.totals,{'in':0,'out':0})
        self.assertEqual(guarded.update(1,(30,0,70,90),(50,90),d,.08)['direction'],'in')
        self.assertEqual(guarded.totals,{'in':1,'out':0})

    def test_exit_guard_preserves_measured_outside_and_missing_feet(self):
        settings=dict(low=.95,high=1.05,confirm=1,geometry='doorway',outside_margin=.6);d=(0,0,100,100)
        for foot in ((50,110),None):
            c=DualAnchorCounter(settings,exit_ankle_guard=True)
            c.update(1,(30,0,70,90),None,d,0)
            self.assertEqual(c.update(1,(30,0,70,110),foot,d,.04)['direction'],'out')
        with self.assertRaises(ValueError):DualAnchorCounter(settings,exit_ankle_guard=1)
        with self.assertRaises(ValueError):DualAnchorCounter({'low':.4,'high':.6},exit_ankle_guard=True)

    def test_early_inside_foot_is_not_consumed_and_outside_return_cancels_candidate(self):
        c=DualAnchorCounter({'low':.4,'high':.6,'confirm':1},require_body_transition=True,defer_ankle=True);d=(0,0,100,100)
        c.update(1,(20,0,80,90),(50,85),d,0)
        c.update(1,(20,0,80,90),(50,30),d,.04)
        self.assertNotIn(1,c.pending)
        c.update(1,(20,0,80,50),(50,30),d,.08)
        self.assertIn(1,c.pending)
        c.update(1,(20,0,80,90),(50,85),d,.12)
        self.assertNotIn(1,c.pending)
        self.assertEqual(c.advance(1,[]),[])
        self.assertEqual(c.totals,{'in':0,'out':0})

    def test_deferred_ankle_prefers_later_body_and_loss_keeps_observation_time(self):
        c=DualAnchorCounter({'low':.4,'high':.6,'confirm':1},defer_ankle=True);d=(0,0,100,100)
        c.update(1,(20,0,80,90),(50,85),d,0)
        self.assertIsNone(c.update(1,(20,0,80,50),(50,30),d,.04))
        for i in range(1,21):
            self.assertEqual(c.advance(i*.1,[1]),[])
            c.update(1,(20,0,80,50),None,d,i*.1)
        self.assertEqual(c.update(1,(20,0,80,30),None,d,2.04)['anchor_evidence'],'body')
        self.assertEqual(c.advance(3,[]),[])
        c.update(2,(20,0,80,90),(50,85),d,3.1)
        c.update(2,(20,0,80,50),(50,30),d,3.14,frame=100)
        event=c.advance(4,[])[0]
        self.assertEqual(event['time_s'],3.14);self.assertEqual(event['commit_time_s'],4)
        self.assertEqual(event['observation_frame'],100)
        self.assertEqual(c.totals,{'in':2,'out':0})

    def test_deferred_ankle_return_and_door_loss_cancel_pending(self):
        c=DualAnchorCounter({'low':.4,'high':.6,'confirm':1},defer_ankle=True);d=(0,0,100,100)
        for t in (1,2):
            c.update(t,(20,0,80,90),(50,85),d,0)
            c.update(t,(20,0,80,50),(50,30),d,.04)
        c.update(1,(20,0,80,50),(50,85),d,.08)
        self.assertNotIn(1,c.pending)
        c.reset_tracks();self.assertEqual(c.advance(1,[]),[])
        self.assertEqual(c.totals,{'in':0,'out':0})

    def test_front_foot_then_body_counts_once_and_body_can_confirm_real_return(self):
        c=DualAnchorCounter({'low':.4,'high':.6,'confirm':1},1)
        door=(0,0,100,100)
        self.assertIsNone(c.update(1,(20,0,80,90),(50,85),door,0))
        self.assertEqual(c.update(1,(20,0,80,90),(50,30),door,.04)['anchor_evidence'],'measured_ankle')
        self.assertIsNone(c.update(1,(20,0,80,30),(50,30),door,.08))
        self.assertEqual(c.totals,{'in':1,'out':0})
        self.assertEqual(c.update(1,(20,0,80,90),(50,85),door,.12)['direction'],'out')
        self.assertEqual(c.update(1,(20,0,80,30),(50,30),door,.16)['direction'],'in')
        self.assertEqual(c.totals,{'in':2,'out':1})

    def test_unknown_ankle_body_still_counts_and_door_reset_removes_dedup_history(self):
        c=DualAnchorCounter({'low':.4,'high':.6,'confirm':1},1);d=(0,0,100,100)
        for offset in (0,1):
            c.reset_tracks()
            c.update(1,(20,0,80,90),None,d,offset)
            self.assertEqual(c.update(1,(20,0,80,30),None,d,offset+.04)['direction'],'in')
        self.assertEqual(c.totals,{'in':2,'out':0})

    def test_same_frame_conflict_is_not_fabricated_count(self):
        c=DualAnchorCounter({'low':.4,'high':.6,'confirm':1},1);d=(0,0,100,100)
        c.update(1,(20,0,80,90),(50,30),d,0)
        self.assertIsNone(c.update(1,(20,0,80,30),(50,85),d,.04))
        self.assertEqual(c.totals,{'in':0,'out':0})

    def test_early_ankle_does_not_suppress_later_body_and_transition_foot_can_board(self):
        c=DualAnchorCounter({'low':.4,'high':.6,'confirm':1},1,require_body_transition=True);d=(0,0,100,100)
        c.update(1,(20,0,80,90),(50,85),d,0)
        self.assertIsNone(c.update(1,(20,0,80,90),(50,30),d,.04))
        self.assertEqual(c.update(1,(20,0,80,30),None,d,.08)['anchor_evidence'],'body')
        c.update(2,(20,0,80,90),(50,85),d,.1)
        self.assertEqual(c.update(2,(20,0,80,50),(50,30),d,.14)['anchor_evidence'],'measured_ankle')
        self.assertEqual(c.totals,{'in':2,'out':0})

if __name__=='__main__':unittest.main()
