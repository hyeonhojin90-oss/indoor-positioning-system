"""Qualitative native doorway model check; fixed 640 end-to-end ONNX only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--run',type=Path)
    p.add_argument('--frames',type=int,nargs='+',default=[350,400,440]);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    model=Path('models/doorway26n.onnx');opts=ort.SessionOptions();opts.intra_op_num_threads=2
    session=ort.InferenceSession(str(model),sess_options=opts,providers=['CPUExecutionProvider'])
    meta=session.get_modelmeta().custom_metadata_map
    if meta.get('end2end')!='True' or session.get_inputs()[0].shape!=[1,3,640,640]:
        raise ValueError('Unsupported output/input contract')
    spec=importlib.util.spec_from_file_location('public_mirror','models/mirror_suppress_source.py')
    post=importlib.util.module_from_spec(spec);spec.loader.exec_module(post)
    doors=[json.loads(x) for x in (a.run/'doors.jsonl').read_text().splitlines()] if a.run else []
    cap=cv2.VideoCapture(a.source);rows=[]
    try:
        for f in a.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,frame=cap.read()
            if not ok:raise ValueError('Cannot decode frame')
            h,w=frame.shape[:2];regions=[(0,0,w,h)]
            prior=[d for d in doors if d['frame']<=f and d['locked']]
            if prior:
                b=prior[-1]['locked'];dw,dh=b[2]-b[0],b[3]-b[1]
                regions.append((max(0,int(b[0]-2*dw)),max(0,int(b[1]-.3*dh)),
                                min(w,int(b[2]+2*dw)),min(h,int(b[3]+.3*dh))))
            for index,(x1,y1,x2,y2) in enumerate(regions):
                crop=frame[y1:y2,x1:x2];ch,cw=crop.shape[:2]
                scale=min(640/cw,640/ch);nw,nh=round(cw*scale),round(ch*scale)
                left,top=(640-nw)//2,(640-nh)//2
                canvas=np.full((640,640,3),114,np.uint8)
                canvas[top:top+nh,left:left+nw]=cv2.resize(crop,(nw,nh))
                tensor=np.ascontiguousarray(canvas[:,:,::-1].transpose(2,0,1)[None],dtype=np.float32)/255
                pred=session.run(None,{'images':tensor})[0]
                if pred.shape!=(1,300,38):raise ValueError('Unexpected end-to-end segmentation output')
                detections=[]
                for item in pred[0]:
                    score=float(item[4]);cls=float(item[5])
                    if not 0<=score<=1 or cls!=int(cls) or not 0<=cls<=4:
                        raise ValueError('Invalid output confidence/class contract')
                    if score<.1:continue
                    b=[(float(item[0])-left)/scale+x1,(float(item[1])-top)/scale+y1,
                       (float(item[2])-left)/scale+x1,(float(item[3])-top)/scale+y1]
                    detections.append({'box':b,'conf':score,'cls':int(cls)})
                kept=post.finalize(detections,out_conf=.1)
                row={'frame':f,'region':[x1,y1,x2,y2],'detections':kept};rows.append(row)
                im=frame.copy()
                for d in kept:
                    b=tuple(round(v) for v in d['box']);cv2.rectangle(im,b[:2],b[2:],(20,200,255),2)
                    cv2.putText(im,f"class {d['cls']} {d['conf']:.2f}",(b[0],b[1]-5),0,.5,(20,200,255),1)
                cv2.imwrite(str(a.output/f'frame-{f}-region-{index}.jpg'),im)
                print(json.dumps(row),flush=True)
    finally:cap.release()
    (a.output/'detections.json').write_text(json.dumps({'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
        'metadata':meta,'rows':rows,'mask_evaluated':False,'independent_accuracy_validated':False},indent=2))


if __name__=='__main__':main()
