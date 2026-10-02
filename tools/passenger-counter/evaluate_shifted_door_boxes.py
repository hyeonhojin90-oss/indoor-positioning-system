"""Door-only development diagnostic against unchanged bootstrap rectangles."""
import argparse,csv,hashlib,json,re,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs'/'settings'))
import cv2
import torch
from ultralytics import YOLO
from counter import iou
from runtime_threads import configure_model_threads


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--left',type=Path,required=True)
    p.add_argument('--right',type=Path,required=True);p.add_argument('--models',nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    torch.set_num_threads(2);base_hash=digest(a.base)
    rows=list(csv.DictReader(a.manifest.open(encoding='utf-8-sig')))
    rows=[r for r in rows if r['source_sha256']==base_hash]
    if not rows:raise ValueError('No bootstrap rows for base source')
    labels=[]
    for row in rows:
        image=Path(row['image']);label=a.manifest.parent/'labels'/image.with_suffix('.txt').name
        values=label.read_text().split()
        if len(values)!=5 or values[0]!='0':raise ValueError('Exactly one bootstrap door label required')
        cx,cy,w,h=map(float,values[1:]);fid=int(re.search(r'-(\d+)\.jpg$',image.name)[1])
        labels.append(dict(frame=fid,xyxy=[cx-w/2,cy-h/2,cx+w/2,cy+h/2],
                           label_sha256=digest(label),review_status=row['review_status'],split=row['split']))
    sources=[('base',a.base,0)]
    for name,path in [('left',a.left),('right',a.right)]:
        meta=json.loads(path.with_suffix('.source.json').read_text())
        if meta['source_sha256']!=base_hash or meta['output_sha256']!=digest(path):
            raise ValueError('Derived video provenance mismatch')
        if (name=='left' and meta['dx']>=0) or (name=='right' and meta['dx']<=0):
            raise ValueError('Incorrect shift direction')
        sources.append((name,path,meta['dx']))
    frames=[]
    for scene,path,dx in sources:
        cap=cv2.VideoCapture(str(path))
        try:
            if not cap.isOpened():raise ValueError('Cannot open source')
            for label in labels:
                cap.set(cv2.CAP_PROP_POS_FRAMES,label['frame']);ok,image=cap.read()
                if not ok:raise ValueError('Missing labeled frame')
                h,w=image.shape[:2];b=label['xyxy']
                gt=[max(0,min(w,b[0]*w+dx)),b[1]*h,max(0,min(w,b[2]*w+dx)),b[3]*h]
                frames.append((scene,label['frame'],image,gt))
        finally:cap.release()
    results={}
    for spec in a.models:
        name,filename=spec.split('=',1);path=Path(filename);before=digest(path)
        model=YOLO(str(path),task='detect');configure_model_threads(model,2);measures=[]
        for scene,fid,image,gt in frames:
            result=model.predict(image,classes=[0],imgsz=416,rect=True,conf=.35,device='cpu',verbose=False)[0]
            boxes=result.boxes.xyxy.tolist();scores=result.boxes.conf.tolist()
            top=boxes[0] if boxes else None
            # The best-overlap result uses known labels and is diagnostic only.
            best=max(boxes,key=lambda b:iou(gt,b)) if boxes else None
            measures.append(dict(scene=scene,frame=fid,bootstrap_gt=gt,detection_count=len(boxes),
                                 highest_confidence_box=top,highest_confidence_score=scores[0] if scores else None,
                                 top_iou=iou(gt,top) if top else 0,
                                 top_bottom_error_px=top[3]-gt[3] if top else None,
                                 oracle_best_iou=iou(gt,best) if best else 0))
        if before!=digest(path):raise ValueError('Weights changed during diagnostic')
        results[name]=dict(model=str(path),sha256=before,measurements=measures)
    output=dict(manifest=str(a.manifest),manifest_sha256=digest(a.manifest),labels=labels,
                source_hashes={name:digest(path) for name,path,_ in sources},models=results,
                diagnostic_only=True,independent_validation=False,
                note='Training bootstrap rectangles and derived shifts. Assistant annotations, not new human ground truth; oracle matching is not runtime selection or end-to-end accuracy.')
    with a.output.open('x') as stream:json.dump(output,stream,indent=2)
    for name,item in results.items():
        for scene,_,_ in sources:
            selected=[x for x in item['measurements'] if x['scene']==scene]
            print(name,scene,'mean_top_iou',round(sum(x['top_iou'] for x in selected)/len(selected),3),
                  'bottom_errors',[round(x['top_bottom_error_px'],1) if x['top_bottom_error_px'] is not None else None for x in selected])

if __name__=='__main__':main()
