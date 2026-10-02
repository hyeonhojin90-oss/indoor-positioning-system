"""Export a checkpoint copy and compare fixed CPU FP32 detections to PyTorch."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import math
from pathlib import Path
import shutil
from counter import iou
from runtime_threads import configure_model_threads


def compare_detections(reference, exported, min_iou=.99, max_score_error=.001,
                       max_coordinate_error=1.):
    edges = []
    for a in reference:
        candidates=[]
        for j,b in enumerate(exported):
            if a['class_id'] != b['class_id']:
                continue
            score_error=abs(a['score']-b['score'])
            coordinate_error=max(abs(x-y) for x,y in zip(a['box'],b['box']))
            overlap=iou(a['box'],b['box'])
            if overlap>=min_iou and score_error<=max_score_error and coordinate_error<=max_coordinate_error:
                candidates.append(j)
        edges.append(candidates)
    matched={}
    def assign(index,seen):
        for j in edges[index]:
            if j in seen:continue
            seen.add(j)
            if j not in matched or assign(matched[j],seen):
                matched[j]=index;return True
        return False
    for index in range(len(reference)):assign(index,set())
    return {'reference_count':len(reference),'exported_count':len(exported),
            'matched':len(matched),
            'matched_pairs':sorted((i,j) for j,i in matched.items()),
            'passed':len(matched)==len(reference)==len(exported)}

def compare_pose_detections(reference,exported):
    result=compare_detections(reference,exported);errors=[]
    for i,j in result['matched_pairs']:
        a,b=reference[i].get('keypoints'),exported[j].get('keypoints')
        if a is None or b is None or len(a)!=17 or len(b)!=17:
            errors.append({'reference':i,'exported':j,'error':'Missing COCO keypoints'});continue
        for index,(pa,pb) in enumerate(zip(a,b)):
            if len(pa)!=3 or len(pb)!=3 or not all(math.isfinite(x) for x in pa+pb) or max(abs(x-y) for x,y in zip(pa[:2],pb[:2]))>1 or abs(pa[2]-pb[2])>.001:
                errors.append({'reference':i,'exported':j,'keypoint':index})
    return dict(result,passed=result['passed'] and not errors,keypoint_errors=errors)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--frames',type=int,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--imgsz',type=int,default=640)
    p.add_argument('--conf',type=float,default=.25)
    p.add_argument('--classes',type=int,nargs='+',default=[0])
    p.add_argument('--dynamic',action='store_true',
                   help='Preserve rectangular auto-padding with variable input dimensions')
    a=p.parse_args()
    if a.imgsz<32 or a.imgsz%32 or not 0<a.conf<1 or min(a.frames)<0:
        raise ValueError('Invalid export input/threshold/frame')
    a.output.mkdir(parents=True,exist_ok=False)
    os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs/settings'))
    os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent/'runs/matplotlib'))
    import cv2
    import onnx
    from ultralytics import YOLO
    checkpoint=a.output/'model.pt'
    shutil.copy2(a.model,checkpoint)
    export_model=YOLO(str(checkpoint))
    configure_model_threads(export_model,2)
    exported_path=Path(export_model.export(format='onnx',imgsz=a.imgsz,batch=1,
                                         device='cpu',half=False,dynamic=a.dynamic,
                                         simplify=False,opset=17,nms=False))
    onnx.checker.check_model(str(exported_path))
    # Fresh models avoid export-time fusion/in-place state influencing the reference.
    reference=YOLO(str(checkpoint));exported=YOLO(str(exported_path),task=reference.task)
    if reference.task not in ('detect','pose','segment'):raise ValueError('Unsupported parity task')
    configure_model_threads(reference,2);configure_model_threads(exported,2)
    cap=cv2.VideoCapture(str(a.source));rows=[]
    def serialize(result):
        rows=[{'box':b,'score':s,'class_id':c} for b,s,c in zip(
            result.boxes.xyxy.tolist(),result.boxes.conf.tolist(),result.boxes.cls.int().tolist())]
        if result.keypoints is not None:
            for row,k in zip(rows,result.keypoints.data.tolist()):row['keypoints']=k
        return rows
    try:
        for frame in a.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,image=cap.read()
            if not ok:raise ValueError(f'Cannot decode source frame {frame}')
            kwargs=dict(imgsz=a.imgsz,conf=a.conf,iou=.7,classes=a.classes,
                        device='cpu',rect=a.dynamic,verbose=False)
            pt=serialize(reference.predict(image,**kwargs)[0])
            ox=serialize(exported.predict(image,**kwargs)[0])
            rows.append({'frame':frame,'pytorch':pt,'onnx':ox,
                         'comparison':(compare_pose_detections if reference.task=='pose' else compare_detections)(pt,ox)})
    finally:cap.release()
    positive=sum(row['comparison']['matched'] for row in rows)
    passed=all(row['comparison']['passed'] for row in rows) and positive>0
    report={'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            'onnx_sha256':hashlib.sha256(exported_path.read_bytes()).hexdigest(),
            'source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),
            'source':str(a.source),'imgsz':a.imgsz,'conf':a.conf,'classes':a.classes,
            'task':reference.task,'rect':a.dynamic,'dynamic':a.dynamic,'opset':17,'precision':'FP32','device':'Windows CPU',
            'tolerances':{'minimum_iou':.99,'maximum_score_error':.001,'maximum_pixel_error':1},
            'versions':{name:importlib.metadata.version(name) for name in ('ultralytics','torch','onnx','onnxruntime')},
            'parity_passed':passed,'matched_positive_detections':positive,'rows':rows,
            'jetson_validated':False,'tensorrt_validated':False,
            'segmentation_masks_compared':False,
            'note':'Fixed frame boxes/classes/confidences and pose keypoints only; segmentation masks are unused by passenger counting and not compared. No tracker, count, speed or unseen-scene validation.'}
    (a.output/'parity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'parity_passed':passed,'positive_detections':positive},indent=2))
    if not passed:raise SystemExit('Export detection parity failed or no positive detections')


if __name__=='__main__':main()
