"""Compare actual source-frame boxes/keypoints across PT, ONNX or target engines."""
import argparse,hashlib,json,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
from export_verified_onnx import compare_detections,compare_pose_detections
from runtime_threads import configure_model_threads,backend_runtime_info

def observations(result,pose=False):
    rows=[]
    for i,(box,score,cls) in enumerate(zip(result.boxes.xyxy.tolist(),result.boxes.conf.tolist(),result.boxes.cls.int().tolist())):
        row=dict(box=box,score=score,class_id=cls)
        if pose:row['keypoints']=result.keypoints.data[i].tolist()
        rows.append(row)
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--frames',type=int,nargs='+',required=True);p.add_argument('--imgsz',type=int,required=True)
    p.add_argument('--task',choices=['detect','pose'],required=True);p.add_argument('--conf',type=float,default=.35)
    p.add_argument('--classes',type=int,nargs='+',default=[0]);p.add_argument('--device',default='cpu')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.imgsz<32 or a.imgsz%32 or not 0<a.conf<1:raise ValueError('Invalid input size/confidence')
    target_environment=None
    if a.candidate.suffix=='.engine':
        from collect_device_environment import collect
        from export_target_engine import validate_target
        target_environment=collect();validate_target(target_environment)
        if a.device not in ('0','cuda:0'):raise ValueError('Target engine requires CUDA0')
    import cv2
    from ultralytics import YOLO
    hashes={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in [('reference',a.reference),('candidate',a.candidate),('source',a.source)]}
    ref=YOLO(str(a.reference),task=a.task);candidate=YOLO(str(a.candidate),task=a.task)
    if ref.task!=a.task:raise ValueError('Reference task differs')
    for model in [ref,candidate]:configure_model_threads(model,2)
    cap=cv2.VideoCapture(str(a.source));rows=[]
    try:
        for f in a.frames:
            if f<0:raise ValueError('Negative source frame')
            cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,img=cap.read()
            if not ok:raise ValueError(f'Missing frame {f}')
            results=[m.predict(img,imgsz=a.imgsz,conf=a.conf,classes=a.classes,rect=True,device=a.device,verbose=False)[0] for m in [ref,candidate]]
            actual=[observations(r,a.task=='pose') for r in results]
            comparison=(compare_pose_detections if a.task=='pose' else compare_detections)(*actual)
            rows.append(dict(frame=f,reference=actual[0],candidate=actual[1],comparison=comparison))
            print(f,comparison['passed'],comparison['reference_count'],flush=True)
    finally:cap.release()
    final_hashes={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in [('reference',a.reference),('candidate',a.candidate),('source',a.source)]}
    if hashes!=final_hashes:raise ValueError('Source/model changed during comparison')
    report=dict(passed=all(r['comparison']['passed'] for r in rows) and bool(rows),hashes=hashes,
                task=a.task,imgsz=a.imgsz,conf=a.conf,classes=a.classes,rect=True,device=a.device,rows=rows,
                backend={'reference':backend_runtime_info(ref),'candidate':backend_runtime_info(candidate)},
                full_counter_validated=False,independent_accuracy_validated=False,
                note='Current-frame model parity only; whole tracking/events and target thermal/latency must be checked separately.')
    if target_environment is not None:report['target_environment']=target_environment
    with a.output.open('x') as f:json.dump(report,f,indent=2)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
