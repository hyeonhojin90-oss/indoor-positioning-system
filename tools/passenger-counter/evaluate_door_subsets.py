"""Evaluate frozen test images by source family, without hiding bus failures."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from runtime_threads import configure_model_threads


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--imgsz', type=int, default=416)
    p.add_argument('--cpu-threads', type=int, default=2)
    args = p.parse_args()
    if not args.model.is_file():
        raise ValueError('Completed checkpoint required')
    with args.manifest.open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    groups = {'public': [], 'bus_development': []}
    for row in rows:
        if row['split'] != 'test':
            continue
        family = 'public' if row['session_id'].startswith('public-') else 'bus_development'
        groups[family].append((args.manifest.parent / row['image']).resolve())
    if not all(groups.values()):
        raise ValueError('Both frozen test families are required')
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(__file__).resolve().parent/'runs/settings'))
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent/'runs/matplotlib'))
    from ultralytics import YOLO
    result = {'model_sha256': hashlib.sha256(args.model.read_bytes()).hexdigest(),
              'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              'imgsz': args.imgsz, 'independent_accuracy_validated': False,
              'note': 'Bus test sources have already been reviewed during development; labels require human correction.',
              'subsets': {}}
    for family, images in groups.items():
        image_list = args.output / f'{family}.txt'
        image_list.write_text('\n'.join(x.as_posix() for x in images)+'\n', encoding='utf-8')
        data = args.output / f'{family}.yaml'
        data.write_text(json.dumps({'test': image_list.resolve().as_posix(),
                                    'train': image_list.resolve().as_posix(),
                                    'val': image_list.resolve().as_posix(),
                                    'names': {0: 'door'}}), encoding='utf-8')
        model = YOLO(str(args.model))
        configure_model_threads(model, args.cpu_threads)
        metrics = model.val(data=str(data.resolve()), split='test', device='cpu',
                            imgsz=args.imgsz, workers=0, batch=4,
                            project=str(args.output.resolve()), name=family)
        result['subsets'][family] = {'images': len(images), 'metrics': metrics.results_dict}
        (args.output/'metrics.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
