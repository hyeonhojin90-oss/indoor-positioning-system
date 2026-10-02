import json
from pathlib import Path

def save(name,cfg):
    with (Path('configs')/name).open('x') as f:json.dump(cfg,f,indent=2)

def main():
    cfg=json.loads(Path('configs/bus-portal-person-seg-exit-guard-onnx-r2.json').read_text())
    cfg['door_model']='runs/door-photo-enriched-dynamic-onnx-parity-20261001-r2/model.onnx'
    cfg['experiment_note']='Photo-enriched door only; retain verified segmentation-box person/pose/bus ONNX and exit guard. Fixed conf .35 and counting/GT windows. Full video accuracy pending.'
    save('bus-portal-photo-enriched-seg-guard-onnx-r2.json',cfg)
    cfg['door_selection_confidence']=True
    cfg['experiment_note']+=' Optional confidence*passenger-support initial selection; lock retention/minimum support unchanged.'
    save('bus-portal-photo-enriched-confidence-onnx-r2.json',cfg)
    base=json.loads(Path('configs/bus-portal-aux-pose-gated-onnx-candidate.json').read_text())
    base['door_selection_confidence']=True
    base['experiment_note']='Default algorithms/models with optional confidence ranking only; regression experiment, default file unchanged.'
    save('bus-portal-baseline-confidence-onnx-r2.json',base)

if __name__=='__main__':main()
