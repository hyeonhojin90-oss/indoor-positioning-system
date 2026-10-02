"""Association must distinguish high/low subset indices in installed tracker."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
from measured_detection_boxes import MeasuredDetectionBoxes

def tensor(values):
    x=Mock();x.int.return_value=x;x.cpu.return_value=x;x.tolist.return_value=values;return x

class MeasuredBoxesTests(unittest.TestCase):
    def setUp(self):
        self.model=NS(predictor=None,add_callback=Mock())
        with patch('measured_detection_boxes.importlib.metadata.version',return_value='8.3.228'):self.a=MeasuredDetectionBoxes(self.model)
        self.a.snapshots=[dict(box=[0,0,10,10],score=.9,cls=0),dict(box=[20,0,30,10],score=.2,cls=0),dict(box=[40,0,50,10],score=.8,cls=0)]
    def test_same_local_index_high_and_low_map_to_different_detections(self):
        tracks=[NS(track_id=7,idx=0,score=.9,is_activated=True,frame_id=2),NS(track_id=8,idx=0,score=.2,is_activated=True,frame_id=2)]
        tracker=NS(tracked_stracks=tracks,frame_id=2,args=NS(track_high_thresh=.25,track_low_thresh=.1))
        result=NS(boxes=NS(id=tensor([7,8]),cls=tensor([0,0]),conf=tensor([.9,.2])))
        boxes,proof=self.a.recover(result,tracker)
        self.assertEqual(boxes,[self.a.snapshots[0]['box'],self.a.snapshots[1]['box']])
        self.assertEqual([p['association_band'] for p in proof],['high','low'])
    def test_score_mismatch_aborts_instead_of_guessing(self):
        tracker=NS(tracked_stracks=[NS(track_id=7,idx=0,score=.8,is_activated=True,frame_id=2)],frame_id=2,args=NS(track_high_thresh=.25,track_low_thresh=.1))
        result=NS(boxes=NS(id=tensor([7]),cls=tensor([0]),conf=tensor([.8])))
        with self.assertRaises(ValueError):self.a.recover(result,tracker)
    def test_unsupported_version_rejected(self):
        with patch('measured_detection_boxes.importlib.metadata.version',return_value='future'):
            with self.assertRaises(ValueError):MeasuredDetectionBoxes(self.model)
    def test_lost_track_is_not_a_current_measurement(self):
        tracker=NS(tracked_stracks=[NS(track_id=7,idx=0,score=.9,is_activated=True,frame_id=1)],frame_id=2,args=NS(track_high_thresh=.25,track_low_thresh=.1))
        result=NS(boxes=NS(id=tensor([7]),cls=tensor([0]),conf=tensor([.9])))
        with self.assertRaises(ValueError):self.a.recover(result,tracker)

if __name__=='__main__':unittest.main()
