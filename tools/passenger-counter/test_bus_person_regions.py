import unittest
from bus_person_regions import search_regions,restore_observation


class BusPersonRegionTests(unittest.TestCase):
    def test_bounded_actual_crop_and_coordinate_restore(self):
        region=search_regions([[50,50,150,150]],300,300)[0]
        self.assertEqual(region,(30,30,170,170))
        self.assertEqual(restore_observation([10,10,100,130],region,300,300),[40,40,130,160])

    def test_clipped_feet_or_head_do_not_become_full_person_measurements(self):
        region=(30,30,170,170)
        for box in [[10,10,100,139],[10,0,100,100],[0,10,100,130],[10,10,140,130]]:
            self.assertIsNone(restore_observation(box,region,300,300))

    def test_no_bus_and_full_image_do_not_add_crop_inference(self):
        self.assertEqual(search_regions([],300,300),[])
        self.assertEqual(search_regions([[0,0,300,300]],300,300),[])
        with self.assertRaises(ValueError):search_regions([[0,0,301,300]],300,300)


if __name__=='__main__':unittest.main()
