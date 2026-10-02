import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
import cv2
import numpy as np
from record_camera_sample import record,verify,sha


class CameraSampleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'fixture.avi';self.output=self.root/'sample'
        writer=cv2.VideoWriter(str(self.source),cv2.VideoWriter_fourcc(*'MJPG'),10.,(64,48))
        self.assertTrue(writer.isOpened())
        for value in (30,70,110,150):writer.write(np.full((48,64,3),value,np.uint8))
        writer.release()

    def test_file_drill_is_verified_without_claiming_a_camera(self):
        before=sha(self.source)
        record(str(self.source),self.output,max_frames=2,recording_fps=10.,allow_file_drill=True)
        result=verify(self.output)
        self.assertEqual(result['frames'],2)
        self.assertTrue(result['file_drill'])
        self.assertFalse(result['camera_connection_validated'])
        self.assertFalse(result['camera_exposure_timestamp_verified'])
        self.assertFalse(result['boarding_accuracy_validated'])
        self.assertEqual(before,sha(self.source))

    def test_unbounded_or_implicit_file_capture_is_rejected_before_writing(self):
        with self.assertRaisesRegex(ValueError,'positive duration'):record(str(self.source),self.output,allow_file_drill=True)
        with self.assertRaisesRegex(ValueError,'explicit file'):record(str(self.source),self.output,max_frames=1)
        self.assertFalse(self.output.exists())

    def test_failed_live_open_keeps_failure_receipt_without_camera_proof(self):
        fake=Mock();fake.isOpened.return_value=False
        with patch('cv2.VideoCapture',return_value=fake),self.assertRaisesRegex(ValueError,'Cannot open'):
            record(0,self.output,max_frames=1)
        state=json.loads((self.output/'capture.json').read_text())
        self.assertEqual(state['phase'],'failed')
        self.assertFalse(state['camera_connection_validated'])
        with self.assertRaisesRegex(ValueError,'did not complete'):verify(self.output)

    def test_regressed_clock_stops_before_writing_false_timestamps(self):
        values=iter([1.,.5])
        with self.assertRaisesRegex(ValueError,'clock regressed'):
            record(str(self.source),self.output,max_frames=1,allow_file_drill=True,clock=lambda:next(values))
        state=json.loads((self.output/'capture.json').read_text())
        self.assertEqual(state['phase'],'failed')
        self.assertEqual(state['frames'],0)

    def test_changed_timestamp_artifact_is_rejected(self):
        record(str(self.source),self.output,max_frames=2,allow_file_drill=True)
        ledger=self.output/'read-times.jsonl';ledger.write_text(ledger.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):verify(self.output)

    def test_rehashed_but_invalid_clock_is_still_rejected(self):
        record(str(self.source),self.output,max_frames=2,allow_file_drill=True)
        ledger=self.output/'read-times.jsonl'
        ledger.write_text('\n'.join(json.dumps(dict(frame=i,host_read_time_s=t)) for i,t in enumerate([1.,.5]))+'\n')
        path=self.output/'capture.json';state=json.loads(path.read_text())
        state['read-times_jsonl_sha256']=sha(ledger);path.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError,'host read clock'):verify(self.output)


if __name__=='__main__':unittest.main()
