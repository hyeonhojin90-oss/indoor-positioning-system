import unittest
from door_acquisition_fallback import fallback_due,validate

class AcquisitionFallbackTests(unittest.TestCase):
    def test_existing_lock_and_primary_candidate_protect_geometry(self):
        self.assertFalse(fallback_due([0,0,10,30],None,False,'strong_detection'))
        self.assertFalse(fallback_due(None,[0,0,10,30],False,'strong_detection'))
    def test_weak_bus_and_already_active_backend_cannot_trigger_extra_model(self):
        self.assertFalse(fallback_due(None,None,False,'visual_continuity'))
        self.assertFalse(fallback_due(None,None,True,'strong_detection'))
        self.assertTrue(fallback_due(None,None,False,'strong_detection'))
    def test_invalid_size_or_unknown_configuration_rejected(self):
        for config in [dict(model='x',imgsz=True),dict(model='x',imgsz=417),dict(model=''),dict(model='x',unknown=True)]:
            with self.assertRaises(ValueError):validate(config)

if __name__=='__main__':unittest.main()
