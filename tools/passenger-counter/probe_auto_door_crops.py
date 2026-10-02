"""Diagnose automatic person/bus crops on full-source saved detections, without GT regions."""
import argparse,hashlib,json,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
import cv2
from ultralytics import YOLO
from runtime_threads import configure_model_threads
from door_selection import passenger_search_regions,select_door
from bus_gate import BusPresenceGate
from audit_completed_run import audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--models',nargs='+',required=True);p.add_argument('--frames',nargs='+',type=int,required=True)
    p.add_argument('--imgsz',type=int,default=640);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    completed=audit(a.run)
    if not completed['complete_source'] or not completed['replay_parity']:raise ValueError('Require full-source audited saved detections')
    a.output.mkdir(parents=True,exist_ok=False)
    s=json.loads((a.run/'summary.json').read_text());c=s['config'];source=Path(s['source'])
    observations={r['frame']:r for r in map(json.loads,(a.run/'tracks.jsonl').read_text().splitlines())}
    bus=YOLO(c['bus_model'],task='detect');configure_model_threads(bus,2)
    models={name:YOLO(path,task='detect') for name,path in (x.split('=',1) for x in a.models)}
    for model in models.values():configure_model_threads(model,2)
    cap=cv2.VideoCapture(str(source));rows=[]
    try:
        for frame_id in a.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,frame_id);ok,frame=cap.read()
            if not ok:raise ValueError('Frame unavailable')
            height,width=frame.shape[:2];people=observations[frame_id]['raw_boxes']
            b=bus.predict(frame,imgsz=640,conf=.05,classes=[5],device='cpu',rect=True,verbose=False)[0]
            gate=BusPresenceGate(**{k:v for k,v in c['bus_gate'].items() if k!='enabled'})
            gate.observe(b.boxes.xyxy.tolist(),b.boxes.cls.tolist(),b.boxes.conf.tolist(),width,height,frame_id/s['source_fps'])
            regions=passenger_search_regions(people,gate.boxes,width,height,max_regions=4)
            for name,model in models.items():
                drawn=frame.copy();candidates=[];detections=[]
                for region in regions:
                    x1,y1,x2,y2=region;crop=frame[y1:y2,x1:x2]
                    pred=model.predict(crop,imgsz=a.imgsz,conf=c.get('door_conf',.35),classes=[0],device='cpu',rect=True,verbose=False)[0]
                    cv2.rectangle(drawn,(x1,y1),(x2,y2),(255,120,0),1)
                    for box,score in zip(pred.boxes.xyxy.tolist(),pred.boxes.conf.tolist()):
                        mapped=[box[0]+x1,box[1]+y1,box[2]+x1,box[3]+y1]
                        w,h=mapped[2]-mapped[0],mapped[3]-mapped[1]
                        accepted=w>0 and h/w>=c.get('min_door_aspect',1) and w*h/(width*height)<=c.get('max_door_area',.6) and gate.accept_door(mapped)
                        detections.append(dict(box=mapped,score=score,region=region,geometry_bus_accepted=accepted))
                        if accepted:candidates.append(mapped)
                        xx1,yy1,xx2,yy2=map(round,mapped);cv2.rectangle(drawn,(xx1,yy1),(xx2,yy2),(0,200,0) if accepted else (0,0,255),2)
                        cv2.putText(drawn,f'{score:.3f}',(xx1,yy1-4),0,.55,(0,200,0),2)
                options={k:v for k,v in c['door_selection'].items() if k!='enabled'}
                chosen=select_door(candidates,people,None,**options)
                row=dict(frame=frame_id,model=name,bus_source=gate.observation_kind,regions=regions,detections=detections,selected=candidates[chosen] if chosen is not None else None)
                rows.append(row);cv2.imwrite(str(a.output/f'{name}-{frame_id}.jpg'),drawn)
                print(name,frame_id,'regions',len(regions),'selected',row['selected'],flush=True)
    finally:cap.release()
    report=dict(source=s['source'],source_sha256=s['source_sha256'],imgsz=a.imgsz,rows=rows,
        model_sha256={name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in (x.split('=',1) for x in a.models)},
        no_oracle_region=True,frozen_person_run=str(a.run),diagnostic_only=True,full_counter_validated=False)
    (a.output/'probe.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
