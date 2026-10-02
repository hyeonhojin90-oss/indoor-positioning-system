import unittest
from temporal_nested_bridge import TemporalNestedBridge

class TemporalBridgeTests(unittest.TestCase):
    def test_short_gap_partial_requires_multiple_observations(self):
        b=TemporalNestedBridge();full=(0,0,100,400);part=(30,0,70,100)
        b.update([(1,full)],0)
        self.assertEqual(b.update([(2,part)],.1),[(2,part)])
        self.assertEqual(b.update([(2,part)],.2),[(2,part)])
        self.assertEqual(b.update([(2,part)],.3),[(1,part)])
    def test_expired_or_ambiguous_parent_never_links(self):
        full=(0,0,100,400);part=(30,0,70,100)
        for gap,parents in [(1,[(1,full)]),(.1,[(1,full),(3,full)])]:
            b=TemporalNestedBridge();b.update(parents,0)
            for dt in [0,.1,.2]:self.assertEqual(b.update([(2,part)],gap+dt),[(2,part)])
        self.assertEqual(b.aliases,{})
    def test_same_parent_cannot_absorb_competing_people(self):
        b=TemporalNestedBridge();b.update([(1,(0,0,100,400))],0)
        for now in [.1,.2,.3]:b.update([(2,(20,0,60,100)),(3,(35,0,75,100))],now)
        self.assertEqual(b.aliases,{})
    def test_reappearing_distinct_parent_revokes_alias(self):
        b=TemporalNestedBridge();b.update([(1,(0,0,100,400))],0)
        for now in [.1,.2,.3]:b.update([(2,(30,0,70,100))],now)
        self.assertEqual(b.update([(1,(200,0,300,400)),(2,(30,0,70,100))],.4),[(1,(200,0,300,400)),(2,(30,0,70,100))])
    def test_recent_child_seen_before_full_parent_disappears_can_confirm(self):
        b=TemporalNestedBridge();full=(0,0,100,400);part=(30,0,70,100)
        b.update([(1,full)],0);b.update([(1,full),(2,part)],.1)
        for now in [.2,.3,.4]:result=b.update([(2,part)],now)
        self.assertEqual(result,[(1,part)])
    def test_long_established_neighbor_is_not_reassigned(self):
        b=TemporalNestedBridge();full=(0,0,100,400);part=(30,0,70,100)
        for now in [0,.5,1]:b.update([(1,full),(2,part)],now)
        for now in [1.1,1.2,1.3]:result=b.update([(2,part)],now)
        self.assertEqual(result,[(2,part)])

if __name__=='__main__':unittest.main()
