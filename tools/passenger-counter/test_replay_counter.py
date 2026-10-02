import unittest
from replay_counter import replay_rows


class ReplayTests(unittest.TestCase):
    def test_door_coordinates_can_change_within_same_generation(self):
        cfg = {'counting': {'axis':'y','entry':'negative','low':.4,'high':.6,
                            'confirm':2,'max_gap':1}}
        ys = [.9,.9,.1,.1]
        rows = [dict(frame=i,time_s=i*.1,door=[0,0,1+i*.01,1],
                     door_generation=1,ids=[7],boxes=[[.4,y-.1,.6,y]])
                for i,y in enumerate(ys)]
        result = replay_rows(rows,cfg)
        self.assertEqual(result['counts'],{'in':1,'out':0})
        self.assertFalse(result['legacy_reset_approximation'])

    def test_new_generation_clears_partial_crossing(self):
        cfg = {'counting': {'axis':'y','entry':'negative','low':.4,'high':.6,
                            'confirm':2,'max_gap':1}}
        rows = [dict(frame=i,time_s=i*.1,door=[0,0,1,1],
                     door_generation=1 if i<2 else 2,ids=[7],
                     boxes=[[.4,y-.1,.6,y]])
                for i,y in enumerate([.9,.9,.1,.1])]
        self.assertEqual(replay_rows(rows,cfg)['counts'],{'in':0,'out':0})


if __name__ == '__main__':
    unittest.main()
