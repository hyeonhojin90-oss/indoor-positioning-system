import unittest
from compare_run_exports import same_points

class PointParityTests(unittest.TestCase):
    def test_missing_measured_ankle_or_different_person_cannot_pass_box_parity(self):
        a={'ids':[1],'points':[[20,30]]}
        self.assertTrue(same_points(a,{'ids':[1],'points':[[20.1,30.1]]}))
        self.assertFalse(same_points(a,{'ids':[1],'points':[None]}))
        self.assertFalse(same_points(a,{'ids':[2],'points':[[20,30]]}))
        self.assertFalse(same_points(a,{'ids':[1],'points':[[float('nan'),30]]}))
if __name__=='__main__':unittest.main()
