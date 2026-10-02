import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import cv2
import numpy as np
from passage_review import ReviewSession
from serve_passage_review import serve


class PassageReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);source=self.root/'source.avi'
        writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'MJPG'),10,(96,64))
        self.assertTrue(writer.isOpened())
        for i in range(6):writer.write(np.full((64,96,3),i*30,np.uint8))
        writer.release();self.session=ReviewSession(source,self.root/'review')

    def payload(self):
        return dict(source_sha256=self.session.manifest['source_sha256'],reviewer='test',reviewer_kind='assistant',
            events=[dict(person='test-person',direction='in',start_frame=1,end_frame=3)])

    def test_actual_requested_frame_and_exact_source_frame_times(self):
        jpeg=self.session.frame(4);image=cv2.imdecode(np.frombuffer(jpeg,np.uint8),cv2.IMREAD_COLOR)
        self.assertAlmostEqual(float(image.mean()),120,delta=3)
        self.assertEqual(self.session.manifest['frames'],6)
        self.session.save(self.payload())
        event=json.loads((self.session.output/'windows-001.jsonl').read_text())
        metadata=json.loads((self.session.output/'review-001.json').read_text())
        self.assertEqual((event['start_s'],event['end_s']),(.1,.3))
        self.assertEqual(metadata['actual_requested_frames'],[4])
        self.assertEqual(metadata['served_frame_proof']['4']['jpeg_sha256'],hashlib.sha256(jpeg).hexdigest())
        self.assertFalse(metadata['human_reviewed'])
        self.assertFalse(metadata['whole_ground_truth_complete'])

    def test_new_save_preserves_previous_truth_and_cannot_claim_human_review(self):
        self.session.save(self.payload());before=(self.session.output/'windows-001.jsonl').read_bytes()
        payload=self.payload();payload['events'][0]['end_frame']=4
        self.session.save(payload)
        self.assertEqual((self.session.output/'windows-001.jsonl').read_bytes(),before)
        self.assertTrue((self.session.output/'windows-002.jsonl').is_file())

    def test_invalid_intervals_and_duplicate_truth_are_rejected_before_write(self):
        for start,end in [(True,3),(-1,3),(4,3),(1,6)]:
            payload=self.payload();payload['events'][0].update(start_frame=start,end_frame=end)
            with self.assertRaises(ValueError):self.session.save(payload)
        payload=self.payload();payload['events']*=2
        with self.assertRaises(ValueError):self.session.save(payload)
        self.assertEqual(list(self.session.output.glob('windows-*.jsonl')),[])

    def test_changed_source_is_not_bound_to_old_annotations(self):
        self.session.source.write_bytes(self.session.source.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.session.save(self.payload())
        self.assertFalse((self.session.output/'windows-001.jsonl').exists())
        with self.assertRaisesRegex(ValueError,'changed'):self.session.frame(4)

    def test_unavailable_or_wrong_seek_position_uses_sequential_frame(self):
        actual=cv2.VideoCapture
        for seek_supported in (False,True):
            first=Mock();first.isOpened.return_value=True;first.set.return_value=seek_supported
            first.get.return_value=0;first.read.return_value=(True,np.zeros((64,96,3),np.uint8))
            with self.subTest(seek_supported=seek_supported),patch('cv2.VideoCapture',side_effect=[first,actual(str(self.session.source))]):
                data=self.session.frame(4)
            image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
            self.assertAlmostEqual(float(image.mean()),120,delta=3)
            self.assertEqual(self.session.served[4]['decoder_mode'],'counted_sequential_decode')

    def test_local_http_rejects_external_origin_and_non_json_write(self):
        server=serve(self.session,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
            connection.request('GET','/manifest');response=connection.getresponse()
            self.assertEqual(response.status,200);self.assertEqual(json.loads(response.read())['frames'],6)
            for headers,expected in [({'Content-Type':'application/json','Origin':'https://external.invalid'},403),
                                     ({'Content-Type':'text/plain'},415)]:
                connection.request('POST','/save',json.dumps(self.payload()),headers=headers)
                response=connection.getresponse();response.read();self.assertEqual(response.status,expected)
            connection.request('GET','/frame?index=99');response=connection.getresponse()
            response.read();self.assertEqual(response.status,400);connection.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
