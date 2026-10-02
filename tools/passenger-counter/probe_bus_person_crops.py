"""Diagnostic: actual current COCO bus detections define person search crops."""
import argparse
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
os.environ.setdefault('MPLCONFIGDIR',str(Path('runs/matplotlib').resolve()))


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--frames',type=int,nargs='+',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    import cv2
    from ultralytics import YOLO
    from bus_person_regions import search_regions,restore_observation
    from feature_cache_proof import snapshot_files,require_unchanged
    from runtime_threads import configure_model_threads
    model_path=Path('models/yolo11m.pt')
    snapshot=snapshot_files([a.source,model_path,Path(__file__),Path('bus_person_regions.py'),Path('runtime_threads.py')])
    model=YOLO(str(model_path));configure_model_threads(model,2)
    a.output.mkdir(parents=True,exist_ok=False);cap=cv2.VideoCapture(str(a.source));rows=[]
    try:
        for fid in a.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,fid);ok,frame=cap.read()
            if not ok:raise ValueError('Missing actual video frame')
            h,w=frame.shape[:2]
            detected=model.predict(frame,imgsz=640,conf=.1,classes=[0,5],device='cpu',verbose=False)[0]
            bus=[b for b,c,s in zip(detected.boxes.xyxy.tolist(),detected.boxes.cls.tolist(),detected.boxes.conf.tolist())
                 if c==5 and s>=.4 and (b[2]-b[0])*(b[3]-b[1])/(w*h)>=.08]
            regions=search_regions(bus,w,h);candidates=[]
            for region in regions:
                x1,y1,x2,y2=region
                result=model.predict(frame[y1:y2,x1:x2],imgsz=640,conf=.1,classes=[0],rect=True,device='cpu',verbose=False)[0]
                for b,s in zip(result.boxes.xyxy.tolist(),result.boxes.conf.tolist()):
                    restored=restore_observation(b,region,w,h)
                    candidates.append(dict(box=restored,crop_box=b,score=s,rejected=restored is None))
                    if restored:
                        bx1,by1,bx2,by2=map(round,restored)
                        cv2.rectangle(frame,(bx1,by1),(bx2,by2),(0,200,0),1)
                        cv2.putText(frame,f'{s:.2f}',(bx1,max(12,by1-3)),0,.35,(0,200,0),1)
                cv2.rectangle(frame,(x1,y1),(x2,y2),(0,0,255),1)
            row=dict(frame=fid,bus_boxes=bus,regions=regions,candidates=candidates);rows.append(row)
            if not cv2.imwrite(str(a.output/f'frame-{fid}.jpg'),frame):raise ValueError('Cannot save actual review')
            print(json.dumps(row),flush=True)
    finally:cap.release()
    require_unchanged(snapshot)
    report=dict(source=str(a.source),source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),rows=rows,
        input_snapshot_sha256=snapshot,inputs_unchanged_after_work=True,oracle_roi_used=False,
        diagnostic_only=True,tracking_rerun=False,jetson_validated=False)
    (a.output/'probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
