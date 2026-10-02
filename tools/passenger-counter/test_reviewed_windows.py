import unittest
from evaluate_events import evaluate_windows


class ReviewWindowTests(unittest.TestCase):
    def test_overlapping_intervals_need_one_to_one_rematching(self):
        result = evaluate_windows([{'direction':'in','time_s':2},
                                   {'direction':'in','time_s':3}],
                                  [{'direction':'in','start_s':1,'end_s':4},
                                   {'direction':'in','start_s':1,'end_s':2}])
        self.assertEqual(result['matched_reviewed_events'],2)

    def test_subset_does_not_call_unknown_prediction_false_positive(self):
        result = evaluate_windows([{'direction':'out','time_s':2}],
                                  [{'direction':'in','start_s':1,'end_s':3}])
        self.assertEqual(len(result['missed_reviewed_events']),1)
        self.assertEqual(len(result['unclassified_predictions']),1)
        self.assertIsNone(result['precision'])

    def test_duplicate_predictions_do_not_double_match(self):
        result = evaluate_windows([{'direction':'in','time_s':2}]*2,
                                  [{'direction':'in','start_s':1,'end_s':3}])
        self.assertEqual(result['matched_reviewed_events'],1)

    def test_invalid_interval_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_windows([], [{'direction':'in','start_s':3,'end_s':2}])

    def test_identity_review_blocks_duplicate_in_another_person_window(self):
        predictions=[{'frame':61,'track_id':14,'direction':'in','time_s':2},
                     {'frame':115,'track_id':4,'direction':'in','time_s':3.8}]
        truth=[{'person':'olive','direction':'in','start_s':1.8,'end_s':2.8},
               {'person':'brown','direction':'in','start_s':2.8,'end_s':4.5}]
        review=[{'frame':61,'track_id':14,'direction':'in','status':'accepted','person':'olive'},
                {'frame':115,'track_id':4,'direction':'in','status':'duplicate','person':'olive'}]
        result=evaluate_windows(predictions,truth,identity_review=review)
        self.assertEqual(result['matched_reviewed_events'],1)
        self.assertEqual(result['missed_reviewed_events'][0]['person'],'brown')
        self.assertFalse(result['temporal_matching_only'])

    def test_stale_identity_review_rejected(self):
        with self.assertRaisesRegex(ValueError,'does not match'):
            evaluate_windows([],[],identity_review=[{'frame':1,'track_id':4,
                             'direction':'in','status':'duplicate'}])


if __name__ == '__main__':
    unittest.main()
