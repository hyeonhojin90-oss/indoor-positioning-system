import unittest
from counter import DoorLock


class DoorAcquisitionTests(unittest.TestCase):
    def test_median_rejects_one_boundary_outlier_and_stays_frozen(self):
        lock = DoorLock(stable=5,aggregation='median')
        boxes = [(10,20,100,200),(11,21,101,201),(10,20,100,225),
                 (9,19,99,199),(10,20,100,200)]
        for n,b in enumerate(boxes):
            lock.observe(b,n*.1)
        self.assertEqual(lock.box,(10,20,100,200))
        lock.observe((12,22,102,210),.6)
        self.assertEqual(lock.box,(10,20,100,200))

    def test_miss_displacement_and_expiry_break_consensus(self):
        for interrupted in ('miss','displacement','expiry'):
            with self.subTest(interrupted=interrupted):
                lock = DoorLock(stable=3,aggregation='median',ttl=.5)
                a=(0,0,100,200);b=(200,0,300,200)
                lock.observe(a,0);lock.observe(a,.1)
                if interrupted == 'miss':lock.observe(None,.2)
                if interrupted == 'displacement':lock.observe(b,.2)
                lock.observe(a,1 if interrupted=='expiry' else .3)
                self.assertIsNone(lock.box)
                self.assertEqual(lock.hits,1)
                self.assertEqual(lock.history,[a])

    def test_default_latest_geometry_is_preserved(self):
        lock=DoorLock(stable=2)
        lock.observe((0,0,100,200),0)
        lock.observe((1,2,101,205),.1)
        self.assertEqual(lock.box,(1,2,101,205))
        with self.assertRaises(ValueError):DoorLock(aggregation='average_forever')


if __name__=='__main__':unittest.main()
