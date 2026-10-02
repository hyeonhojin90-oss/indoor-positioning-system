import unittest
from latest_usage import stop_policy

class UsageBoundaryTest(unittest.TestCase):
    def test_user_strict_below_five(self):
        self.assertFalse(stop_policy(94,5)['stop_reached'])
        self.assertFalse(stop_policy(95,5)['stop_reached'])
        self.assertTrue(stop_policy(95.1,5)['stop_reached'])
        self.assertTrue(stop_policy(96,5)['stop_reached'])

    def test_prior_threshold_stays_compatible(self):
        self.assertTrue(stop_policy(95)['stop_reached'])
        self.assertFalse(stop_policy(94.9)['stop_reached'])
        with self.assertRaises(ValueError):stop_policy(50,0)

if __name__=='__main__':unittest.main()
