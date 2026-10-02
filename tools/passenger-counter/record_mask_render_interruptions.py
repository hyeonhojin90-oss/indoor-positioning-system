import json
from pathlib import Path

def main():
    names=['people-negative-person-seg-exit-guard-cpu2','green-person-seg-exit-guard-onnx',
           'green-right80-person-seg-exit-guard-onnx','green-left80-person-seg-exit-guard-onnx']
    for name in names:
        root=Path('runs')/(name+'-20261001-r2-full')
        with (root/'interrupted.json').open('x') as f:json.dump(dict(completed=False,
            reason='Stopped exact own run.py process after command-line/PID check to remove unused expensive mask rendering. Partial traces are not full validation.',
            evidence='runs/segment-mask-render-cost-r2.json',retry_suffix='-box-render-20261001-r2-full'),f,indent=2)
    root=Path('runs/people-negative-person-seg-exit-guard-20261001-r2-full/interrupted.json')
    r=json.loads(root.read_text());r['reason']='Severe slowdown; initial unbounded-thread explanation was incorrect. Original config and completed jobs requested/used 2 threads. Same-frame mask rendering measured 3.1..3.6s versus box rendering 0.006..0.043s. First partial run stopped, no completed summary.'
    root.write_text(json.dumps(r,indent=2))

if __name__=='__main__':main()
