"""Frozen source-frame door diagnostic; never uses a supplied target region."""
import argparse,hashlib,json,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
import cv2
from ultralytics import YOLO
from runtime_threads import configure_model_threads

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--models',nargs='+',required=True);p.add_argument('--frames',nargs='+',type=int,required=True)
    p.add_argument('--sizes',nargs='+',type=int,default=[416,640]);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    digest=hashlib.sha256(a.source.read_bytes()).hexdigest();cap=cv2.VideoCapture(str(a.source));frames={}
    try:
        for f in a.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,img=cap.read()
            if not ok:raise ValueError(f'Cannot read frame {f}')
            frames[f]=img
    finally:cap.release()
    rows=[]
    for spec in a.models:
        name,path=spec.split('=',1);model=YOLO(path,task='detect');configure_model_threads(model,2)
        model_hash=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for size in a.sizes:
            for f,img in frames.items():
                r=model.predict(img,imgsz=size,conf=.05,classes=[0],rect=True,device='cpu',verbose=False)[0]
                boxes=r.boxes.xyxy.tolist();scores=r.boxes.conf.tolist()
                row=dict(model=name,model_sha256=model_hash,frame=f,imgsz=size,boxes=boxes,scores=scores)
                rows.append(row)
                drawn=img.copy()
                for box,score in zip(boxes,scores):
                    x1,y1,x2,y2=map(round,box);color=(0,200,0) if score>=.35 else (0,0,255)
                    cv2.rectangle(drawn,(x1,y1),(x2,y2),color,2)
                    cv2.putText(drawn,f'{score:.3f}',(x1,y1-3),0,.55,color,2)
                cv2.imwrite(str(a.output/f'{name}-{size}-{f}.jpg'),drawn)
                print(name,size,f,[round(s,3) for s in scores],flush=True)
    report=dict(source=str(a.source),source_sha256=digest,rows=rows,conf=.05,
                acquisition_conf=.35,diagnostic_only=True,training_used=False,oracle_region_used=False)
    (a.output/'probe.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
