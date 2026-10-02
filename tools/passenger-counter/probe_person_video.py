"""Compare local pretrained person models at actual, hash-bound video frames."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('YOLO_CONFIG_DIR', str(Path('runs/settings').resolve()))
os.environ.setdefault('MPLCONFIGDIR', str(Path('runs/matplotlib').resolve()))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--models', nargs='+', required=True)
    p.add_argument('--model-family',choices=['yolo','rtdetr'],default='yolo')
    p.add_argument('--frames', nargs='+', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    import cv2
    from ultralytics import YOLO,RTDETR
    from runtime_threads import configure_model_threads
    from feature_cache_proof import snapshot_files, require_unchanged
    specs = [spec.split('=',1) for spec in a.models]
    snapshot = snapshot_files([a.source, Path(__file__), Path('runtime_threads.py')]
                              + [Path(path) for _,path in specs])
    a.output.mkdir(parents=True, exist_ok=False)
    cap = cv2.VideoCapture(str(a.source))
    frames = {}
    try:
        for fid in a.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f'Cannot decode frame {fid}')
            frames[fid] = frame
    finally:
        cap.release()
    rows = []
    for name, path in specs:
        model = (RTDETR if a.model_family=='rtdetr' else YOLO)(path)
        configure_model_threads(model, 2)
        for fid, image in frames.items():
            result = model.predict(image, classes=[0], conf=.1, imgsz=640,
                                   rect=True, device='cpu', verbose=False)[0]
            boxes, scores = result.boxes.xyxy.tolist(), result.boxes.conf.tolist()
            row = dict(model=name, model_path=path, model_family=type(model).__name__,frame=fid, boxes=boxes, scores=scores)
            rows.append(row)
            frame = image.copy()
            for box, score in zip(boxes,scores):
                x1,y1,x2,y2 = map(round,box)
                cv2.rectangle(frame,(x1,y1),(x2,y2),(0,200,0),1)
                cv2.putText(frame,f'{score:.2f}',(x1,max(12,y1-3)),0,.35,(0,200,0),1)
            if not cv2.imwrite(str(a.output/f'{name}-{fid}.jpg'),frame):
                raise ValueError('Cannot save model review')
            print(json.dumps(row),flush=True)
    require_unchanged(snapshot)
    report = dict(source=str(a.source), source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
                  rows=rows, input_snapshot_sha256=snapshot, inputs_unchanged_after_work=True,
                  diagnostic_only=True, confidence=.1, imgsz=640, jetson_validated=False,
                  training_used=False, tracking_rerun=False)
    (a.output/'probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
