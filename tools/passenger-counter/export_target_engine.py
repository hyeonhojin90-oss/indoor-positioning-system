"""Target-device FP16 TensorRT export into an exclusive folder; no host-engine reuse."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
from collect_device_environment import collect

def validate_target(environment):
    if environment['platform']!='Linux' or environment['machine'] not in ('aarch64','arm64') or not environment['jetson_detected']:
        raise ValueError('Build requires actual Jetson Linux ARM64 device')
    if not environment['cuda_available'] or not environment.get('tensorrt_import_version'):
        raise ValueError('Working device CUDA torch and TensorRT are required')
    if environment['packages'].get('ultralytics')!='8.3.228':
        raise ValueError('Export workflow is pinned to the currently verified Ultralytics8.3.228; new versions need separate regression')

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--imgsz',type=int,required=True);p.add_argument('--workspace-gib',type=float,default=1);a=p.parse_args()
    if a.model.suffix!='.pt' or not a.model.is_file():raise ValueError('Existing PyTorch checkpoint required')
    if a.imgsz<32 or a.imgsz%32 or not 0<a.workspace_gib<=4:raise ValueError('Invalid model size or workspace')
    environment=collect();validate_target(environment)
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'environment-before-export.json').write_text(json.dumps(environment,indent=2))
    source_hash=hashlib.sha256(a.model.read_bytes()).hexdigest();checkpoint=a.output/'model.pt';shutil.copy2(a.model,checkpoint)
    os.environ.setdefault('YOLO_CONFIG_DIR',str((a.output/'settings').resolve()))
    os.environ['YOLO_AUTOINSTALL']='False'
    from ultralytics import YOLO
    model=YOLO(str(checkpoint))
    engine=Path(model.export(format='engine',imgsz=a.imgsz,batch=1,dynamic=True,half=True,
                            device=0,workspace=a.workspace_gib,nms=False,simplify=False))
    assert engine.is_file() and hashlib.sha256(a.model.read_bytes()).hexdigest()==source_hash
    report=dict(source_model_sha256=source_hash,engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
                task=model.task,imgsz=a.imgsz,half=True,dynamic=True,batch=1,workspace_gib=a.workspace_gib,
                target_environment=environment,engine=str(engine),engine_build_completed=True,
                detection_parity_validated=False,keypoint_parity_validated=False,counter_validated=False,
                note='Target-specific engine build only. Must compare actual rect frame detections/keypoints and complete counting before adoption; FP16 event/ID changes may occur.')
    (a.output/'export.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
