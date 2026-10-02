import unittest
from inference_schedule import inference_due


class ScheduleTests(unittest.TestCase):
    def test_slow_live_camera_checks_before_lock_expires(self):
        self.assertTrue(inference_due(2,0,15,1.,0.,True,.75))
        self.assertFalse(inference_due(2,0,15,1.,0.,False,.75))

    def test_fast_camera_and_offline_keep_frame_cadence(self):
        self.assertFalse(inference_due(2,0,15,.05,0.,True,.75))
        self.assertTrue(inference_due(15,0,15,.5,0.,False,.75))
