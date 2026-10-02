import unittest
from moving_door_lock import MovingDoorLock,motion_compatible
class MovingDoorTests(unittest.TestCase):
 def test_short_observed_translation_preserves_generation_and_updates_coordinates(self):
  lock=MovingDoorLock(stable=2,ttl=.3);lock.observe((0,0,100,400),0);lock.observe((2,0,102,400),.03);g=lock.generation
  self.assertEqual(lock.observe((35,0,135,400),.06),(35,0,135,400));self.assertEqual(lock.generation,g)
 def test_large_displacement_wrong_scale_or_long_gap_never_follows(self):
  for box,dt in [((200,0,300,400),.1),((0,0,100,150),.1),((20,0,120,400),.5)]:
   self.assertFalse(motion_compatible((0,0,100,400),box,dt))
 def test_missing_observations_do_not_refresh_time_or_synthesize_movement(self):
  lock=MovingDoorLock(stable=1,ttl=.3);lock.observe((0,0,100,400),0);lock.observe(None,.1)
  self.assertEqual(lock.last_seen,0);self.assertEqual(lock.follow_audit,[]);self.assertIsNone(lock.observe(None,.31))
 def test_long_grace_is_explicitly_rejected(self):
  with self.assertRaises(ValueError):MovingDoorLock(ttl=1.5)
if __name__=='__main__':unittest.main()
