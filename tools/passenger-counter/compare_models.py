"""Same decoded frames for model-size/resolution comparison; no training here."""
import json
import os
from pathlib import Path
import time
import cv2
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
from ultralytics import YOLO, YOLOWorld


def main():
    out=Path('runs/size-comparison');out.mkdir(exist_ok=False)
    c=cv2.VideoCapture('data/bus-3132290.mp4')
    frames={}
    for n in (0,10,20,30,35,40,45,60,90):
        c.set(cv2.CAP_PROP_POS_FRAMES,n);ok,f=c.read()
        if ok:frames[n]=f
    c.release()
    summary=[]
    jobs=[('person-n','yolo11n.pt',False),('person-m','models/yolo11m.pt',False),
          ('door-s','yolov8s-worldv2.pt',True),('door-l','models/yolov8l-worldv2.pt',True)]
    for tag,path,world in jobs:
        model=YOLOWorld(path) if world else YOLO(path)
        if world:model.set_classes(['door','bus','window','person'])
        for size in (640,960):
            start=time.perf_counter()
            for n,frame in frames.items():
                r=model.predict(frame,imgsz=size,conf=.1,classes=None if world else [0],verbose=False)[0]
                det=[{'box':b,'confidence':s,'class_id':k} for b,s,k in zip(r.boxes.xyxy.cpu().tolist(),r.boxes.conf.cpu().tolist(),r.boxes.cls.int().cpu().tolist())]
                summary.append({'model':tag,'size':size,'frame':n,'detections':det})
                if n in (0,40):r.save(str(out/f'{tag}-{size}-{n}.jpg'))
            print(tag,size,round(time.perf_counter()-start,2),flush=True)
            (out/'detections.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')


if __name__=='__main__':main()
