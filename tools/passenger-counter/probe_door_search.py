"""Compare prompts and automatic passenger crops on fixed source samples."""
import json
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
import cv2
from ultralytics import YOLO
from grounding_detector import GroundingDoorDetector


def main():
    out=Path('runs/city-door-search-probe-20260930');out.mkdir(exist_ok=False)
    source='data/regression/bus-city-36462986-1280.mp4'
    cap=cv2.VideoCapture(source)
    model=GroundingDoorDetector('models/hf/models--IDEA-Research--grounding-dino-tiny/snapshots/a2bb814dd30d776dcf7e30523b00659f4f141c71')
    people=YOLO('models/yolo11m.pt');rows=[]
    for f in [350,400,440]:
        cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,frame=cap.read();assert ok
        pred=people.predict(frame,classes=[0],conf=.25,verbose=False)[0]
        candidates=pred.boxes.xyxy.tolist()
        # Automatically derived from full-body people; no labelled door coords.
        regions=[]
        for p in candidates:
            w,h=p[2]-p[0],p[3]-p[1]
            if h<80 or h/w<1.5:continue
            region=[max(0,int(p[0]-2*w)),max(0,int(p[1]-h)),min(1280,int(p[2]+2*w)),min(720,int(p[3]+.2*h))]
            if region[2]-region[0]<32 or region[3]-region[1]<32:continue
            regions.append(region)
        for prompt in ['a bus door.','an open bus door.']:
            model.prompt=prompt
            for region in [None]+regions:
                x1,y1,x2,y2=region or [0,0,1280,720]
                result=model.predict(frame[y1:y2,x1:x2],conf=.35)[0]
                boxes=[[b[0]+x1,b[1]+y1,b[2]+x1,b[3]+y1] for b in result.boxes.xyxy.tolist()]
                scores=result.boxes.conf.tolist();r={'frame':f,'prompt':prompt,'crop':region,'boxes':boxes,'scores':scores};rows.append(r)
                print(json.dumps(r),flush=True)
                (out/'detections.json').write_text(json.dumps(rows,indent=2))
    cap.release()


if __name__=='__main__':main()
