import json
from pathlib import Path

def main():
    original=Path('configs/bus-portal-person-seg-exit-guard-r2.json')
    cfg=json.loads(original.read_text())
    cfg['cpu_threads']=2
    cfg['experiment_note']='Segmentation-box candidate with measured exit evidence guard and bounded CPU threads. Same thresholds; no mask-based counting. Independent and Orin validation absent.'
    with Path('configs/bus-portal-person-seg-exit-guard-cpu2-r2.json').open('x') as f:json.dump(cfg,f,indent=2)
    cfg['person_model']='runs/person-seg-dynamic-onnx-parity-20261001-r2/model.onnx'
    cfg['person_task']='segment'
    with Path('configs/bus-portal-person-seg-exit-guard-onnx-r2.json').open('x') as f:json.dump(cfg,f,indent=2)
    root=Path('runs/people-negative-person-seg-exit-guard-20261001-r2-full')
    with (root/'interrupted.json').open('x') as f:json.dump(dict(completed=False,reason='Severe slowdown; CPU thread omission hypothesis was incorrect: original config already requested 2. Rendering/inference diagnosis pending. Stopped own experiment process identified by start time/PID 368304; command-line inspection was denied. No summary/full-run success.',retry_config='configs/bus-portal-person-seg-exit-guard-cpu2-r2.json'),f,indent=2)

if __name__=='__main__':main()
