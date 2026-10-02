import unittest
from counter import DoorLock
from door_occlusion_guard import contained_shrink

class PartialDoorGuardTest(unittest.TestCase):
    def test_partial_observation_does_not_extend_expiry(self):
        lock=DoorLock(stable=1,ttl=1.5)
        box=(100,100,300,500);partial=(160,100,290,480)
        lock.observe(box,0)
        self.assertTrue(contained_shrink(lock.valid_box(1),partial))
        lock.observe(None,1)
        self.assertEqual(lock.last_seen,0)
        self.assertEqual(lock.box,box)
        self.assertIsNone(lock.valid_box(1.6))
        lock.observe(None,1.6)
        self.assertIsNone(lock.box)

    def test_positive_displacement_is_not_hidden(self):
        box=(100,100,300,500)
        self.assertFalse(contained_shrink(box,(150,100,350,500)))
        self.assertFalse(contained_shrink(box,(50,100,250,500)))
        self.assertFalse(contained_shrink(None,(160,100,290,480)))
        lock=DoorLock(stable=2)
        lock.observe(box,0);lock.observe(box,.1)
        lock.observe((150,100,350,500),.2)
        self.assertIsNone(lock.box)

if __name__=='__main__':unittest.main()
