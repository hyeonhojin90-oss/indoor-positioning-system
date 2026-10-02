import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from retrack_people import load_reference


class FrozenDoorTests(unittest.TestCase):
    def test_rejects_different_source_or_incomplete_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'source.mp4'
            source.write_bytes(b'video-a')
            run = root/'run'
            run.mkdir()
            summary = {'frames':1,'source_sha256':hashlib.sha256(b'video-a').hexdigest()}
            (run/'summary.json').write_text(json.dumps(summary),encoding='utf-8')
            (run/'tracks.jsonl').write_text('{"frame":0,"door":null,"door_generation":0}\n',encoding='utf-8')
            _, rows, digest = load_reference(run,source)
            self.assertEqual((rows[0]['frame'],digest),(0,summary['source_sha256']))
            source.write_bytes(b'video-b')
            with self.assertRaisesRegex(ValueError,'does not match'):
                load_reference(run,source)
            source.write_bytes(b'video-a')
            (run/'tracks.jsonl').write_text('{"frame":1,"door":null}\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'incomplete'):
                load_reference(run,source)
            (run/'tracks.jsonl').write_text('{"frame":0,"door":null}\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'door_generation'):
                load_reference(run,source)


if __name__ == '__main__':
    unittest.main()
