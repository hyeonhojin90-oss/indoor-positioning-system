"""Confirm tracked-ID observations equal fresh same-frame detector boxes."""
import argparse,hashlib,json,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
import cv2
from ultralytics import YOLO
from runtime_threads import configure_model_threads
from export_verified_onnx import compare_detections

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
s=json.loads((a.run/'summary.json').read_text());cfg=s['config'];assert cfg['person_measured_boxes']
assert hashlib.sha256(Path(s['source']).read_bytes()).hexdigest()==s['source_sha256']
rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
model=YOLO(cfg['person_model'],task=cfg['person_task']);configure_model_threads(model,2)
cap=cv2.VideoCapture(s['source']);reports=[]
try:
    for frame in [1,27,59,75,89,180,260,357]:
        cap.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,img=cap.read();assert ok
        r=model.predict(img,imgsz=cfg['person_imgsz'],conf=cfg.get('person_conf',.1),iou=.7,classes=[0],rect=cfg.get('person_rect',True),device='cpu',verbose=False)[0]
        actual=[dict(box=b,score=c,class_id=0) for b,c in zip(r.boxes.xyxy.tolist(),r.boxes.conf.tolist())]
        row=rows[frame];tracked=[dict(box=b,score=c,class_id=0) for b,c in zip(row['raw_boxes'],row['raw_confidences'])]
        comparison=compare_detections(tracked,actual,min_iou=.9999,max_score_error=1e-5,max_coordinate_error=.001)
        assert comparison['matched']==len(tracked),'Tracked observation is not an actual current detection'
        reports.append(dict(frame=frame,tracked_observations=len(tracked),full_detector_boxes=len(actual),matched=comparison['matched']))
finally:cap.release()
with a.output.open('x') as f:json.dump(dict(rows=reports,all_current_detections_verified=True,untracked_boxes_may_be_present=True,source_sha256=s['source_sha256'],independent_accuracy_validated=False),f,indent=2)
print('Verified current detection coordinates',sum(r['matched'] for r in reports))
