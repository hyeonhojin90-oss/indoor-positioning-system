"""Compare person models/trackers against one completed, frozen door trace."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from replay_counter import replay_rows
from tracking_profile import resolve_tracker
from runtime_threads import configure_model_threads, backend_runtime_info
from person_anchor import validate_anchor_config,measured_points


def load_reference(run_dir, source):
    summary = json.loads((run_dir/'summary.json').read_text(encoding='utf-8'))
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != summary.get('source_sha256'):
        raise ValueError('Source video does not match the reference door run')
    with (run_dir/'tracks.jsonl').open(encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream]
    if len(rows) != summary['frames'] or any(row['frame'] != i for i,row in enumerate(rows)):
        raise ValueError('Reference run is incomplete or out of order')
    if any('door_generation' not in row for row in rows):
        raise ValueError('Reference trace has no door_generation; rerun the source with current run.py')
    return summary, rows, source_hash


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--reference-run', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--person-model', required=True)
    p.add_argument('--tracker', choices=['bytetrack.yaml','botsort.yaml'],
                   default='bytetrack.yaml')
    p.add_argument('--crop', type=float, nargs=4, metavar=('X1','Y1','X2','Y2'),
                   help='Optional normalized camera ROI; log boxes in full-frame pixels')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--door-crop', action='store_true',
                   help='Automatic crop from frozen door geometry; resets tracker when crop moves')
    p.add_argument('--device', default='cpu')
    p.add_argument('--max-frames', type=int, default=0)
    p.add_argument('--imgsz', type=int, help='Override person input size for comparison')
    args = p.parse_args()
    if args.door_crop and args.crop:
        raise ValueError('Choose door-crop or fixed crop')
    if args.crop and not (0 <= args.crop[0] < args.crop[2] <= 1
                          and 0 <= args.crop[1] < args.crop[3] <= 1):
        raise ValueError('Invalid normalized crop')
    if args.max_frames < 0:
        raise ValueError('max-frames must be nonnegative')
    if args.imgsz is not None and args.imgsz < 32:
        raise ValueError('imgsz must be at least 32')
    reference, frozen_rows, source_hash = load_reference(args.reference_run,args.source)
    cfg = json.loads(args.config.read_text(encoding='utf-8-sig'))
    cfg['person_model']=args.person_model
    anchor_kind=validate_anchor_config(cfg)
    person_class=cfg.get('person_class_id',0)
    if type(person_class) is not int or person_class<0:
        raise ValueError('person_class_id must be a nonnegative integer')
    implementation_hashes={name:hashlib.sha256(Path(name).read_bytes()).hexdigest()
        for name in ('retrack_people.py','counter.py','replay_counter.py',
                     'tracking_profile.py','runtime_threads.py','track_bridge.py','person_anchor.py','multi_anchor_counter.py')}
    os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs'/'settings'))
    import cv2
    if 'cpu_threads' in cfg:
        if type(cfg['cpu_threads']) is not int or not 1<=cfg['cpu_threads']<=32:
            raise ValueError('cpu_threads must be 1..32')
        import torch
        torch.set_num_threads(cfg['cpu_threads'])
    from ultralytics import YOLO
    model = YOLO(args.person_model)
    configure_model_threads(model,cfg.get('cpu_threads'))
    cap = cv2.VideoCapture(str(args.source))
    if not cap.isOpened():
        raise RuntimeError('Cannot open source video')
    args.output.mkdir(parents=True,exist_ok=False)
    tracker=resolve_tracker(args.tracker,cfg.get('person_tracker_options'),args.output)
    bridge=None;bridge_generation=None;bridge_events=[]
    if cfg.get('track_bridge',{}).get('enabled',False):
        from track_bridge import NestedTrackBridge
        bridge=NestedTrackBridge(**{k:v for k,v in cfg['track_bridge'].items() if k!='enabled'})
    rows = []
    previous_region=None;crop_resets=0
    started = time.perf_counter()
    # An interrupted comparison retains partial evidence but no completion summary.
    trace_stream=(args.output/'tracks.jsonl').open('x',encoding='utf-8')
    try:
        for ref in frozen_rows[:args.max_frames or None]:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f'Video ended before reference frame {ref["frame"]}')
            h,w = frame.shape[:2]
            x1,y1,x2,y2 = (0,0,w,h) if not args.crop else (
                round(args.crop[0]*w),round(args.crop[1]*h),
                round(args.crop[2]*w),round(args.crop[3]*h))
            if args.door_crop and ref['door']:
                dx1,dy1,dx2,dy2=ref['door'];dw,dh=dx2-dx1,dy2-dy1
                x1,y1,x2,y2=(max(0,round(dx1-.75*dw)),max(0,round(dy1-.15*dh)),
                             min(w,round(dx2+.75*dw)),min(h,round(dy2+.65*dh)))
            region=(x1,y1,x2,y2)
            if args.door_crop and previous_region is not None and region!=previous_region:
                # Tracker coordinates are crop-relative. A changed transform
                # must not match unrelated local coordinates across crops.
                for tracking in getattr(model.predictor,'trackers',[]):tracking.reset()
                crop_resets+=1
            previous_region=region
            result = model.track(frame[y1:y2,x1:x2],persist=True,tracker=tracker,
                                 classes=[person_class],conf=cfg.get('person_conf',.1),
                                 imgsz=args.imgsz or cfg.get('person_imgsz',cfg.get('imgsz',640)),
                                 rect=cfg.get('person_rect',True),
                                 device=args.device,verbose=False)[0]
            ids = result.boxes.id.int().cpu().tolist() if result.boxes.id is not None else []
            boxes = result.boxes.xyxy.cpu().tolist()
            boxes = [[b[0]+x1,b[1]+y1,b[2]+x1,b[3]+y1] for b in boxes]
            if not ids:
                boxes = []
            elif len(ids) != len(boxes):
                raise RuntimeError('Tracker returned partially missing IDs')
            raw_ids,raw_boxes=ids,boxes
            poses={}
            if anchor_kind in ('pose_ankle','pose_dual'):
                if result.keypoints is None:raise ValueError('Pose ankle requires a keypoint model')
                data=result.keypoints.data.cpu().tolist()
                poses={tid:[[x+x1,y+y1,c] for x,y,c in k] for tid,k in zip(ids,data)}
            if bridge is not None:
                if bridge_generation!=ref['door_generation'] or ref['door'] is None:
                    bridge.reset();bridge_generation=ref['door_generation']
                before=len(bridge.audit)
                pairs=bridge.update(list(zip(ids,boxes)),ref['time_s'],ref['door'])
                ids=[i for i,b in pairs];boxes=[b for i,b in pairs]
                bridge_events.extend(dict(e,frame=ref['frame']) for e in bridge.audit[before:])
            points=measured_points(list(zip(ids,boxes)),list(zip(raw_ids,raw_boxes)),poses,cfg)
            rows.append({'frame':ref['frame'],'time_s':ref['time_s'],
                         'door':ref['door'],'door_generation':ref['door_generation'],
                         'raw_ids':raw_ids,'raw_boxes':raw_boxes,
                         'person_region':region,
                         'ids':ids,'boxes':boxes,'points':points,
                         **({'raw_keypoints':poses} if anchor_kind in ('pose_ankle','pose_dual') else {})})
            trace_stream.write(json.dumps(rows[-1])+'\n')
            if ref['frame']%30==0:
                trace_stream.flush()
                print(f"frame={ref['frame']} reference_frames={reference['frames']} people={len(ids)}",flush=True)
    finally:
        trace_stream.close()
        cap.release()
    elapsed = time.perf_counter()-started
    replay = replay_rows(rows,cfg)
    summary = {'source':str(args.source),'source_sha256':source_hash,
               'reference_run':str(args.reference_run),'reference_frames':reference['frames'],
               'person_model':args.person_model,'tracker':args.tracker,
               'tracker_options':cfg.get('person_tracker_options'),'crop':args.crop,
               'door_crop':args.door_crop,'crop_tracker_resets':crop_resets,
               'config':cfg,
               'imgsz':args.imgsz or cfg.get('person_imgsz',cfg.get('imgsz',640)),
               'frames':len(rows),'elapsed_s':elapsed,'processed_fps':len(rows)/max(elapsed,.001),
               **replay,'track_bridge_events':bridge_events,
               'frozen_door_experiment':True,'accuracy_validated':False,
               'implementation_sha256':implementation_hashes,
               'model_sha256':{'person_model':hashlib.sha256(Path(args.person_model).read_bytes()).hexdigest()},
               'reference_summary_sha256':hashlib.sha256((args.reference_run/'summary.json').read_bytes()).hexdigest(),
               'backend_execution':{'people':backend_runtime_info(model)},
               'jetson_validated':False}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (args.output/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in replay['events']),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('frames','counts','events','processed_fps')},indent=2))


if __name__ == '__main__':
    main()
