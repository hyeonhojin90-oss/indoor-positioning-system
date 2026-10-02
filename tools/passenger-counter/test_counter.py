import unittest
from counter import DoorLock, PassageCounter, plausible_door


class CountingTests(unittest.TestCase):
    def test_lateral_clipped_foot_needs_horizontal_penetration(self):
        for mirror in (False,True):
            c=PassageCounter(geometry='doorway',low=.95,high=1.1,outside_margin=.6,lateral_inset=.25)
            points=[(1.3,.97),(1.3,.97),(.85,.85),(.84,.85),(.82,.85)]
            transform=lambda p: (1-p[0],p[1]) if mirror else p
            for i,p in enumerate(points):
                self.assertIsNone(c.update(1,transform(p),(0,0,1,1),i*.1))
            self.assertIsNone(c.update(1,transform((.7,.85)),(0,0,1,1),.5))
            self.assertEqual(c.update(1,transform((.69,.85)),(0,0,1,1),.6)['direction'],'in')

    def test_lateral_guard_preserves_bottom_entry(self):
        c=PassageCounter(geometry='doorway',low=.95,high=1.1,outside_margin=.6,lateral_inset=.25)
        for i,p in enumerate([(.85,1.2),(.85,1.2),(.85,.9),(.85,.9)]):
            c.update(1,p,(0,0,1,1),i*.1)
        self.assertEqual(c.totals,{'in':1,'out':0})

    def test_invalid_lateral_guard_rejected(self):
        for value in (-.1,.5):
            with self.assertRaises(ValueError):
                PassageCounter(geometry='doorway',lateral_inset=value)
        with self.assertRaises(ValueError):
            PassageCounter(lateral_inset=.25)

    def test_lateral_doorway_entry_and_exit(self):
        c=PassageCounter(geometry='doorway',low=.95,high=1.1,outside_margin=.6)
        points=[(1.4,.97),(1.3,.97),(1,.96),(.85,.9),(.8,.9),(.9,.95),(1.2,.97),(1.3,.97)]
        events=[c.update(1,p,(0,0,1,1),i*.1) for i,p in enumerate(points)]
        self.assertEqual([e['direction'] for e in events if e],['in','out'])

    def test_lateral_waiting_and_turnback_do_not_count(self):
        c=PassageCounter(geometry='doorway',low=.95,high=1.1,outside_margin=.6)
        for i,x in enumerate([1.3,1.3,1.05,.98,1.1,1.3,1.3]):
            c.update(1,(x,1.0),(0,0,1,1),i*.1)
        self.assertEqual(c.totals,{'in':0,'out':0})

    def test_lateral_loss_and_far_outside_cannot_bridge(self):
        c=PassageCounter(geometry='doorway',low=.95,high=1.1,outside_margin=.6,confirm=1)
        c.update(1,(1.3,.97),(0,0,1,1),0)
        self.assertIsNone(c.update(1,(.8,.9),(0,0,1,1),2))
        c.update(2,(1.9,.97),(0,0,1,1),2)
        self.assertIsNone(c.update(2,(.8,.9),(0,0,1,1),2.1))

    def test_expired_lock_cannot_authorize_weak_revalidation(self):
        d=DoorLock(stable=1,ttl=1)
        d.observe((0,0,1,1),0)
        self.assertIsNotNone(d.valid_box(.5))
        self.assertIsNone(d.valid_box(1.01))
        self.assertIsNone(d.valid_box(-.1))
    def test_door_shape_rejects_wide_bus_box(self):
        self.assertTrue(plausible_door((10,10,40,90),100,100,.6,1))
        self.assertFalse(plausible_door((0,20,95,55),100,100,.6,1))

    def test_approach_zone_outside_door_can_count(self):
        c = PassageCounter(axis='y',entry='negative',low=.95,high=1.1,
                           outside_margin=.2,confirm=2)
        points = [1.17,1.16,1.13,1.05,1.0,.97,.94,.93]
        events = [c.update(1,(.5,y),(0,0,1,1),i*.1) for i,y in enumerate(points)]
        self.assertEqual([e['direction'] for e in events if e], ['in'])

    def test_far_outside_or_wrong_side_cannot_start_count(self):
        c = PassageCounter(axis='y',entry='negative',low=.95,high=1.1,
                           outside_margin=.2,confirm=2)
        c.update(1,(.5,1.5),(0,0,1,1),0)
        c.update(1,(.5,.93),(0,0,1,1),.1)
        self.assertEqual(c.totals['in'],0)
        c.update(2,(1.2,1.15),(0,0,1,1),0)
        c.update(2,(.5,.93),(0,0,1,1),.1)
        self.assertEqual(c.totals['in'],0)

    def test_approach_zone_turn_back_has_no_count(self):
        c = PassageCounter(axis='y',entry='negative',low=.95,high=1.1,
                           outside_margin=.2,confirm=2)
        for i, y in enumerate([1.17,1.16,1.05,1.03,1.12,1.15]):
            c.update(1,(.5,y),(0,0,1,1),i*.1)
        self.assertEqual(c.totals, {'in':0,'out':0})

    def test_stale_candidate_requires_new_observations(self):
        d = DoorLock(stable=2, ttl=1)
        d.observe((0,0,1,1), 0)
        self.assertIsNone(d.observe((0,0,1,1), 2))
        self.assertIsNotNone(d.observe((0,0,1,1), 2.1))

    def test_stale_detection_cannot_revive_old_lock(self):
        d=DoorLock(stable=2,ttl=1)
        d.observe((0,0,1,1),0)
        d.observe((0,0,1,1),.1)
        self.assertIsNone(d.observe((0,0,1,1),2))
        self.assertIsNotNone(d.observe((0,0,1,1),2.1))

    def count_path(self, ys, **kwargs):
        c = PassageCounter(**kwargs)
        events = [c.update(1,(.5,y),(0,0,1,1),i*.1) for i,y in enumerate(ys)]
        return c, [e for e in events if e]

    def test_enter_dwell_reverse(self):
        c, e = self.count_path([.9,.9,.5,.1,.1,.1,.1,.5,.9,.9])
        self.assertEqual(c.totals, {'in':1,'out':1})

    def test_turn_back(self):
        c, _ = self.count_path([.9,.9,.5,.45,.5,.9,.9])
        self.assertEqual(c.totals, {'in':0,'out':0})

    def test_side_exit_does_not_connect(self):
        c, _ = self.count_path([.9,.9,1.1,.1,.1])
        self.assertEqual(c.totals['in'],0)

    def test_long_loss_new_id(self):
        c = PassageCounter(confirm=1)
        c.update(1,(.5,.9),(0,0,1,1),0)
        self.assertIsNone(c.update(1,(.5,.1),(0,0,1,1),2))
        self.assertIsNone(c.update(2,(.5,.9),(0,0,1,1),2.1))

    def test_horizontal(self):
        c = PassageCounter(axis='x',entry='positive',confirm=1)
        c.update(1,(.1,.5),(0,0,1,1),0)
        self.assertEqual(c.update(1,(.9,.5),(0,0,1,1),.1)['direction'],'in')

    def test_door_stability_movement_loss(self):
        d = DoorLock(stable=2)
        self.assertIsNone(d.observe((0,0,1,1),0))
        self.assertIsNotNone(d.observe((0,0,1,1),.1))
        self.assertIsNone(d.observe((2,0,3,1),.2))
        self.assertIsNotNone(d.observe((2,0,3,1),.3))
        self.assertIsNone(d.observe(None,2))


if __name__ == '__main__':
    unittest.main()
