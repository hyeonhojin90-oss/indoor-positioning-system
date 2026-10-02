import unittest
from bus_gate import BusPresenceGate
from counter import DoorLock


class BusGateTests(unittest.TestCase):
    def test_associated_weak_bus_never_acquires_or_renews_strong_deadline(self):
        gate=BusPresenceGate(min_conf=.4,min_area=.1,grace_s=.1,associated_conf=.15,max_associated_span_s=.5)
        box=[[0,0,50,50]]
        self.assertFalse(gate.observe(box,[5],[.2],100,100,0))
        self.assertTrue(gate.observe(box,[5],[.8],100,100,.1))
        self.assertTrue(gate.observe(box,[5],[.2],100,100,.3,continuity_valid=True))
        self.assertEqual(gate.observation_kind,'associated_detection')
        self.assertTrue(gate.observe(box,[5],[.2],100,100,.5,continuity_valid=True))
        self.assertFalse(gate.observe(box,[5],[.2],100,100,.8))

    def test_associated_bus_requires_anchor_overlap(self):
        gate=BusPresenceGate(min_conf=.4,min_area=.1,grace_s=.1,associated_conf=.15)
        gate.observe([[0,0,50,50]],[5],[.8],100,100,0)
        self.assertFalse(gate.observe([[50,50,100,100]],[5],[.2],100,100,.2))

    def test_weak_bus_cannot_reacquire_after_unobserved_gap(self):
        gate=BusPresenceGate(min_conf=.4,min_area=.1,grace_s=.1,associated_conf=.15)
        box=[[0,0,50,50]]
        gate.observe(box,[5],[.8],100,100,0)
        self.assertFalse(gate.observe(box,[5],[.2],100,100,.5))

    def test_visible_bus_then_grace_then_absence(self):
        gate = BusPresenceGate(min_conf=.4,min_area=.1,grace_s=.5)
        box = [[0,0,50,50]]
        self.assertFalse(gate.observe([],[],[],100,100,0))
        self.assertTrue(gate.observe(box,[5],[.8],100,100,.1))
        self.assertTrue(gate.observe([],[],[],100,100,.5))
        self.assertFalse(gate.observe([],[],[],100,100,.7))

    def test_small_or_weak_bus_does_not_enable(self):
        gate = BusPresenceGate(min_conf=.4,min_area=.1)
        self.assertFalse(gate.observe([[0,0,20,20]],[5],[.8],100,100,0))
        self.assertFalse(gate.observe([[0,0,50,50]],[5],[.3],100,100,.1))
        self.assertFalse(gate.observe([[0,0,50,50]],[0],[.8],100,100,.2))

    def test_rejects_bus_front_sized_false_door(self):
        gate = BusPresenceGate(min_area=.01,max_door_bus_width_ratio=.65)
        self.assertTrue(gate.observe([[0,0,100,100]],[5],[.9],120,120,0))
        self.assertTrue(gate.accept_door([55,10,95,90]))
        self.assertFalse(gate.accept_door([10,10,90,90]))
        self.assertFalse(gate.accept_door([101,10,111,90]))
        self.assertFalse(gate.observe([],[],[],120,120,1))
        self.assertFalse(gate.accept_door([55,10,95,90]))

    def test_lost_bus_clears_door_lock(self):
        door = DoorLock(stable=2)
        door.observe((0,0,10,10),0)
        door.observe((0,0,10,10),.1)
        generation = door.generation
        door.reset()
        self.assertIsNone(door.box)
        self.assertEqual(door.generation,generation+1)
        door.reset()
        self.assertEqual(door.generation,generation+1)


if __name__ == '__main__':
    unittest.main()
