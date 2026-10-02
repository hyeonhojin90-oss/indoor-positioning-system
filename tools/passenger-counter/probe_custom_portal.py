"""Save exact custom-model predictions on fixed development source frames."""
import argparse
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs'/'settings'))
import cv2
import torch
from ultralytics import YOLO
from runtime_threads import configure_model_threads


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True)
    p.add_argument('--source',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--frames',type=int,nargs='+',required=True);p.add_argument('--imgsz',type=int,default=640)
    p.add_argument('--conf',type=float,default=.1)
    p.add_argument('--classes',type=int,nargs='+');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);torch.set_num_threads(2)
    model=YOLO(str(a.model));configure_model_threads(model,2);cap=cv2.VideoCapture(a.source);rows=[]
    try:
        for f in a.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,frame=cap.read()
            if not ok:raise ValueError('Cannot decode requested frame')
            result=model.predict(frame,imgsz=a.imgsz,conf=a.conf,classes=a.classes,device='cpu',verbose=False)[0]
            row={'frame':f,'boxes':result.boxes.xyxy.tolist(),
                 'scores':result.boxes.conf.tolist(),'classes':result.boxes.cls.int().tolist()}
            rows.append(row)
            if not cv2.imwrite(str(a.output/f'frame-{f}.jpg'),result.plot()):raise ValueError('Cannot write image')
    finally:cap.release()
    (a.output/'detections.json').write_text(json.dumps({'model':str(a.model),
        'model_sha256':hashlib.sha256(a.model.read_bytes()).hexdigest(),'names':model.names,
        'source':a.source,'source_sha256':hashlib.sha256(Path(a.source).read_bytes()).hexdigest(),
        'imgsz':a.imgsz,'conf':a.conf,'rows':rows,'development_only':True},indent=2))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
