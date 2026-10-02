import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch,Mock
from audit_completed_run import audit

class TimestampAuditTests(unittest.TestCase):
    def test_equal_counts_and_ids_do_not_hide_tampered_event_time(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder);source=run/'source.mp4';source.write_bytes(b'bounded mock video')
            rows=[dict(frame=i,time_s=i*.04,door=[0,0,100,100],door_generation=1,ids=[1],boxes=[[20,0,80,y]]) for i,y in enumerate((90,30))]
            (run/'tracks.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            summary=dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),frames=2,counts={'in':1,'out':0},config={'counting':{'confirm':1,'low':.4,'high':.6}},events=[dict(frame=1,track_id=1,direction='in',time_s=.04)])
            (run/'summary.json').write_text(json.dumps(summary))
            cap=Mock();cap.isOpened.return_value=True;cap.get.return_value=2
            with patch('audit_completed_run.cv2.VideoCapture',return_value=cap):
                self.assertTrue(audit(run)['replay_parity'])
                summary['events'][0]['time_s']=.99;(run/'summary.json').write_text(json.dumps(summary))
                with self.assertRaisesRegex(ValueError,'disagree'):audit(run)

    def test_saved_observation_frame_and_anchor_must_match_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder);source=run/'source.mp4';source.write_bytes(b'mock')
            rows=[dict(frame=i,time_s=i*.04,door=[0,0,100,100],door_generation=1,ids=[1],boxes=[[20,0,80,y]],points=[None]) for i,y in enumerate((90,30))]
            (run/'tracks.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            event=dict(frame=1,observation_frame=1,track_id=1,direction='in',time_s=.04,anchor_evidence='body')
            summary=dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),frames=2,counts={'in':1,'out':0},config={'person_anchor_kind':'pose_dual','counting':{'confirm':1,'low':.4,'high':.6}},events=[event])
            cap=Mock();cap.isOpened.return_value=True;cap.get.return_value=2
            with patch('audit_completed_run.cv2.VideoCapture',return_value=cap):
                (run/'summary.json').write_text(json.dumps(summary))
                self.assertTrue(audit(run)['event_observation_frame_checked'])
                for key,value in [('observation_frame',0),('anchor_evidence','measured_ankle_deferred')]:
                    original=event[key];event[key]=value
                    (run/'summary.json').write_text(json.dumps(summary))
                    with self.assertRaisesRegex(ValueError,'disagree'):audit(run)
                    event[key]=original
if __name__=='__main__':unittest.main()
