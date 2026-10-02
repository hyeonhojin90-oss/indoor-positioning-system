"""Prepare an isolated box-only architecture experiment; defaults stay unchanged."""
import json
from pathlib import Path

p=Path('configs/bus-portal-person-seg-exit-guard-onnx-r2.json')
if not p.exists():
    choices=list(Path('configs').glob('*seg*guard*onnx*r2.json'))
    choices=[x for x in choices if 'photo' not in x.name and 'cpu2' not in x.name]
    assert len(choices)==1,choices
    p=choices[0]
c=json.loads(p.read_text(encoding='utf-8'))
c['person_model']='runs/segment-trained-box-dynamic-onnx-parity-20261001-r2/model.onnx'
c['person_task']='detect'
c['experiment_note']='Segmentation-trained shared box weights retained exactly; unused mask head removed. Whole-video equivalence experiment, no threshold changes or Orin claims.'
target=Path('configs/bus-portal-segment-trained-box-guard-onnx-r2.json')
with target.open('x',encoding='utf-8') as f:json.dump(c,f,indent=2)
for n in ['green','green-right80','green-left80']:
    s=json.loads((Path('runs')/(n+'-person-seg-exit-guard-onnx-box-render-20261001-r2-full')/'summary.json').read_text())
    print(n,s['source'])
