import unittest
from evaluate_events import evaluate


class EventTests(unittest.TestCase):
    def test_duplicate_and_wrong_direction(self):
        r=evaluate([{'time_s':1,'direction':'in'},{'time_s':1.1,'direction':'in'},
                    {'time_s':2,'direction':'out'}],
                   [{'time_s':1,'direction':'in'},{'time_s':2,'direction':'in'}])
        self.assertEqual((r['in']['tp'],r['in']['fp'],r['in']['fn']),(1,1,1))
        self.assertEqual(r['out']['fp'],1)

    def test_equal_counts_not_equal_events(self):
        r=evaluate([{'time_s':5,'direction':'in'}],[{'time_s':1,'direction':'in'}])
        self.assertEqual(r['in']['tp'],0)

    def test_nan_tolerance_cannot_make_unrelated_events_match(self):
        with self.assertRaises(ValueError):
            evaluate([{'time_s':5,'direction':'in'}],[{'time_s':1,'direction':'in'}],float('nan'))

    def test_invalid_direction_or_time_cannot_disappear_from_totals(self):
        for event in [{'time_s':1,'direction':'unknown'},
                      {'time_s':float('nan'),'direction':'in'},
                      {'time_s':-1,'direction':'out'}]:
            with self.subTest(event=event),self.assertRaises(ValueError):evaluate([event],[])


if __name__=='__main__': unittest.main()
