"""Experimental box-only derivative; preserve segmentation-trained box weights."""
import copy,hashlib,json,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))

def main():
    import cv2,torch
    from ultralytics import YOLO
    from ultralytics.nn.modules.head import Detect,Segment
    from ultralytics.nn.tasks import DetectionModel,SegmentationModel
    from runtime_threads import configure_model_threads
    from export_verified_onnx import compare_detections
    source=Path('models/yolo11s-seg.pt');output=Path('models/yolo11s-seg-trained-box-detector-r2.pt')
    report_path=output.with_suffix('.source.json')
    if output.exists() or report_path.exists():raise FileExistsError('Derivative already exists')
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    torch.set_num_threads(2);reference=YOLO(str(source));derived=YOLO(str(source))
    assert type(derived.model) is SegmentationModel and type(derived.model.model[-1]) is Segment
    before={n:p.detach().clone() for n,p in derived.model.state_dict().items()}
    original_parameters=sum(p.numel() for p in derived.model.parameters())
    head=derived.model.model[-1]
    for attr in ['proto','cv4','nm','npr']:delattr(head,attr)
    head.__class__=Detect
    derived.model.__class__=DetectionModel
    derived.model.args=copy.deepcopy(derived.model.args);derived.model.args['task']='detect'
    derived.model.task='detect';derived.task='detect';derived.overrides['task']='detect'
    derived.model.yaml=copy.deepcopy(derived.model.yaml)
    derived.model.yaml['head'][-1][2]='Detect';derived.model.yaml['head'][-1][3]=['nc']
    if derived.ckpt.get('ema') is not None:raise ValueError('EMA checkpoint needs explicit derivation')
    derived.save(str(output))
    restored=YOLO(str(output),task='detect')
    assert restored.task=='detect' and type(restored.model.model[-1]) is Detect
    state=restored.model.state_dict()
    assert all(n in before and torch.equal(p,before[n]) for n,p in state.items())
    removed=sorted(set(before)-set(state))
    assert removed and all('.proto.' in n or '.cv4.' in n for n in removed)
    configure_model_threads(reference,2);configure_model_threads(restored,2)
    video=Path('data/regression/bus-green-32245403-720.mp4');cap=cv2.VideoCapture(str(video));rows=[]
    def boxes(r):return [dict(box=b,score=s,class_id=c) for b,s,c in zip(r.boxes.xyxy.tolist(),r.boxes.conf.tolist(),r.boxes.cls.int().tolist())]
    try:
        for fid in [32,59,89,119,180,260,331,357]:
            cap.set(cv2.CAP_PROP_POS_FRAMES,fid);ok,frame=cap.read();assert ok
            options=dict(imgsz=640,classes=[0],conf=.25,iou=.7,rect=True,device='cpu',verbose=False)
            a=reference.predict(frame,**options)[0];b=restored.predict(frame,**options)[0]
            assert a.masks is not None and b.masks is None
            rows.append(dict(frame=fid,reference=boxes(a),derived=boxes(b),comparison=compare_detections(boxes(a),boxes(b))))
    finally:cap.release()
    passed=all(r['comparison']['passed'] for r in rows) and sum(r['comparison']['matched'] for r in rows)>0
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    report=dict(source_model_sha256=source_hash,derived_model_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        source_model=str(source),derived_model=str(output),original_source_unchanged=True,
        original_parameters=original_parameters,derived_parameters=sum(p.numel() for p in restored.model.parameters()),
        all_retained_tensors_exactly_equal=True,removed_mask_tensor_names=removed,
        data_source_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),rows=rows,box_parity_passed=passed,
        training_performed=False,segmentation_masks_available=False,
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        full_counter_parity_validated=False,jetson_validated=False,tensorrt_validated=False,
        note='Architecture derivative only: pretrained segmentation box/backbone parameters retained exactly, unused mask branch removed. Fixed-frame box parity is not full-video or Orin proof.')
    report_path.write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ['original_parameters','derived_parameters','all_retained_tensors_exactly_equal','box_parity_passed']}))
    if not passed:raise SystemExit('Derived box model differs from reference')

if __name__=='__main__':main()
