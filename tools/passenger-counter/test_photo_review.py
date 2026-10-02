import unittest
from probe_door_photos import validate_review

class ReviewSchemaTests(unittest.TestCase):
    def row(self):
        return dict(name='photo.jpg',sha256='a'*64,status='visible',target_box=[1,2,30,40])

    def test_missing_status_rejected_before_inference(self):
        r=self.row();del r['status']
        with self.assertRaisesRegex(ValueError,'missing status'):validate_review(dict(images=[r]))

    def test_unknown_positive_geometry_allowed_invalid_boxes_rejected(self):
        r=self.row();r['target_box']=None
        self.assertEqual(validate_review(dict(images=[r])),[r])
        for box in ([3,2,1,4],[0,0,float('nan'),4],[0,0,True,4]):
            r=self.row();r['target_box']=box
            with self.assertRaises(ValueError):validate_review(dict(images=[r]))

    def test_paths_and_duplicate_names_rejected(self):
        r=self.row();r['name']='../photo.jpg'
        with self.assertRaises(ValueError):validate_review(dict(images=[r]))
        with self.assertRaises(ValueError):validate_review(dict(images=[self.row(),self.row()]))

if __name__=='__main__':unittest.main()
