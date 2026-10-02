import unittest
from counter import PassageCounter

class EntryMotionTests(unittest.TestCase):
    def counter(self):
        return PassageCounter(axis='x',entry='positive',low=.4,high=.6,confirm=2,
            transverse_margin=.2,transverse_exit=1.1,min_entry_displacement=.15)

    def test_vertical_box_bounce_is_not_entry_but_real_alighting_remains(self):
        c=self.counter();box=(0,0,100,100)
        events=[]
        for i,p in enumerate([(70,115),(70,115),(70,95),(70,95),
                               (70,115),(70,115),(72,95),(72,95)]):
            e=c.update(1,p,box,i*.04)
            if e:events.append(e['direction'])
        self.assertEqual(events,['out'])
        self.assertEqual(c.totals,{'in':0,'out':1})

    def test_observed_horizontal_entry_passes_and_long_gap_cannot_inherit_it(self):
        c=self.counter();box=(0,0,100,100)
        self.assertIsNone(c.update(1,(30,90),box,0))
        self.assertIsNone(c.update(1,(30,90),box,.04))
        self.assertIsNone(c.update(1,(70,90),box,.08))
        self.assertEqual(c.update(1,(70,90),box,.12)['direction'],'in')
        self.assertIsNone(c.update(2,(30,90),box,.13))
        self.assertIsNone(c.update(2,(30,90),box,.17))
        self.assertIsNone(c.update(2,(70,90),box,2))
        self.assertIsNone(c.update(2,(70,90),box,2.04))
        self.assertEqual(c.totals,{'in':1,'out':0})

    def test_default_still_accepts_previous_axis_behavior(self):
        c=PassageCounter(axis='x',entry='positive',low=.4,high=.6,confirm=1)
        c.update(1,(20,50),(0,0,100,100),0)
        self.assertEqual(c.update(1,(70,50),(0,0,100,100),.1)['direction'],'in')

    def test_person_appearing_from_inside_step_cannot_create_entry(self):
        c=PassageCounter(axis='x',entry='positive',low=.4,high=.6,confirm=1,
            transverse_margin=.2,transverse_exit=1.1,min_entry_displacement=.15,
            entry_approach_v_min=1.05)
        box=(0,0,100,100)
        c.update(1,(20,85),box,0)
        self.assertIsNone(c.update(1,(70,95),box,.04))
        self.assertEqual(c.update(1,(70,115),box,.08)['direction'],'out')
        c.update(2,(20,115),box,.1)
        self.assertEqual(c.update(2,(70,95),box,.14)['direction'],'in')
        self.assertEqual(c.totals,{'in':1,'out':1})

if __name__=='__main__':unittest.main()
