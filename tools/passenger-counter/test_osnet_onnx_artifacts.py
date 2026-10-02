import json
from pathlib import Path
import shutil
import tempfile
import unittest
from osnet_onnx_features import ONNXOSNetFeatures


class OSNetArtifactTests(unittest.TestCase):
    def setUp(self):
        original=Path('runs/osnet-observed-dynamic-onnx-resume4-r2')
        if not original.is_dir():self.skipTest('Optional verified OSNet export not available')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name in ('model.onnx','parity.json'):shutil.copy2(original/name,self.root/name)

    def test_loaded_session_does_not_mask_later_model_or_proof_mutation(self):
        for name in ('model.onnx','parity.json'):
            with self.subTest(name=name):
                feature=ONNXOSNetFeatures(self.root)
                path=self.root/name;before=path.read_bytes();path.write_bytes(before+b' ')
                with self.assertRaisesRegex(ValueError,'changed'):feature.verify_artifacts_unchanged()
                path.write_bytes(before)

    def test_failure_proof_cannot_be_used_as_a_valid_export(self):
        proof_path=self.root/'parity.json';proof=json.loads(proof_path.read_text())
        proof['feature_parity_passed']=False;proof_path.write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError,'positive feature parity'):ONNXOSNetFeatures(self.root)


if __name__=='__main__':unittest.main()
