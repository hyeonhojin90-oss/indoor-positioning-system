import json
from pathlib import Path

def main():
    cfg=json.loads(Path('configs/bus-portal-person-seg-exit-guard-onnx-r2.json').read_text())
    cfg['person_model']='runs/person-dynamic-onnx-parity-20260930/model.onnx'
    cfg['person_task']='detect'
    cfg['experiment_note']='Existing verified YOLO11m ONNX person boxes, old door and conditional pose/bus models, exit guard. Larger detector comparison only, no threshold/window tuning; Orin speed/memory unverified.'
    with Path('configs/bus-portal-medium-person-exit-guard-onnx-r2.json').open('x') as f:json.dump(cfg,f,indent=2)

if __name__=='__main__':main()
