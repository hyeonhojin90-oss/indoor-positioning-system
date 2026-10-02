import unittest
from exit_evidence_guard import ExitEvidenceGuard

class ExitEvidenceTests(unittest.TestCase):
    def make(self):return ExitEvidenceGuard(.95,1.05)
    def test_initial_truncated_box_has_no_measured_inside_proof(self):
        g=self.make();d=(0,0,100,100)
        self.assertTrue(g.observe(1,None,d,0)['allow_exit'])
        r=g.observe(1,(50,101),d,.04)
        self.assertFalse(r['allow_exit'])
        self.assertEqual(r['reason'],'unproven_inside_and_foot_not_outside')

    def test_actual_inside_history_and_outside_motion_remain_eligible(self):
        g=self.make();d=(0,0,100,100)
        g.observe(1,(50,80),d,0);g.observe(1,(50,82),d,.04)
        self.assertTrue(g.observe(1,(50,99),d,.08)['allow_exit'])
        self.assertTrue(g.observe(2,(50,110),d,.08)['allow_exit'])
        self.assertTrue(g.observe(3,(120,80),d,.08)['allow_exit'])

    def test_missing_feet_reset_votes_and_gap_or_door_reset_clear_history(self):
        g=self.make();d=(0,0,100,100)
        g.observe(1,(50,80),d,0);g.observe(1,None,d,.04)
        self.assertFalse(g.observe(1,(50,99),d,.08)['allow_exit'])
        g.observe(2,(50,80),d,0);g.observe(2,(50,82),d,.04)
        self.assertFalse(g.observe(2,(50,99),d,1)['allow_exit'])
        g.observe(3,(50,80),d,1);g.observe(3,(50,82),d,1.04)
        g.reset();self.assertFalse(g.observe(3,(50,99),d,1.08)['allow_exit'])

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):ExitEvidenceGuard(.95,1.05,confirm=True)
        with self.assertRaises(ValueError):self.make().observe(1,(float('nan'),0),(0,0,100,100),0)
    def test_strict_unknown_requires_prior_actual_inside_foot(self):
        g=ExitEvidenceGuard(.95,1.05,unknown_requires_inside=True);d=(0,0,100,100)
        self.assertFalse(g.observe(1,None,d,0)['allow_exit'])
        g.observe(1,(50,80),d,.04);g.observe(1,(50,82),d,.08)
        self.assertTrue(g.observe(1,None,d,.12)['allow_exit'])
        self.assertFalse(g.observe(1,None,d,1)['allow_exit'])
    def test_strict_unknown_cannot_be_enabled_without_guard(self):
        from multi_anchor_counter import DualAnchorCounter
        with self.assertRaises(ValueError):DualAnchorCounter({'low':.95,'high':1.05},exit_unknown_requires_inside=True)

if __name__=='__main__':unittest.main()
