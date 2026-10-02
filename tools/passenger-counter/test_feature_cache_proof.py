import copy
import hashlib
import unittest
import tempfile
from pathlib import Path
from feature_cache_proof import validate_feature_cache, snapshot_files, require_unchanged


class FeatureCacheProofTests(unittest.TestCase):
    def setUp(self):
        self.reference = [dict(frame=0, raw_ids=[1], raw_boxes=[[0, 0, 10, 20]])]
        self.rows = [dict(self.reference[0], features=[[1., 0.]])]
        self.summary = {key: hashlib.sha256(value).hexdigest() for key, value in
                        [('features_sha256', b'features'), ('reference_summary_sha256', b'summary'),
                         ('reference_tracks_sha256', b'tracks')]}

    def check(self, **changes):
        args = dict(reference=self.reference, summary=self.summary, cache_rows=self.rows,
                    feature_bytes=b'features', reference_summary_bytes=b'summary', reference_tracks_bytes=b'tracks')
        args.update(changes)
        validate_feature_cache(**args)

    def test_exact_observed_reference_passes(self):
        self.check()

    def test_changed_or_missing_digest_is_rejected(self):
        for key in self.summary:
            summary = dict(self.summary)
            summary.pop(key)
            with self.assertRaises(ValueError):
                self.check(summary=summary)
        for key in ('feature_bytes', 'reference_summary_bytes', 'reference_tracks_bytes'):
            with self.assertRaises(ValueError):
                self.check(**{key: b'changed'})

    def test_same_source_with_different_crop_or_identity_is_rejected(self):
        for key, value in [('frame', 1), ('raw_ids', [2]), ('raw_boxes', [[1, 0, 10, 20]]), ('features', [])]:
            rows = copy.deepcopy(self.rows)
            rows[0][key] = value
            with self.assertRaises(ValueError):
                self.check(cache_rows=rows)

    def test_incomplete_cache_is_rejected(self):
        with self.assertRaises(ValueError):
            self.check(cache_rows=[])

    def test_changed_reference_during_extraction_cannot_get_completion_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'tracks.jsonl'
            path.write_bytes(b'initial observed boxes')
            snapshot = snapshot_files([path])
            require_unchanged(snapshot)
            path.write_bytes(b'different observed boxes')
            with self.assertRaises(ValueError):
                require_unchanged(snapshot)

    def test_removed_reference_cannot_get_completion_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'summary.json'
            path.write_bytes(b'initial summary')
            snapshot = snapshot_files([path])
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                require_unchanged(snapshot)


if __name__ == '__main__':
    unittest.main()
