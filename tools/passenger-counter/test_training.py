import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from train_door import prepare, repeat_bus_training


class DatasetTests(unittest.TestCase):
    def test_label_edit_changes_provenance_even_when_images_are_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'images').mkdir(); (root/'labels').mkdir()
            with (root/'manifest.csv').open('w',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(['image','session_id','split'])
                for i,split in enumerate(['train','val','test']):
                    (root/f'images/{i}.jpg').write_bytes(bytes([i]))
                    (root/f'labels/{i}.txt').write_text('0 .5 .5 .2 .2\n')
                    writer.writerow([f'images/{i}.jpg',str(i),split])
            prepare(root/'manifest.csv',root/'before')
            label=root/'labels/0.txt'
            label.write_text('0 .5 .5 .4 .4\n')
            prepare(root/'manifest.csv',root/'after')
            before=json.loads((root/'before/provenance.json').read_text())
            after=json.loads((root/'after/provenance.json').read_text())
            self.assertEqual(before['sha256'],after['sha256'])
            self.assertNotEqual(before['label_sha256'][label.as_posix()],after['label_sha256'][label.as_posix()])
            self.assertEqual(after['label_sha256'][label.as_posix()],hashlib.sha256(label.read_bytes()).hexdigest())

    def test_bus_sampling_keeps_unique_sources_and_evaluation_splits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'images').mkdir(); (root/'labels').mkdir()
            manifest = root/'manifest.csv'
            with manifest.open('w',newline='') as f:
                writer=csv.writer(f);writer.writerow(['image','session_id','split'])
                for n,(group,split) in enumerate([('public-A','train'),('bus-A','train'),
                                                  ('bus-B','val'),('bus-C','test')]):
                    (root/f'images/{n}.jpg').write_bytes(bytes([n]))
                    (root/f'labels/{n}.txt').write_text('0 .5 .5 .3 .8\n')
                    writer.writerow([f'images/{n}.jpg',group,split])
            data=prepare(manifest,root/'prepared')
            before={s:(data.parent/f'{s}.txt').read_bytes() for s in ('val','test')}
            repeat_bus_training(manifest,data,4)
            paths=(data.parent/'train.txt').read_text().splitlines()
            self.assertEqual(len(paths),5)
            self.assertEqual(len(set(paths)),2)
            self.assertEqual(paths.count((root/'images/1.jpg').as_posix()),4)
            for split,value in before.items():
                self.assertEqual((data.parent/f'{split}.txt').read_bytes(),value)

    def test_invalid_geometry_or_duplicate_door_rejected_before_training_output(self):
        for bad in ['0 .9 .5 .4 .2','0 .5 .5 .2 .2\n0 .5 .5 .2 .2']:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'images').mkdir();(root/'labels').mkdir()
                with (root/'manifest.csv').open('w',newline='') as stream:
                    writer=csv.writer(stream);writer.writerow(['image','session_id','split'])
                    for i,split in enumerate(['train','val','test']):
                        (root/f'images/{i}.jpg').write_bytes(bytes([i]))
                        (root/f'labels/{i}.txt').write_text(bad if i==0 else '0 .5 .5 .2 .2')
                        writer.writerow([f'images/{i}.jpg',str(i),split])
                with self.assertRaises(ValueError):prepare(root/'manifest.csv',root/'output')
                self.assertFalse((root/'output').exists())

    def test_split_and_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'images').mkdir()
            (root/'labels').mkdir()
            for n in range(3):
                (root/f'images/{n}.jpg').write_bytes(bytes([n]))
                (root/f'labels/{n}.txt').write_text('0 0.5 0.5 0.3 0.8\n')
            manifest = root/'manifest.csv'
            def write(groups):
                with manifest.open('w',newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['image','session_id','split'])
                    for n,s in enumerate(['train','val','test']):
                        w.writerow([f'images/{n}.jpg',groups[n],s])
            write(['A','B','C'])
            self.assertTrue(prepare(manifest,root/'good').exists())
            write(['A','A','C'])
            with self.assertRaisesRegex(ValueError,'Session leakage'):
                prepare(manifest,root/'bad')


if __name__ == '__main__':
    unittest.main()
