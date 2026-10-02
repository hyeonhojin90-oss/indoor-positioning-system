import tempfile,unittest
from pathlib import Path
from pipeline_profile import PipelineProfile,STAGES

class ProfileTests(unittest.TestCase):
    def make(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);tick=iter(range(1000))
        p=PipelineProfile(Path(folder.name)/'times.jsonl',clock=lambda:next(tick));self.addCleanup(p.close);return p
    def test_warmup_and_empty_steady_samples_not_claimed_as_real_performance(self):
        p=self.make();p.begin(0)
        for s in STAGES:p.mark(s)
        p.finish();r=p.summary();self.assertIsNone(r['steady_total']);self.assertEqual(r['frames'],1)
        self.assertFalse(r['camera_capture_to_display_latency_validated'])
    def test_missing_or_reordered_stage_and_frame_gap_rejected(self):
        p=self.make()
        with self.assertRaises(ValueError):p.begin(1)
        p.begin(0)
        with self.assertRaises(ValueError):p.mark('person')
        with self.assertRaises(ValueError):p.finish()
    def test_eof_partial_frame_not_counted(self):
        p=self.make();p.begin(0);p.close();self.assertEqual(p.summary()['frames'],0)

if __name__=='__main__':unittest.main()
