"""Optional verified ONNX appearance adapter; no native model load or tracking."""
import hashlib
import json
from pathlib import Path
import numpy as np
import onnxruntime as ort
from osnet_preprocessing import observed_crops, transform
from feature_cache_proof import snapshot_files, require_unchanged


class ONNXOSNetFeatures:
    def __init__(self, root):
        root = Path(root)
        model = root / 'model.onnx'
        artifact_snapshot = snapshot_files([model, root/'parity.json'])
        proof = json.loads((root / 'parity.json').read_text(encoding='utf-8'))
        comparisons = proof.get('comparisons', [])
        if not proof.get('feature_parity_passed') or not comparisons or not all(x['passed'] for x in comparisons):
            raise ValueError('Require actual positive feature parity')
        if hashlib.sha256(model.read_bytes()).hexdigest() != proof['exported_sha256']:
            raise ValueError('Changed verified feature model')
        if proof['input'] != 'RGB float32 ImageNet normalized N,3,256,128':
            raise ValueError('Different feature input contract')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider'])
        self.transform = transform()
        self.provenance = proof
        require_unchanged(artifact_snapshot)
        self.artifact_snapshot = artifact_snapshot

    def verify_artifacts_unchanged(self):
        require_unchanged(self.artifact_snapshot)

    def extract(self, frame, boxes):
        inputs = observed_crops(frame, boxes, self.transform).numpy()
        if not len(inputs):
            return np.empty((0, 512), dtype=np.float32)
        features = self.session.run(['features'], {'rgb_normalized': inputs})[0]
        if features.shape != (len(boxes), 512) or not np.isfinite(features).all():
            raise ValueError('Invalid observed feature output')
        if np.any(np.abs(np.linalg.norm(features, axis=1) - 1) > .001):
            raise ValueError('Unnormalized observed features')
        return features
