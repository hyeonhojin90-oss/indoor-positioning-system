"""Known-object and checkpoint preparation sanity check, not passenger accuracy."""
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs/settings'))

def main():
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    torch.set_num_threads(2)
    root=Path('runs/yoloe-preparation-sanity-r2')
    root.mkdir(exist_ok=False)
    source=Path('data/commons-door-photos-20261001-r2/vancouver-boarding-20111126.jpg')
    im=cv2.imdecode(np.fromfile(source,dtype=np.uint8),cv2.IMREAD_COLOR)
    results=[]
    for name,filename in [('base','models/yoloe-11s-seg.pt'),
                          ('prepared-person','models/yoloe-11s-person-text-sanity-r2.pt'),
                          ('prepared-door','models/yoloe-11s-door-text-r2.pt'),
                          ('coco-small','models/yolo11s-seg.pt')]:
        model=YOLO(filename)
        people=[int(k) for k,v in model.names.items() if v=='person']
        for size in [416,640]:
            pred=model.predict(im,imgsz=size,conf=.1,classes=people or [0],device='cpu',verbose=False)[0]
            r=dict(name=name,imgsz=size,conf=.1,classes=people or [0],names=model.names,
                   count=len(pred.boxes),scores=pred.boxes.conf.tolist(),boxes=pred.boxes.xyxy.tolist(),
                   model_sha256=hashlib.sha256(Path(filename).read_bytes()).hexdigest())
            results.append(r)
            ok,encoded=cv2.imencode('.jpg',pred.plot());assert ok
            (root/f'{name}-{size}.jpg').write_bytes(encoded.tobytes())
            print(name,size,r['count'],r['scores'])
    report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),results=results,
                diagnostic_only=True,conf_for_diagnosis_only=True,passenger_accuracy_validated=False)
    (root/'diagnostic.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
