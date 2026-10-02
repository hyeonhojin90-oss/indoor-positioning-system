import unittest
from evaluate_events import evaluate_person_directions


class PersonDirectionReviewTests(unittest.TestCase):
    def event(self,frame,tid):return dict(frame=frame,track_id=tid,direction='in',time_s=frame)
    def review(self,frame,tid,person='one'):return dict(frame=frame,track_id=tid,direction='in',person=person,status='accepted')
    def truth(self):return [dict(person='one',direction='in',start_s=10,end_s=20)]

    def test_same_person_two_ids_cannot_inflate_the_matched_person_count(self):
        r=evaluate_person_directions([self.event(11,1),self.event(12,2)],self.truth(),[self.review(11,1),self.review(12,2)])
        self.assertEqual(r['matched_person_directions'],1)
        self.assertEqual(len(r['repeated_accepted_person_predictions']),1)
        self.assertEqual(r['strict_time_matching']['matched_reviewed_events'],1)
        self.assertIsNone(r['precision'])

    def test_early_identity_match_stays_a_strict_timing_failure(self):
        r=evaluate_person_directions([self.event(9,1)],self.truth(),[self.review(9,1)])
        self.assertEqual(r['matched_person_directions'],1)
        self.assertEqual(r['strict_time_matching']['matched_reviewed_events'],0)
        self.assertFalse(r['temporal_accuracy_validated'])

    def test_unreviewed_event_and_wrong_direction_do_not_match_person(self):
        r=evaluate_person_directions([self.event(11,1)],self.truth(),[])
        self.assertEqual(r['matched_person_directions'],0)
        self.assertEqual(len(r['unclassified_predictions']),1)
        event=dict(self.event(11,1),direction='out');review=dict(self.review(11,1),direction='out')
        r=evaluate_person_directions([event],self.truth(),[review])
        self.assertEqual(r['matched_person_directions'],0)

    def test_two_visits_cannot_be_silently_reduced_to_one_person(self):
        with self.assertRaisesRegex(ValueError,'passage-level'):
            evaluate_person_directions([],self.truth()*2,[])


if __name__=='__main__':unittest.main()
