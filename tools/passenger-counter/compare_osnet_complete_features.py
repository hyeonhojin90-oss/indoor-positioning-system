"""Compare exported embeddings on every actual frozen observed crop."""
import argparse
import hashlib
import json
import time
from pathlib import Path
import cv2
import numpy as np
import torch
from feature_cache_proof import validate_feature_cache, snapshot_files, require_unchanged
from osnet_onnx_features import ONNXOSNetFeatures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--reference-cache', type=Path, required=True)
    parser.add_argument('--onnx', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    summary_path = args.run / 'summary.json'
    tracks_path = args.run / 'tracks.jsonl'
    initial = snapshot_files([summary_path, tracks_path, args.reference_cache / 'summary.json',
                              args.reference_cache / 'features.jsonl', args.onnx / 'model.onnx',
                              args.onnx / 'parity.json', 'compare_osnet_complete_features.py',
                              'osnet_onnx_features.py', 'osnet_preprocessing.py', 'feature_cache_proof.py'])
    summary = json.loads(summary_path.read_text())
    tracks = [json.loads(x) for x in tracks_path.read_text().splitlines()]
    cache_summary = json.loads((args.reference_cache / 'summary.json').read_text())
    cache_path = args.reference_cache / 'features.jsonl'
    cache = [json.loads(x) for x in cache_path.read_text().splitlines()]
    validate_feature_cache(tracks, cache_summary, cache, cache_path.read_bytes(),
                           summary_path.read_bytes(), tracks_path.read_bytes())
    source = Path(summary['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != summary['source_sha256']:
        raise ValueError('Changed source')
    if len(tracks) != summary['frames'] or [r['frame'] for r in tracks] != list(range(summary['frames'])):
        raise ValueError('Incomplete source trace')
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(2)
    encoder = ONNXOSNetFeatures(args.onnx)
    cap = cv2.VideoCapture(str(source))
    started = time.perf_counter()
    max_error = 0.
    min_cosine = 1.
    observed_boxes = 0
    failures = []
    try:
        with (args.output / 'features.jsonl').open('x') as stream:
            for actual, reference in zip(tracks, cache):
                ok, frame = cap.read()
                if not ok:
                    raise ValueError('Early source end')
                features = encoder.extract(frame, actual['raw_boxes'])
                expected = np.asarray(reference['features'], dtype=np.float32)
                if len(features):
                    error = float(np.max(np.abs(features - expected)))
                    cosine = float(np.min(np.sum(features * expected, axis=1)))
                    max_error, min_cosine = max(max_error, error), min(min_cosine, cosine)
                    if error > 1e-4 or cosine < .99999:
                        failures.append(dict(frame=actual['frame'], max_abs_error=error, min_cosine=cosine))
                observed_boxes += len(features)
                stream.write(json.dumps(dict(frame=actual['frame'], raw_ids=actual['raw_ids'],
                                             raw_boxes=actual['raw_boxes'], features=features.tolist())) + '\n')
                if actual['frame'] % 60 == 0:
                    print('observed ONNX features frame', actual['frame'], flush=True)
            if cap.read()[0]:
                raise ValueError('Unprocessed actual source tail')
    finally:
        cap.release()
    if hashlib.sha256(source.read_bytes()).hexdigest() != summary['source_sha256']:
        raise ValueError('Source changed during feature comparison')
    require_unchanged(initial)
    report = dict(frames=len(tracks), observed_boxes=observed_boxes, failures=failures,
                  max_abs_error=max_error, min_cosine=min_cosine, feature_parity_passed=not failures,
                  source_sha256=summary['source_sha256'], reference_run=str(args.run),
                  reference_summary_sha256=hashlib.sha256(summary_path.read_bytes()).hexdigest(),
                  reference_tracks_sha256=hashlib.sha256(tracks_path.read_bytes()).hexdigest(),
                  reference_features_sha256=cache_summary['features_sha256'],
                  features_sha256=hashlib.sha256((args.output / 'features.jsonl').read_bytes()).hexdigest(),
                  model_provenance=encoder.provenance, elapsed_seconds=time.perf_counter() - started,
                  full_observed_crops_processed=True, whole_tracking_validated=False,
                  hardware_validated=False, independent_accuracy_validated=False)
    report.update(input_snapshot_sha256=initial, inputs_unchanged_during_extraction=True)
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['frames', 'observed_boxes', 'max_abs_error',
                                           'min_cosine', 'feature_parity_passed', 'elapsed_seconds']}))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
