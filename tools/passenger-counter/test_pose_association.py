import unittest
from associate_pose import associated_keypoints

class PoseAssociationTests(unittest.TestCase):
    def test_match_is_geometry_based_and_ambiguous_competing_bodies_are_rejected(self):
        box=[0,0,100,100];pose=[[0,0,0]]*17
        matches,proof=associated_keypoints([(99,box)],[box],[pose])
        self.assertEqual(set(matches),{99});self.assertEqual(proof[0]['pose_index'],0)
        self.assertFalse(associated_keypoints([(99,box),(100,box)],[box],[pose])[0])
        self.assertFalse(associated_keypoints([(99,box)],[box,box],[pose,pose])[0])
        self.assertFalse(associated_keypoints([(99,[200,0,300,100])],[box],[pose])[0])

if __name__=='__main__':unittest.main()
