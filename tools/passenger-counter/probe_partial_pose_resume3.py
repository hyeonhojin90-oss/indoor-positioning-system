"""Inspect all current pose detections before any partial-body runtime adoption."""
import argparse,hashlib,json,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
import cv2
from ultralytics import YOLO
from runtime_threads import configure_model_threads
from partial_pose_observations import recover_observations
from person_anchor import measured_points

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--frames',nargs='+',type=int,required=True);a=p.parse_args()
s=json.loads((a.run/'summary.json').read_text());cfg=s['config'];rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
assert hashlib.sha256(Path(s['source']).read_bytes()).hexdigest()==s['source_sha256']
model=YOLO(cfg['pose_aux_model'],task='pose');configure_model_threads(model,2);cap=cv2.VideoCapture(s['source']);out=[]
try:
    for f in a.frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,img=cap.read();assert ok
        r=model.predict(img,imgsz=cfg['person_imgsz'],conf=.1,device='cpu',verbose=False)[0]
        raw=list(zip(rows[f]['raw_ids'],rows[f]['raw_boxes']))
        pairs,poses,proof=recover_observations(raw,r.boxes.xyxy.tolist(),r.keypoints.data.tolist())
        pts=measured_points(pairs,pairs,poses,cfg)
        out.append(dict(frame=f,original_pose_inferred=rows[f]['pose_aux_inferred'],raw_ids=rows[f]['raw_ids'],raw_boxes=rows[f]['raw_boxes'],recovered_boxes=[b for _,b in pairs],points=pts,proof=proof,pose_boxes=r.boxes.xyxy.tolist(),pose_keypoints=r.keypoints.data.tolist()))
        print(f,[(p['raw_track_id'],p['partial_recovery']) for p in proof if p['partial_recovery']])
finally:cap.release()
with a.output.open('x') as f:json.dump(dict(rows=out,source_sha256=s['source_sha256'],diagnostic_only=True,full_counter_rerun=False,no_guessed_keypoints=True,default_changed=False),f,indent=2)
