import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from audit_observed_trace import audit


class ObservedTraceAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'run';self.run.mkdir();self.code=self.root/'code';self.code.mkdir()
        names=['run.py','counter.py','person_anchor.py','multi_anchor_counter.py','source_timing.py']
        hashes={}
        for name in names:
            shutil.copy2(name,self.code/name);hashes[name]=hashlib.sha256((self.code/name).read_bytes()).hexdigest()
        self.rows=[dict(frame=i,time_s=t,door=[0,0,100,100],door_generation=1,ids=[1],
            boxes=[[30,0,70,bottom]],points=[[50,bottom]]) for i,(t,bottom) in enumerate([(.01,80),(.13,20)])]
        self.event=dict(frame=1,time_s=.13,track_id=1,direction='in',door_generation=1)
        self.summary=dict(frames=2,counts=dict(in_=1),config=dict(counting=dict(low=.4,high=.6,confirm=1)),implementation_sha256=hashes)
        self.summary['counts']={'in':1,'out':0};self.save()

    def save(self):
        (self.run/'summary.json').write_text(json.dumps(self.summary))
        (self.run/'tracks.jsonl').write_text('\n'.join(json.dumps(row) for row in self.rows)+'\n')
        (self.run/'events.jsonl').write_text(json.dumps(self.event)+'\n')

    def test_consistent_observations_are_not_complete_camera_or_hardware_proof(self):
        report=audit(self.run,self.code)
        self.assertTrue(report['observed_trace_verified'])
        self.assertFalse(report['original_source_complete_verified'])
        self.assertFalse(report['original_source_hash_verified'])
        self.assertFalse(report['jetson_validated'])

    def test_missing_frame_and_clock_regression_cannot_be_verified(self):
        self.rows[1]['frame']=2;self.save()
        with self.assertRaisesRegex(ValueError,'incomplete'):audit(self.run,self.code)
        self.rows[1]['frame']=1;self.rows[1]['time_s']=0;self.save()
        with self.assertRaisesRegex(ValueError,'clock'):audit(self.run,self.code)

    def test_correct_total_with_wrong_event_time_or_door_cannot_pass(self):
        self.event['time_s']=.2;self.save()
        with self.assertRaisesRegex(ValueError,'time differs'):audit(self.run,self.code)
        self.event['time_s']=.13;self.event['door_generation']=2;self.save()
        with self.assertRaisesRegex(ValueError,'different'):audit(self.run,self.code)

    def test_changed_runtime_code_invalidates_live_replay_proof(self):
        (self.code/'counter.py').write_bytes((self.code/'counter.py').read_bytes()+b'\n# changed\n')
        report=audit(self.run,self.code)
        self.assertFalse(report['observed_trace_verified'])
        self.assertEqual(report['implementation_drift_since_start'],['counter.py'])


if __name__=='__main__':unittest.main()
