"""Prepare a fixed offline visual reference; no per-video manual door ROI."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(__file__).resolve().parent/'runs/settings'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--image', required=True, help='Image name within bootstrap images/')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists() or a.output.with_suffix('.source.json').exists():
        raise FileExistsError('Preserve existing prepared model and provenance')
    if 'yoloe' not in a.output.stem:
        raise ValueError('Output name must contain yoloe for runtime class dispatch')
    rows = list(csv.DictReader(a.manifest.open(encoding='utf-8-sig')))
    selected = [r for r in rows if Path(r['image']).name == a.image]
    if len(selected) != 1 or selected[0]['split'] != 'train':
        raise ValueError('Exactly one training reference required; no evaluation reference')
    row = selected[0]
    image_path = a.manifest.parent / row['image']
    label_path = a.manifest.parent/'labels'/Path(a.image).with_suffix('.txt')
    fields = label_path.read_text().split()
    if len(fields) != 5 or fields[0] != '0':
        raise ValueError('Reference must have exactly one class-0 bootstrap door')
    import cv2
    import numpy as np
    import torch
    import ultralytics
    from ultralytics import YOLO, YOLOE
    from ultralytics.models.yolo.yoloe.predict import YOLOEVPSegPredictor
    torch.set_num_threads(2)
    image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Cannot read reference image')
    h, w = image.shape[:2]
    cx, cy, bw, bh = map(float, fields[1:])
    if not (0 < bw <= 1 and 0 < bh <= 1 and 0 <= cx-bw/2 < cx+bw/2 <= 1
            and 0 <= cy-bh/2 < cy+bh/2 <= 1):
        raise ValueError('Reference box outside image')
    box = [(cx-bw/2)*w, (cy-bh/2)*h, (cx+bw/2)*w, (cy+bh/2)*h]
    before = digest(a.model)
    model = YOLOE(str(a.model))
    opts = dict(imgsz=416, conf=.35, device='cpu', verbose=False, rect=True)
    model.predict(image, refer_image=image,
                  visual_prompts={'bboxes': [box], 'cls': [0]},
                  predictor=YOLOEVPSegPredictor, **opts)
    model.set_classes(['bus door'], model.model.pe.detach().clone())
    original = model.predict(image, **opts)[0]
    a.output.parent.mkdir(parents=True, exist_ok=True)
    model.save(a.output)
    restored = YOLO(str(a.output))
    result = restored.predict(image, **opts)[0]
    restore_parity = (restored.task == 'segment' and restored.names == {0: 'bus door'}
                      and original.boxes.xyxy.shape == result.boxes.xyxy.shape
                      and torch.allclose(original.boxes.xyxy, result.boxes.xyxy, atol=1, rtol=0)
                      and torch.allclose(original.boxes.conf, result.boxes.conf, atol=.001, rtol=0))
    if not restore_parity or digest(a.model) != before:
        raise RuntimeError('Prepared checkpoint restore or base-model integrity failed')
    provenance = dict(base_model=str(a.model), base_model_sha256=before,
                      output_sha256=digest(a.output), ultralytics=ultralytics.__version__,
                      prompt_kind='fixed_visual_reference', reference_row=row,
                      reference_image_sha256=digest(image_path), reference_label_sha256=digest(label_path),
                      manifest_sha256=digest(a.manifest), reference_box=box,
                      checkpoint_restore_parity=True, coordinate_tolerance_px=1,
                      reference_predictions=[dict(box=b, conf=c) for b, c in
                                             zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist())],
                      independent_accuracy_validated=False, jetson_validated=False,
                      note='Assistant bootstrap training reference. Prepared once offline; automatic runtime localization uses no manual per-frame ROI. Same-recording testing remains development evidence.')
    a.output.with_suffix('.source.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    print(json.dumps(provenance, indent=2))


if __name__ == '__main__':
    main()
