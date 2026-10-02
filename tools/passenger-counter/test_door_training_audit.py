import csv,tempfile,unittest
from pathlib import Path
from audit_door_training_data import audit

class DatasetAuditTests(unittest.TestCase):
    def create(self,records):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);(root/'images').mkdir();(root/'labels').mkdir()
        for i,(group,split,content,label) in enumerate(records):
            (root/'images'/f'{i}.jpg').write_bytes(content);(root/'labels'/f'{i}.txt').write_text(label)
        manifest=root/'manifest.csv'
        with manifest.open('w',newline='') as f:
            writer=csv.writer(f);writer.writerow(['image','session_id','split']);writer.writerows((f'images/{i}.jpg',group,split) for i,(group,split,_,_) in enumerate(records))
        return manifest
    def test_recording_leak_and_duplicate_sampling_cannot_increase_data(self):
        for records in [[('same','train',b'a',''),('same','test',b'b','')],[('one','train',b'a',''),('two','test',b'a','')]]:
            with self.assertRaises(ValueError):audit(self.create(records))
    def test_empty_labels_not_claimed_visually_correct(self):
        r=audit(self.create([('one','train',b'a','')]))
        self.assertEqual(r['unique_images'],1);self.assertFalse(r['label_visual_correctness_validated']);self.assertEqual(len(r['splits']['train']['empty_label_images']),1)
    def test_nonfinite_or_zero_size_label_rejected(self):
        for label in ['0 nan .5 .2 .2','0 .5 .5 0 .2','1 .5 .5 .2 .2']:
            with self.assertRaises(ValueError):audit(self.create([('one','train',b'a',label)]))

    def test_outside_box_and_duplicate_label_rejected(self):
        for label in ['0 .9 .5 .4 .2','0 .5 .1 .2 .4','0 .5 .5 .2 .2\n0 .5 .5 .2 .2']:
            with self.assertRaises(ValueError):audit(self.create([('one','train',b'a',label)]))
    def test_border_touching_label_is_valid(self):
        r=audit(self.create([('one','train',b'a','0 .5 .5 1 1')]))
        self.assertEqual(r['splits']['train']['positive_boxes'],1)

if __name__=='__main__':unittest.main()
