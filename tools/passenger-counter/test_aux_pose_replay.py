import unittest
from replay_aux_pose import pair_rows

class PairedLogTests(unittest.TestCase):
    def test_missing_frame_and_time_shift_cannot_masquerade_as_simultaneous_pose(self):
        row=dict(frame=0,time_s=0,raw_ids=[],raw_boxes=[],ids=[],boxes=[])
        cfg={'person_anchor_kind':'pose_dual'}
        self.assertEqual(list(pair_rows([row],[row],cfg))[0]['points'],[])
        with self.assertRaisesRegex(ValueError,'sequence'):
            list(pair_rows([dict(row,frame=1)],[dict(row,frame=1)],cfg))
        with self.assertRaisesRegex(ValueError,'simultaneous'):
            list(pair_rows([row],[dict(row,time_s=.04)],cfg))
        with self.assertRaisesRegex(ValueError,'counts'):
            list(pair_rows([row],[],cfg))
if __name__=='__main__':unittest.main()
