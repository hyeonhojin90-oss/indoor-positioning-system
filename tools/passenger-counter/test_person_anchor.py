import unittest
from person_anchor import ankle_point,measured_points,row_points
from replay_counter import replay_rows

class FootAnchorTests(unittest.TestCase):
    def test_leading_visible_foot_is_measured_and_missing_or_bad_points_are_unknown(self):
        points=[[0,0,0] for _ in range(17)]
        points[15]=[40,85,.9];points[16]=[60,95,.8]
        self.assertEqual(ankle_point([0,0,100,100],points),(40,85))
        self.assertEqual(ankle_point([0,0,100,100],points,foot_choice='trailing'),(60,95))
        points[15][2]=.1
        self.assertIsNone(ankle_point([0,0,100,100],points))
        self.assertEqual(ankle_point([0,0,100,100],points,min_visible=1),(60,95))
        points[16]=[60,20,.9]
        self.assertIsNone(ankle_point([0,0,100,100],points,min_visible=1))

    def test_bridge_uses_pose_of_selected_raw_box_not_alias_number(self):
        b=[0,0,100,100];k=[[0,0,0] for _ in range(17)];k[15]=[40,85,.9];k[16]=[60,95,.9]
        cfg={'person_anchor_kind':'pose_ankle'}
        self.assertEqual(measured_points([(1,b)],[(2,b)],{2:k},cfg),[(40,85)])
        self.assertEqual(measured_points([(1,b)],[(2,b),(3,b)],{2:k},cfg),[None])

    def test_unknown_pose_is_not_box_fallback_and_nonfinite_log_is_rejected(self):
        cfg={'person_anchor_kind':'pose_ankle','counting':{'confirm':1}}
        row={'frame':0,'time_s':0,'ids':[1],'boxes':[[0,0,100,100]],'door':[0,0,100,100],'door_generation':1,'points':[None]}
        self.assertEqual(replay_rows([row],cfg)['counts'],{'in':0,'out':0})
        with self.assertRaisesRegex(ValueError,'requires measured'):
            row_points({k:v for k,v in row.items() if k!='points'},cfg)
        with self.assertRaisesRegex(ValueError,'Invalid measured'):
            row_points(dict(row,points=[[float('nan'),80]]),cfg)

if __name__=='__main__':unittest.main()
