import unittest
from counter import PassageCounter
from geometry_visibility import boundary_visibility


class VisibilityTests(unittest.TestCase):
    def test_clipped_bottom_cannot_establish_a_below_door_approach(self):
        counter=PassageCounter(geometry='doorway',low=.95,high=1.05)
        info=boundary_visibility(counter,(860,90,1390,1080),1920,1080)
        self.assertFalse(info['high_region_visible'])
        self.assertTrue(info['lateral_route_possible'])
        self.assertEqual(counter.totals,{'in':0,'out':0})

    def test_translation_preserves_visible_horizontal_passage(self):
        counter=PassageCounter(axis='x',entry='negative',low=.3,high=.4)
        for door in [(860,90,1390,1080),(540,90,1070,1080)]:
            self.assertFalse(boundary_visibility(counter,door,1920,1080)['has_invisible_axis_region'])
