import unittest
from export_verified_onnx import compare_detections,compare_pose_detections


class ExportParityTests(unittest.TestCase):
    def test_pose_boxes_alone_cannot_hide_ankle_confidence_change(self):
        a={'box':[0,0,100,100],'score':.8,'class_id':0,'keypoints':[[20,30,.8] for _ in range(17)]}
        b=dict(a,keypoints=[list(x) for x in a['keypoints']]);b['keypoints'][15][2]=.4
        self.assertFalse(compare_pose_detections([a],[b])['passed'])
        self.assertTrue(compare_pose_detections([a],[a])['passed'])
        b['keypoints'][15][2]=float('nan')
        self.assertFalse(compare_pose_detections([a],[b])['passed'])
    def test_duplicate_and_class_change_cannot_hide_as_same_count(self):
        a={'box':[0,0,100,100],'score':.8,'class_id':0}
        b={'box':[150,0,250,100],'score':.7,'class_id':0}
        self.assertFalse(compare_detections([a,b],[a,a])['passed'])
        self.assertFalse(compare_detections([a],[dict(a,class_id=5)])['passed'])

    def test_matching_ignores_order_but_bounds_numeric_error(self):
        a={'box':[0,0,100,100],'score':.8,'class_id':0}
        b={'box':[150,0,250,100],'score':.7,'class_id':0}
        self.assertTrue(compare_detections([a,b],[b,a])['passed'])
        self.assertFalse(compare_detections([a],[dict(a,score=.85)])['passed'])
