import unittest
from door_selection import passenger_support,select_door,passenger_search_regions,locked_search_region


class SelectionTests(unittest.TestCase):
    def test_automatic_lock_crop_covers_door_with_frame_clamps(self):
        self.assertEqual(locked_search_region((10,10,40,90),100,100),[(0,0,70,100)])
        self.assertEqual(locked_search_region((0,0,1,1),100,100),[])
    def test_search_crops_require_bus_and_full_body(self):
        self.assertEqual(passenger_search_regions([(0,0,10,40)],[],100,100),[])
        self.assertEqual(passenger_search_regions([(45,5,55,20)],[(30,0,100,100)],100,100),[])
        r=passenger_search_regions([(45,25,55,90)],[(30,0,100,100)],100,100)
        self.assertEqual(len(r),1)
        self.assertTrue(all(0<=v<=100 for v in r[0]))
    def test_waiting_passengers_choose_middle_door(self):
        front=(70,0,100,100);middle=(10,10,30,80)
        self.assertEqual(select_door([front,middle],[(12,25,25,90)]),1)

    def test_window_heads_and_absent_passengers_cannot_acquire(self):
        self.assertIsNone(select_door([(0,0,20,100)],[]))
        self.assertEqual(passenger_support((0,0,20,100),[(5,0,15,30)]),0)

    def test_lock_retention_and_switch_requires_better_support(self):
        a=(0,0,20,100);b=(80,0,100,100)
        self.assertEqual(select_door([a,b],[],a),0)
        self.assertEqual(select_door([a,b],[(82,30,98,100)],a),1)
