import json
from pathlib import Path
import tempfile
import unittest
from evaluate_review_snapshot import digest,evaluate_snapshot


class ReviewSnapshotEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'run';self.run.mkdir()
        self.source=self.root/'synthetic-fixture.bin';self.source.write_bytes(b'unit fixture only, no camera')
        self.windows=self.root/'windows-001.jsonl';self.meta=self.root/'review-001.json'
        self.truth=dict(person='passenger-A',direction='in',start_frame=1,end_frame=3,start_s=.1,end_s=.3)
        self.event=dict(frame=2,track_id=5,direction='in',time_s=.2)
        self.summary=dict(source=str(self.source),source_sha256=digest(self.source),frames=5,source_fps=10.,
                          source_timing=dict(source_kind='file'),counts={'in':1,'out':0})
        self.receipt=dict(phase='process_finished',process_returncode=0,full_run_verified=True)
        self.audit=dict(complete_source=True,replay_parity=True,implementation_drift_since_start=[],
                        frames=5,counts=self.summary['counts'],events=[self.event])
        self.save()

    def save(self):
        self.windows.write_text(json.dumps(self.truth)+'\n')
        metadata=dict(source_sha256=digest(self.source),windows_file=self.windows.name,
                      windows_sha256=digest(self.windows),all_source_frames_decoded=True,frames=5,
                      fps=10.,events=1,reviewer_kind='assistant')
        self.meta.write_text(json.dumps(metadata))
        (self.run/'summary.json').write_text(json.dumps(self.summary))
        (self.run/'events.jsonl').write_text(json.dumps(self.event)+'\n')
        (self.run/'completion-audit.json').write_text(json.dumps(self.audit))
        self.run.with_name('run.process.json').write_text(json.dumps(self.receipt))

    def test_source_bound_subset_is_not_independent_accuracy_or_full_truth(self):
        result=evaluate_snapshot(self.run,self.meta)
        self.assertTrue(result['source_and_window_binding_verified'])
        self.assertEqual(result['matched_reviewed_events'],1)
        self.assertTrue(result['temporal_matching_only'])
        self.assertFalse(result['whole_ground_truth_complete'])
        self.assertIsNone(result['precision'])
        self.assertFalse(result['independent_accuracy_validated'])

    def test_modified_truth_or_video_cannot_use_original_binding(self):
        self.windows.write_text(self.windows.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'windows hash'):evaluate_snapshot(self.run,self.meta)
        self.save();self.source.write_bytes(b'different source')
        with self.assertRaisesRegex(ValueError,'source.*differ'):evaluate_snapshot(self.run,self.meta)

    def test_wrong_passenger_does_not_match_even_at_identical_time(self):
        identity=self.root/'identity.jsonl'
        identity.write_text(json.dumps(dict(frame=2,track_id=5,direction='in',person='passenger-A',status='uncertain'))+'\n')
        result=evaluate_snapshot(self.run,self.meta,identity)
        self.assertEqual(result['matched_reviewed_events'],0)
        self.assertFalse(result['temporal_matching_only'])

    def test_event_changed_after_completion_receipt_is_rejected(self):
        self.event=dict(self.event,time_s=.25)
        (self.run/'events.jsonl').write_text(json.dumps(self.event)+'\n')
        with self.assertRaisesRegex(ValueError,'captured completion'):evaluate_snapshot(self.run,self.meta)

    def test_partial_or_failed_execution_cannot_claim_full_file_evaluation(self):
        self.receipt['full_run_verified']=False;self.save()
        with self.assertRaisesRegex(ValueError,'process receipt'):evaluate_snapshot(self.run,self.meta)

    def test_review_timestamp_cannot_be_widened_without_matching_original_frames(self):
        self.truth['end_s']=.4;self.save()
        with self.assertRaisesRegex(ValueError,'frame/time'):evaluate_snapshot(self.run,self.meta)


if __name__=='__main__':unittest.main()
