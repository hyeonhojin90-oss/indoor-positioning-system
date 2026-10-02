"""Local reference diagnostic on source frames, without supplied door coordinates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

os.environ.setdefault('YOLO_CONFIG_DIR', str(Path('runs/settings').resolve()))
os.environ.setdefault('MPLCONFIGDIR', str(Path('runs/matplotlib').resolve()))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--frames', nargs='+', type=int, required=True)
    p.add_argument('--prompt', default='a bus door.')
    p.add_argument('--conf', type=float, default=.2)
    p.add_argument('--object-class',choices=['door','person'],default='door')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if not 0 < a.conf <= 1 or any(f < 0 for f in a.frames):
        raise ValueError('Invalid confidence or frame')
    import cv2
    import torch
    from grounding_detector import GroundingDoorDetector
    from feature_cache_proof import snapshot_files, require_unchanged
    torch.set_num_threads(2)
    model = GroundingDoorDetector(prompt=a.prompt)
    snapshot_paths = [a.source, Path(__file__), Path('grounding_detector.py')]
    snapshot_paths += list(Path(model.provenance['snapshot_path']).glob('*'))
    snapshot = snapshot_files([f for f in snapshot_paths if f.is_file()])
    a.output.mkdir(parents=True, exist_ok=False)
    cap = cv2.VideoCapture(str(a.source))
    rows = []
    start = time.perf_counter()
    try:
        for fid in a.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f'Cannot decode frame {fid}')
            if a.object_class=='door':
                result = model.predict(frame, conf=a.conf, device='cpu')[0]
                boxes, scores = result.boxes.xyxy.tolist(), result.boxes.conf.tolist()
            else:
                from PIL import Image
                image=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                inputs=model.processor(images=image,text=a.prompt,return_tensors='pt')
                with torch.inference_mode():outputs=model.model(**inputs)
                detected=model.processor.post_process_grounded_object_detection(outputs,inputs.input_ids,
                    threshold=a.conf,text_threshold=.25,target_sizes=[image.size[::-1]])[0]
                candidates=[(b,s) for b,s,label in zip(detected['boxes'].tolist(),detected['scores'].tolist(),detected['text_labels'])
                            if any(word in label for word in ('person','woman','man','passenger'))]
                boxes=[b for b,_ in candidates];scores=[s for _,s in candidates]
            rows.append(dict(frame=fid, boxes=boxes, scores=scores))
            for box, score in zip(boxes, scores):
                x1, y1, x2, y2 = map(round, box)
                cv2.rectangle(frame, (x1,y1), (x2,y2), (0,200,0), 2)
                cv2.putText(frame, f'{score:.3f}', (x1,max(12,y1-3)), 0, .4, (0,200,0), 1)
            if not cv2.imwrite(str(a.output/f'frame-{fid}.jpg'), frame):
                raise ValueError('Cannot save actual diagnostic frame')
            print(json.dumps(rows[-1]), flush=True)
    finally:
        cap.release()
    require_unchanged(snapshot)
    report = dict(source=str(a.source), source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
                  rows=rows, model=model.provenance, prompt=a.prompt, confidence=a.conf,object_class=a.object_class,
                  input_snapshot_sha256=snapshot, inputs_unchanged_after_work=True,
                  elapsed_seconds=time.perf_counter()-start, diagnostic_only=True,
                  oracle_region_used=False, training_used=False, jetson_validated=False)
    (a.output/'probe.json').write_text(json.dumps(report,indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
