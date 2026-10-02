"""Observed-frame diagnostic; not a full tracking or accuracy validation."""
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/yolo-settings').resolve()))
import argparse,json,hashlib,cv2
from person_model_family import load
from runtime_threads import configure_model_threads
from rtdetr_duplicate_filter import kept_indices

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--frames',type=int,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 cfg=json.loads(a.config.read_text());model=load(cfg);configure_model_threads(model,2)
 source_hash=hashlib.sha256(a.source.read_bytes()).hexdigest();cap=cv2.VideoCapture(str(a.source));rows=[]
 try:
  for fid in a.frames:
   cap.set(cv2.CAP_PROP_POS_FRAMES,fid);ok,im=cap.read()
   if not ok:raise ValueError('Missing source frame')
   r=model.predict(im,classes=[0],conf=cfg.get('person_conf',.1),imgsz=640,rect=False,device='cpu',verbose=False)[0]
   boxes=r.boxes.xyxy.cpu().tolist();scores=r.boxes.conf.cpu().tolist();classes=r.boxes.cls.int().cpu().tolist()
   keep=kept_indices(boxes,scores,classes,.7)
   rows.append(dict(frame=fid,boxes=boxes,scores=scores,classes=classes,kept_indices=keep,removed=len(boxes)-len(keep)))
 finally:cap.release()
 assert source_hash==hashlib.sha256(a.source.read_bytes()).hexdigest()
 report=dict(source_sha256=source_hash,model_sha256=hashlib.sha256(Path(cfg['person_model']).read_bytes()).hexdigest(),frames=rows,iou_threshold=.7,full_tracking_validated=False,independent_accuracy_validated=False,hardware_validated=False)
 with a.output.open('x') as stream:json.dump(report,stream,indent=2)
 print(json.dumps(dict(frames=len(rows),detections=sum(len(r['boxes']) for r in rows),removed=sum(r['removed'] for r in rows),full_tracking_validated=False)))
if __name__=='__main__':main()
