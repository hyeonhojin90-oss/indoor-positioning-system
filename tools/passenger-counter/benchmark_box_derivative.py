"""Alternating warmed Windows CPU inference timing; no Jetson or pipeline FPS claim."""
import json,time,statistics,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
os.environ.setdefault('MPLCONFIGDIR',str(Path('runs/matplotlib').resolve()))
import cv2
from ultralytics import YOLO
from runtime_threads import configure_model_threads
from export_verified_onnx import compare_detections

models=[YOLO('runs/person-seg-dynamic-onnx-parity-20261001-r2/model.onnx',task='segment'),
        YOLO('runs/segment-trained-box-dynamic-onnx-parity-20261001-r2/model.onnx',task='detect')]
for m in models:configure_model_threads(m,2)
cap=cv2.VideoCapture('data/regression/bus-green-32245403-720.mp4');images=[]
for f in [59,89,180,260,357]:
    cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,img=cap.read();assert ok;images.append((f,img))
cap.release()
kwargs=dict(imgsz=640,conf=.25,iou=.7,classes=[0],device='cpu',rect=True,verbose=False)
for m in models:m.predict(images[0][1],**kwargs)
rows=[]
for repeat in range(3):
    for frame,img in images:
        results={};times={}
        for index in ([0,1] if repeat%2==0 else [1,0]):
            start=time.perf_counter();r=models[index].predict(img,**kwargs)[0];times[index]=time.perf_counter()-start
            results[index]=[dict(box=b,score=s,class_id=c) for b,s,c in zip(r.boxes.xyxy.tolist(),r.boxes.conf.tolist(),r.boxes.cls.int().tolist())]
        parity=compare_detections(results[0],results[1]);assert parity['passed']
        rows.append(dict(frame=frame,repeat=repeat,segment_seconds=times[0],box_seconds=times[1],matched=parity['matched']))
report=dict(rows=rows,median_segment_seconds=statistics.median(r['segment_seconds'] for r in rows),
            median_box_seconds=statistics.median(r['box_seconds'] for r in rows),
            cpu_threads=2,alternating_order=True,all_box_parity_passed=True,
            device='Windows CPU',pipeline_fps_validated=False,jetson_validated=False,
            note='Warm same-frame inference including postprocessing. No rendering/tracking/door/pose; incidental host workload uncontrolled.')
with Path('runs/segment-trained-box-cpu-inference-timing-r2.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
