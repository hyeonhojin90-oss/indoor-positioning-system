"""Optional observed-feature parity export; does not validate tracking or Jetson."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import cv2
import numpy as np
import onnx
import onnxruntime as ort
import torch
from osnet_features import OSNetFeatures
from feature_cache_proof import snapshot_files, require_unchanged


class NormalizedOSNet(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, rgb_normalized):
        return torch.nn.functional.normalize(self.model(rgb_normalized), dim=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--frames', nargs='+', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    initial = snapshot_files([args.run / 'summary.json', args.run / 'tracks.jsonl',
                              args.run / 'completion-audit.json', 'export_osnet_verified.py',
                              'osnet_features.py', 'osnet_preprocessing.py', 'feature_cache_proof.py',
                              *[Path('models/osnet-x025-author-resume4') / n
                                for n in ['source.json', 'osnet.py', 'model.pth', 'LICENSE', 'README.md']]])
    summary = json.loads((args.run / 'summary.json').read_text(encoding='utf-8'))
    audit = json.loads((args.run / 'completion-audit.json').read_text(encoding='utf-8'))
    if not audit['complete_source'] or not audit['replay_parity']:
        raise ValueError('Require completed source proof')
    source = Path(summary['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != summary['source_sha256']:
        raise ValueError('Changed source')
    rows = [json.loads(x) for x in (args.run / 'tracks.jsonl').read_text().splitlines()]
    if len(rows) != summary['frames'] or [r['frame'] for r in rows] != list(range(summary['frames'])):
        raise ValueError('Incomplete raw trace')
    if not args.frames or min(args.frames) < 0 or max(args.frames) >= len(rows):
        raise ValueError('Invalid actual frame selection')
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(2)
    encoder = OSNetFeatures()
    wrapper = NormalizedOSNet(encoder.model).eval()
    exported = args.output / 'model.onnx'
    torch.onnx.export(wrapper, torch.zeros(1, 3, 256, 128), str(exported),
                      input_names=['rgb_normalized'], output_names=['features'],
                      dynamic_axes={'rgb_normalized': {0: 'people'}, 'features': {0: 'people'}},
                      opset_version=17, dynamo=False)
    onnx.checker.check_model(str(exported))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(exported), sess_options=options, providers=['CPUExecutionProvider'])
    cap = cv2.VideoCapture(str(source))
    comparisons = []
    try:
        for frame in args.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, image = cap.read()
            if not ok:
                raise ValueError('Failed actual source decode')
            boxes = rows[frame]['raw_boxes']
            if not boxes:
                raise ValueError('Parity needs actual positive crops')
            inputs = encoder.prepare(image, boxes)
            # Both batch one and variable observed positive batches must work.
            for batch in sorted({1, len(boxes)}):
                x = inputs[:batch]
                with torch.inference_mode():
                    expected = wrapper(x).numpy()
                actual = session.run(['features'], {'rgb_normalized': x.numpy()})[0]
                finite = bool(np.isfinite(actual).all())
                error = float(np.max(np.abs(expected - actual)))
                cosine = float(np.min(np.sum(expected * actual, axis=1)))
                passed = finite and actual.shape == (batch, 512) and error <= 1e-4 and cosine >= .99999
                comparisons.append(dict(frame=frame, batch=batch, max_abs_error=error,
                                        min_cosine=cosine, finite=finite, passed=passed))
    finally:
        cap.release()
    for name in ('LICENSE', 'README.md', 'source.json'):
        shutil.copy2(Path('models/osnet-x025-author-resume4') / name, args.output / name)
    require_unchanged(initial)
    if hashlib.sha256(source.read_bytes()).hexdigest() != summary['source_sha256']:
        raise ValueError('Source changed during export parity')
    report = dict(source_sha256=summary['source_sha256'], reference_run=str(args.run),
                  reference_tracks_sha256=hashlib.sha256((args.run / 'tracks.jsonl').read_bytes()).hexdigest(),
                  model_provenance=encoder.provenance,
                  exported_sha256=hashlib.sha256(exported.read_bytes()).hexdigest(),
                  bytes=exported.stat().st_size, input='RGB float32 ImageNet normalized N,3,256,128',
                  output='L2-normalized float32 N,512', cpu_providers=session.get_providers(),
                  comparisons=comparisons, feature_parity_passed=all(x['passed'] for x in comparisons),
                  tracking_validated=False, jetson_validated=False, accuracy_validated=False,
                  implementation_sha256={n: hashlib.sha256(Path(n).read_bytes()).hexdigest()
                                         for n in ['export_osnet_verified.py', 'osnet_features.py', 'osnet_preprocessing.py', 'feature_cache_proof.py']},
                  input_snapshot_sha256=initial, inputs_unchanged_during_export=True)
    (args.output / 'parity.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=report['feature_parity_passed'], bytes=report['bytes'],
                         comparisons=len(comparisons))))
    if not report['feature_parity_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
