import unittest
from counter import PassageCounter


class CornerTests(unittest.TestCase):
    def test_side_entry_and_downward_alighting_share_one_track(self):
        c=PassageCounter(axis='x',entry='positive',low=.4,high=.6,confirm=2,
                         transverse_margin=.2,transverse_exit=1.1)
        box=(0,0,100,100)
        for t in (0,.1):self.assertIsNone(c.update(1,(20,105),box,t))
        self.assertIsNone(c.update(1,(80,105),box,.2))
        self.assertEqual(c.update(1,(80,105),box,.3)['direction'],'in')
        self.assertIsNone(c.update(1,(80,115),box,.4))
        self.assertEqual(c.update(1,(80,115),box,.5)['direction'],'out')
    def test_left_waiting_and_uncovered_vertical_range_do_not_count(self):
        c=PassageCounter(axis='x',entry='positive',transverse_margin=.2,transverse_exit=1.1)
        for n in range(8):self.assertIsNone(c.update(1,(20,90),(0,0,100,100),n*.1))
        self.assertIsNone(c.update(1,(80,125),(0,0,100,100),.9))
        self.assertEqual(c.totals,{'in':0,'out':0})
    def test_incompatible_orientation_rejected(self):
        with self.assertRaises(ValueError):PassageCounter(transverse_exit=1.1)
