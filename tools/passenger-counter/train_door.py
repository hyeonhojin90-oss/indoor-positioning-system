"""Fine-tune a nano detector from a manually reviewed YOLO dataset."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from runtime_threads import configure_model_threads


def prepare(manifest, output):
    """Manifest image paths must use YOLO images/... -> labels/... layout.

    Split by original recording/session, never random adjacent video frames.
    """
    manifest = Path(manifest).resolve()
    with manifest.open(encoding='utf-8-sig') as source:
        rows = list(csv.DictReader(source))
    groups, hashes, label_hashes, splits = {}, {}, {}, {'train':[], 'val':[], 'test':[]}
    for r in rows:
        split, group = r['split'], r['session_id']
        if split not in splits or not group.strip():
            raise ValueError('Need train/val/test and a recording session_id')
        if group in groups and groups[group] != split:
            raise ValueError(f'Session leakage: {group}')
        groups[group] = split
        image = (manifest.parent/r['image']).resolve()
        parts = list(image.parts)
        if 'images' not in parts:
            raise ValueError('Use dataset/images/... and matching dataset/labels/...')
        parts[len(parts)-1-parts[::-1].index('images')] = 'labels'
        label = Path(*parts).with_suffix('.txt')
        if not image.is_file() or not label.is_file():
            raise ValueError(f'Missing image or reviewed label: {image}')
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if digest in hashes:
            raise ValueError(f'Duplicate image: {image}')
        hashes[digest] = split
        label_hashes[label.as_posix()] = hashlib.sha256(label.read_bytes()).hexdigest()
        seen_labels=set()
        for line in label.read_text().splitlines():
            values = list(map(float,line.split()))
            if len(values) != 5 or values[0] != 0 or not all(0<=v<=1 for v in values[1:]) or min(values[3:]) <= 0:
                raise ValueError(f'Expected single-class door YOLO label: {label}')
            _,x,y,w,h=values
            if min(x-w/2,y-h/2)<-1e-6 or max(x+w/2,y+h/2)>1+1e-6:
                raise ValueError(f'Door label extends outside image: {label}')
            if tuple(values) in seen_labels:
                raise ValueError(f'Duplicate door label: {label}')
            seen_labels.add(tuple(values))
        splits[split].append(image.as_posix())
    if not all(splits.values()):
        raise ValueError('All three splits need independent reviewed images')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for split, paths in splits.items():
        (output/f'{split}.txt').write_text('\n'.join(paths)+'\n',encoding='utf-8')
    data = {s:(output/f'{s}.txt').as_posix() for s in splits}
    data['names'] = {0:'door'}
    # JSON is valid YAML and accepted by Ultralytics.
    path = output/'dataset.yaml'
    path.write_text(json.dumps(data,indent=2),encoding='utf-8')
    (output/'provenance.json').write_text(json.dumps({'rows':rows,'sha256':hashes,
        'label_sha256':label_hashes},indent=2),encoding='utf-8')
    return path


def repeat_bus_training(manifest, data, repeat):
    """Increase bus sampling weight only; repetitions are not new observations."""
    if type(repeat) is not int or not 1 <= repeat <= 32:
        raise ValueError('bus-train-repeat must be 1..32')
    if repeat == 1:
        return
    manifest = Path(manifest).resolve()
    with manifest.open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    train = [row for row in rows if row['split'] == 'train']
    public = [row for row in train if row['session_id'].startswith('public-')]
    bus = [row for row in train if not row['session_id'].startswith('public-')]
    if not public or not bus:
        raise ValueError('Reweighting requires both public- and bus training sessions')
    paths = [(manifest.parent/row['image']).resolve().as_posix()
             for row in train for _ in range(1 if row in public else repeat)]
    (Path(data).parent/'train.txt').write_text('\n'.join(paths)+'\n',encoding='utf-8')
    (Path(data).parent/'sampling.json').write_text(json.dumps({
        'bus_repeat':repeat,'unique_public_train_images':len(public),
        'unique_bus_train_images':len(bus),'training_list_entries':len(paths),
        'validation_test_unchanged':True,
        'note':'Repeated training paths change sampling weight; no new independent images.'
    },indent=2),encoding='utf-8')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--device',default='0')
    p.add_argument('--epochs',type=int,default=50)
    p.add_argument('--batch',type=int,default=4)
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--imgsz',type=int,default=640)
    p.add_argument('--cpu-threads',type=int,help='Bound CPU inference/training threads (1..32)')
    p.add_argument('--initial-model',default='yolo11n.pt')
    p.add_argument('--nominal-batch',type=int,default=64,
                   help='Gradient accumulation target; use batch for a tiny bootstrap experiment')
    p.add_argument('--patience',type=int,default=10)
    p.add_argument('--bus-train-repeat',type=int,default=1,
                   help='Sampling weight of bus train images in a mixed public/bus manifest; no new images')
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--skip-test',action='store_true',help='Development training: validation only, preserve test for a final evaluation')
    p.add_argument('--translate',type=float,default=.1)
    p.add_argument('--scale',type=float,default=.5)
    p.add_argument('--fliplr',type=float,default=0.)
    p.add_argument('--optimizer',choices=['auto','AdamW','SGD'],default='auto')
    p.add_argument('--lr0',type=float,default=.01)
    p.add_argument('--freeze',type=int,default=0,help='Freeze this many initial layers for a retention comparison')
    p.add_argument('--warmup-epochs',type=float,default=3.)
    args = p.parse_args()
    if args.cpu_threads is not None and not 1<=args.cpu_threads<=32:
        raise ValueError('cpu-threads must be 1..32')
    if args.nominal_batch<1 or args.patience<0:
        raise ValueError('Invalid nominal-batch/patience')
    if not all(0<=x<=1 for x in (args.translate,args.scale,args.fliplr)):
        raise ValueError('Invalid augmentation range')
    if not 0<args.lr0<=1 or not 0<=args.freeze<=20 or not 0<=args.warmup_epochs<=100:
        raise ValueError('Invalid optimizer controls')
    data = prepare(args.manifest,args.output)
    repeat_bus_training(args.manifest,data,args.bus_train_repeat)
    if not args.prepare_only:
        os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(__file__).resolve().parent/'runs'/'settings'))
        os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'runs'/'matplotlib'))
        from ultralytics import YOLO
        if args.cpu_threads is not None:
            import torch
            torch.set_num_threads(args.cpu_threads)
        model = YOLO(args.initial_model)
        configure_model_threads(model,args.cpu_threads)
        from feature_cache_proof import snapshot_files, require_unchanged
        manifest_path = Path(args.manifest).resolve()
        with manifest_path.open(encoding='utf-8-sig') as stream:
            training_rows = list(csv.DictReader(stream))
        image_paths = [(manifest_path.parent / row['image']).resolve() for row in training_rows]
        label_paths = []
        for image in image_paths:
            parts = list(image.parts)
            parts[len(parts)-1-parts[::-1].index('images')] = 'labels'
            label_paths.append(Path(*parts).with_suffix('.txt'))
        checkpoint = Path(model.ckpt_path)
        snapshot = snapshot_files([manifest_path, Path(__file__).resolve(), Path('runtime_threads.py'),
            Path('feature_cache_proof.py'), checkpoint, data, data.parent/'train.txt',
            data.parent/'val.txt', data.parent/'test.txt'] + image_paths + label_paths)
        (Path(args.output)/'training-inputs.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
        model.train(data=str(data),epochs=args.epochs,batch=args.batch,imgsz=args.imgsz,
                    device=args.device,workers=args.workers,seed=42,patience=args.patience,nbs=args.nominal_batch,
                    optimizer=args.optimizer,lr0=args.lr0,freeze=args.freeze,warmup_epochs=args.warmup_epochs,
                    project=str(Path(args.output).resolve()/'training'),name='door',
                    fliplr=args.fliplr,translate=args.translate,scale=args.scale,mosaic=.5,close_mosaic=10)
        require_unchanged(snapshot)
        if args.skip_test:
            (Path(args.output)/'training-completion.json').write_text(json.dumps(dict(
                inputs_unchanged_after_training=True, test_evaluated=False,
                checkpoint_selected_by='validation', best=str(model.trainer.best),
                independent_accuracy_validated=False, jetson_validated=False),indent=2),encoding='utf-8')
            return
        # No tuning against test split. Evaluate best validation checkpoint once.
        best = YOLO(str(model.trainer.best))
        configure_model_threads(best,args.cpu_threads)
        metrics = best.val(data=str(data),split='test',device=args.device,
                           imgsz=args.imgsz, workers=args.workers,
                           project=str(Path(args.output).resolve()/'evaluation'),name='test')
        (Path(args.output)/'test-metrics.json').write_text(
            json.dumps(metrics.results_dict,indent=2),encoding='utf-8')
        require_unchanged(snapshot)
        (Path(args.output)/'training-completion.json').write_text(json.dumps(dict(
            inputs_unchanged_after_training=True, test_evaluated=True,
            checkpoint_selected_by='validation', best=str(model.trainer.best),
            independent_accuracy_validated=False, jetson_validated=False),indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
