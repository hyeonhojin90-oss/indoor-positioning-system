import unittest
from confidence_door_selection import select_confident_door

class ConfidenceDoorTests(unittest.TestCase):
    def test_high_confidence_portal_beats_neighbor_window(self):
        a=(0,0,20,100);b=(30,0,50,100)
        people=[(5,40,15,100),(31,40,41,100),(39,40,49,100)]
        self.assertEqual(select_confident_door([a,b],people,[.95,.2]),0)

    def test_no_passengers_or_head_only_cannot_acquire(self):
        door=(0,0,20,100)
        for people in ([],[(5,0,15,20)]):
            self.assertIsNone(select_confident_door([door],people,[.99]))
        self.assertEqual(select_confident_door([door],[],[.1],door),0)

    def test_bad_scores_rejected_and_lock_cannot_be_switched_by_confidence_alone(self):
        a=(0,0,20,100);b=(30,0,50,100)
        people=[(5,40,15,100),(35,40,45,100)]
        self.assertEqual(select_confident_door([a,b],people,[.1,.9],a),0)
        for scores in ([.9],[.9,float('nan')],[.9,True],[.9,1.1]):
            with self.assertRaises(ValueError):select_confident_door([a,b],people,scores)

if __name__=='__main__':unittest.main()
