import hashlib,json,tempfile,unittest
from pathlib import Path
from verify_handoff import verify
from export_target_engine import validate_target

class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.file=self.root/'model.onnx';self.file.write_bytes(b'actual graph')
        self.rows=[dict(path='model.onnx',bytes=12,sha256=hashlib.sha256(self.file.read_bytes()).hexdigest())]
    def manifest(self): (self.root/'handoff-manifest.json').write_text(json.dumps(dict(files=self.rows)))
    def test_integrity_passes_and_tamper_fails(self):
        self.manifest();self.assertTrue(verify(self.root)['passed'])
        self.file.write_bytes(b'changed data');self.assertFalse(verify(self.root)['passed'])
    def test_missing_file_fails(self):
        self.manifest();self.file.unlink();self.assertFalse(verify(self.root)['passed'])
    def test_path_escape_rejected(self):
        for name in ['../secret','/outside','sub\\file']:
            self.rows[0]['path']=name;self.manifest()
            with self.assertRaises(ValueError):verify(self.root)
    def test_windows_cannot_be_mislabeled_as_target_export(self):
        with self.assertRaises(ValueError):validate_target(dict(platform='Windows',machine='AMD64',jetson_detected=False))
    def test_arm_machine_without_cuda_cannot_export(self):
        with self.assertRaises(ValueError):validate_target(dict(platform='Linux',machine='aarch64',jetson_detected=True,cuda_available=False))
    def test_new_package_version_requires_separate_validation(self):
        with self.assertRaises(ValueError):validate_target(dict(platform='Linux',machine='aarch64',jetson_detected=True,cuda_available=True,tensorrt_import_version='10',packages={'ultralytics':'future'}))

if __name__=='__main__':unittest.main()
