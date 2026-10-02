from pathlib import Path
import tempfile
import unittest
from runtime_input_evidence import RuntimeInputEvidence


class RuntimeInputEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'video.bin';self.source.write_bytes(b'synthetic file')
        self.config=self.root/'config.json';self.config.write_text('{}')
        self.model=self.root/'model.pt';self.model.write_bytes(b'synthetic model')
        self.cfg={'person_model':str(self.model)}

    def test_numeric_camera_and_remote_addresses_are_not_hashed_as_files(self):
        for source in (0,'rtsp://example.invalid/camera','fakesrc ! appsink'):
            with self.subTest(source=source):
                report=RuntimeInputEvidence(source,self.config,self.cfg).verify()
                self.assertIsNone(report['source_sha256'])
                self.assertFalse(report['source_is_local_file'])

    def test_local_source_model_and_config_are_bound_before_processing(self):
        evidence=RuntimeInputEvidence(str(self.source),self.config,self.cfg)
        report=evidence.verify()
        self.assertTrue(report['local_inputs_unchanged_verified'])
        self.assertEqual(report['local_model_sha256']['person_model'],evidence.snapshot[str(self.model)])
        self.assertIsNotNone(report['source_sha256'])

    def test_changed_source_model_or_config_is_rejected(self):
        for path in (self.source,self.model,self.config):
            with self.subTest(path=path):
                evidence=RuntimeInputEvidence(str(self.source),self.config,self.cfg)
                path.write_bytes(path.read_bytes()+b'changed')
                with self.assertRaisesRegex(ValueError,'input changed'):evidence.verify()

    def test_remote_model_role_remains_explicitly_unbound(self):
        evidence=RuntimeInputEvidence(str(self.source),self.config,dict(self.cfg,door_model='IDEA-Research/grounding-dino-tiny'))
        report=evidence.verify()
        self.assertEqual(report['unbound_model_roles'],['door_model'])


if __name__=='__main__':unittest.main()
