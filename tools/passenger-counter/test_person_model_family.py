import tempfile,unittest
from pathlib import Path
from person_model_family import validate
from prepare_engine_config import runtime_roles

class ModelFamilyTests(unittest.TestCase):
    def test_default_family_does_not_require_or_load_alternative_model(self):
        self.assertEqual(validate({}),'yolo')
    def test_alternative_requires_its_own_preprocessing_and_no_reid_hooks(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.pt';path.write_bytes(b'configuration test only')
            config=dict(person_family='rtdetr',person_task='detect',person_rect=False,person_imgsz=640,person_model=str(path))
            self.assertEqual(validate(config),'rtdetr')
            for key,value in [('person_task','pose'),('person_rect',True),('person_imgsz',960),('person_tracker','botsort.yaml'),('lost_reid_guard',True),('person_model','missing.pt')]:
                with self.subTest(key=key),self.assertRaises(ValueError):validate(dict(config,**{key:value}))
    def test_duplicate_suppression_cannot_modify_default_family(self):
        with self.assertRaises(ValueError):validate({'person_rtdetr_nms_iou':.7})

    def test_existing_export_protocol_rejects_unvalidated_family(self):
        with self.assertRaises(ValueError):runtime_roles({'person_family':'rtdetr'})

if __name__=='__main__':unittest.main()
