"""New-source image diagnostic; fixed annotations, no event/field accuracy claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs/settings'))


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def validate_review(review):
    rows=review.get('images')
    if not isinstance(rows,list) or not rows:raise ValueError('Review requires nonempty images list')
    names=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Review image must be an object')
        for key in ('name','sha256','target_box','status'):
            if key not in row:raise ValueError('Review image missing '+key)
        if not isinstance(row['name'],str) or Path(row['name']).name!=row['name'] or row['name'] in names:
            raise ValueError('Review image requires unique local filename')
        names.add(row['name'])
        if not isinstance(row['status'],str) or not row['status']:raise ValueError('Review status is required')
        if not isinstance(row['sha256'],str) or len(row['sha256'])!=64 or any(c not in '0123456789abcdef' for c in row['sha256']):
            raise ValueError('Review requires SHA256 provenance')
        box=row['target_box']
        if box is not None:
            import math
            if not isinstance(box,list) or len(box)!=4 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in box):
                raise ValueError('Review box requires four finite coordinates')
            if not (0<=box[0]<box[2] and 0<=box[1]<box[3]):raise ValueError('Review box must have positive area')
    return rows


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--review',type=Path,required=True)
    p.add_argument('--models',nargs='+',default=[])
    p.add_argument('--grounding',action='store_true')
    p.add_argument('--imgsz',type=int,default=416)
    p.add_argument('--auto-crops',action='store_true')
    p.add_argument('--grounding-prompt',default='a bus door.')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    review=json.loads(a.review.read_text(encoding='utf-8'))
    rows=validate_review(review)
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    from counter import iou,plausible_door
    from bus_gate import BusPresenceGate
    from door_selection import select_door,passenger_search_regions
    from runtime_threads import configure_model_threads
    torch.set_num_threads(2)
    items=[]
    for row in rows:
        path=a.review.parent/row['name']
        if digest(path)!=row['sha256']:raise ValueError('Image provenance mismatch')
        frame=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
        if frame is None:raise ValueError('Cannot decode photograph')
        box=row['target_box']
        if box is not None and (box[2]>frame.shape[1] or box[3]>frame.shape[0]):raise ValueError('Review box exceeds image bounds')
        items.append((row,frame))
    a.output.mkdir(parents=True,exist_ok=False)
    support=YOLO('models/yolo11m.pt')
    configure_model_threads(support,2)
    context=[]
    for row,frame in items:
        pred=support.predict(frame,imgsz=640,classes=[0,5],conf=.05,verbose=False,device='cpu')[0]
        h,w=frame.shape[:2];boxes=pred.boxes.xyxy.tolist();classes=pred.boxes.cls.int().tolist();scores=pred.boxes.conf.tolist()
        gate=BusPresenceGate(min_conf=.4,min_area=.08,max_door_bus_width_ratio=.65)
        gate.observe(boxes,classes,scores,w,h,0)
        people=[b for b,c,s in zip(boxes,classes,scores) if c==0 and s>=.1]
        context.append((gate,people))
    specs=[]
    for spec in a.models:
        name,filename=spec.split('=',1);model=YOLO(filename)
        configure_model_threads(model,2)
        specs.append((name,model,dict(path=filename,sha256=digest(Path(filename)))))
    if a.grounding:
        from grounding_detector import GroundingDoorDetector
        model=GroundingDoorDetector(prompt=a.grounding_prompt)
        specs.append(('grounding',model,model.provenance))
    measures=[]
    for name,model,provenance in specs:
        for (row,frame),(gate,people) in zip(items,context):
            regions=(passenger_search_regions(people,gate.boxes,frame.shape[1],frame.shape[0])
                     if name=='grounding' and a.auto_crops else [])
            extra={'search_regions':regions} if name=='grounding' else {}
            pred=model.predict(frame,imgsz=a.imgsz,conf=.35,classes=[0],rect=True,device='cpu',verbose=False,**extra)[0]
            boxes=pred.boxes.xyxy.tolist();scores=pred.boxes.conf.tolist();h,w=frame.shape[:2]
            candidates=[b for b in boxes if plausible_door(b,w,h,.6,1) and gate.accept_door(b)]
            index=select_door(candidates,people)
            selected=candidates[index] if index is not None else None
            truth=row['target_box']
            measurement=dict(model=name,image=row['name'],target_status=row['status'],raw_boxes=boxes,
                             raw_scores=scores,bus_boxes=gate.boxes,person_boxes=people,
                             gated_candidates=candidates,selected_box=selected,
                             search_regions=regions,
                             selected_iou=iou(truth,selected) if truth and selected else (0 if truth else None),
                             highest_confidence_iou=iou(truth,boxes[0]) if truth and boxes else (0 if truth else None),
                             oracle_best_iou=max((iou(truth,b) for b in boxes),default=0) if truth else None,
                             model_provenance=provenance)
            measures.append(measurement)
            display=frame.copy()
            if truth:cv2.rectangle(display,tuple(truth[:2]),tuple(truth[2:]),(0,255,0),2)
            for b in boxes:cv2.rectangle(display,tuple(map(int,b[:2])),tuple(map(int,b[2:])),(0,180,255),2)
            if selected:cv2.rectangle(display,tuple(map(int,selected[:2])),tuple(map(int,selected[2:])),(255,0,0),3)
            cv2.imencode('.jpg',display)[1].tofile(a.output/(name+'-'+row['name']))
            print(json.dumps(dict(model=name,image=row['name'],raw=len(boxes),selected_iou=measurement['selected_iou'])),flush=True)
    result=dict(review=str(a.review),review_sha256=digest(a.review),measurements=measures,
                imgsz=a.imgsz,grounding_auto_crops=a.auto_crops,grounding_prompt=a.grounding_prompt,
                implementation_sha256=digest(Path(__file__)),
                support_model_sha256=digest(Path('models/yolo11m.pt')),new_source_photos=True,
                training_performed=False,assistant_annotations=True,human_reviewed=False,
                diagnostic_only=True,passenger_accuracy_validated=False,jetson_validated=False,
                note='Static new photographs only. Green=prior annotation, yellow=raw model, blue=bus/person-supported choice. Oracle IoU is diagnostic, not runtime selection. Unlocalizable photo is not a negative label.')
    (a.output/'diagnostic.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':main()
