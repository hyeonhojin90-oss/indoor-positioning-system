import tempfile
import unittest
from pathlib import Path
from tracking_profile import resolve_tracker


class TrackerProfileTests(unittest.TestCase):
    def test_reid_experiment_uses_local_detector_features(self):
        with tempfile.TemporaryDirectory() as d:
            p=resolve_tracker('botsort.yaml',{'with_reid':True,'gmc_method':'none'},d)
            from ultralytics.utils import YAML
            cfg=YAML.load(p)
            self.assertEqual(cfg['model'],'auto')
            self.assertTrue(cfg['with_reid'])
            self.assertEqual(cfg['tracker_type'],'botsort')
    def test_default_does_not_create_override(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(resolve_tracker('bytetrack.yaml',None,d),'bytetrack.yaml')
            self.assertEqual(list(Path(d).iterdir()),[])

    def test_bad_profiles_are_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            for options in ({'unknown':1},{'track_low_thresh':.5},
                            {'track_high_thresh':float('nan')},{'track_buffer':True},
                            {'fuse_score':1}):
                with self.assertRaises(ValueError):
                    resolve_tracker('bytetrack.yaml',options,d)
            with self.assertRaises(ValueError):
                resolve_tracker('botsort.yaml',{},d)
            self.assertEqual(list(Path(d).iterdir()),[])
