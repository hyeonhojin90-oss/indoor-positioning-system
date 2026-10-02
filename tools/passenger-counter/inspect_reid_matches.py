"""Observe native-feature association costs without changing tracker decisions."""
import argparse,hashlib,json,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs'/'settings'))
import cv2,numpy as np
from ultralytics import YOLO
from ultralytics.trackers.bot_sort import BOTSORT
from ultralytics.trackers.track import TRACKER_MAP
from ultralytics.trackers.utils import matching
from tracking_profile import resolve_tracker
from runtime_threads import configure_model_threads

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-frames',type=int,default=130);p.add_argument('--track-ids',type=int,nargs='+',default=[3,18]);p.add_argument('--reference-run',type=Path);a=p.parse_args()
    if not 1<=a.max_frames<=300:raise ValueError('Bound this diagnostic to 1..300 frames')
    cfg=json.loads(a.config.read_text());options=cfg.get('person_tracker_options',{})
    if cfg.get('person_tracker')!='botsort.yaml' or options.get('with_reid') is not True or not cfg['person_model'].endswith('.pt'):
        raise ValueError('Native PyTorch detector-feature ReID configuration required')
    a.output.mkdir(parents=True,exist_ok=False);costs=[];rows=[]
    class AuditedBOTSORT(BOTSORT):
        def get_dists(self,tracks,detections):
            selected=super().get_dists(tracks,detections)
            if len(tracks) and len(detections):
                appearance=matching.embedding_distance(tracks,detections)/2
                overlap=matching.iou_distance(tracks,detections)
                for i,track in enumerate(tracks):
                    if track.track_id not in a.track_ids:continue
                    for j,det in enumerate(detections):
                        costs.append(dict(frame=self.frame_id-1,track_id=track.track_id,detection_index=int(det.idx),detection_box=det.xyxy.tolist(),detection_score=float(det.score),iou_cost=float(overlap[i,j]),appearance_cost=float(appearance[i,j]),selected_cost=float(selected[i,j])))
            return selected
    original=TRACKER_MAP['botsort'];TRACKER_MAP['botsort']=AuditedBOTSORT
    cap=cv2.VideoCapture(str(a.source));model=YOLO(cfg['person_model'],task='detect');configure_model_threads(model,cfg.get('cpu_threads',2))
    tracker=resolve_tracker('botsort.yaml',options,a.output)
    try:
        if not cap.isOpened():raise ValueError('Cannot open source')
        for frame_id in range(a.max_frames):
            ok,frame=cap.read()
            if not ok:raise ValueError('Source shorter than diagnostic')
            person_class=cfg.get('person_class_id',0)
            classes=[person_class,5] if cfg.get('bus_gate',{}).get('enabled') and not cfg.get('bus_model') else [person_class]
            result=model.track(frame,persist=True,tracker=tracker,classes=classes,conf=cfg.get('person_conf',.1),imgsz=cfg.get('person_imgsz',640),rect=cfg.get('person_rect',True),device='cpu',verbose=False)[0]
            assigned={track.track_id:int(track.idx) for track in model.predictor.trackers[0].tracked_stracks}
            rows.append(dict(frame=frame_id,ids=[] if result.boxes.id is None else result.boxes.id.int().tolist(),boxes=result.boxes.xyxy.tolist(),assigned_detection_indices=assigned))
    finally:cap.release();TRACKER_MAP['botsort']=original
    with (a.output/'association-costs.json').open('x') as f:json.dump(costs,f,indent=2)
    with (a.output/'raw-tracks.jsonl').open('x') as f:
        for row in rows:f.write(json.dumps(row)+'\n')
    parity=None
    if a.reference_run:
        reference=json.loads((a.reference_run/'summary.json').read_text())
        if reference['source_sha256']!=hashlib.sha256(a.source.read_bytes()).hexdigest() or reference['config']!=cfg:raise ValueError('Reference source/config mismatch')
        expected=[json.loads(x) for x in (a.reference_run/'tracks.jsonl').read_text().splitlines()][:len(rows)]
        parity=len(expected)==len(rows) and all(x['ids']==y['raw_ids'] and np.allclose(x['boxes'],y['raw_boxes'],atol=1,rtol=0) for x,y in zip(rows,expected))
    with (a.output/'diagnostic.json').open('x') as f:json.dump(dict(source=str(a.source),source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),frames=len(rows),config=cfg,diagnostic_only=True,tracker_decisions_unchanged=True,reference_raw_parity=parity,complete_source=False,accuracy_validated=False),f,indent=2)
    print(json.dumps(dict(frames=len(rows),cost_rows=len(costs),reference_raw_parity=parity)))
    if parity is False:raise ValueError('Instrumented raw tracks differ from reference')
