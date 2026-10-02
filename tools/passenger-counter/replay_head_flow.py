"""Diagnostic only: source pixels + completed boxes, no detector rerun."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import cv2
from motion_head_bridge import MotionHeadBridge
from replay_counter import replay_rows


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    summary = json.loads((a.run/'summary.json').read_text())
    source = Path(summary['source'])
    if digest(source) != summary['source_sha256']:
        raise ValueError('Source mismatch')
    rows = [json.loads(l) for l in (a.run/'tracks.jsonl').read_text().splitlines()]
    if len(rows) != summary['frames'] or any(r['frame']!=i for i,r in enumerate(rows)):
        raise ValueError('Incomplete trace')
    before = replay_rows(rows,summary['config'])
    if before['counts'] != summary['counts']:
        raise ValueError('Baseline replay mismatch')
    bridge = MotionHeadBridge()
    cap = cv2.VideoCapture(str(source))
    output = []
    aliases = []
    generation = None
    try:
        for row in rows:
            ok, image = cap.read()
            if not ok:
                raise ValueError('Source ended before trace')
            if row['door'] is None or row['door_generation'] != generation:
                bridge.reset()
            generation = row['door_generation']
            n = len(bridge.audit)
            pairs = bridge.update(image,list(zip(row['ids'],row['boxes'])),row['time_s'])
            aliases.extend(dict(e,frame=row['frame']) for e in bridge.audit[n:])
            updated = copy.deepcopy(row)
            updated['ids'] = [i for i,_ in pairs]
            # Original measured boxes and foot points are unchanged.
            output.append(updated)
    finally:
        cap.release()
    result = dict(source_run=str(a.run),source_sha256=digest(source),frames=len(rows),
                  aliases=aliases,baseline=before,candidate=replay_rows(output,summary['config']),
                  implementation_sha256={f:digest(Path(f)) for f in
                                         ['motion_head_bridge.py','replay_head_flow.py']},
                  diagnostic_only=True,detector_rerun=False,independent_accuracy_validated=False,
                  note='Measured head optical flow only; boxes and measured foot points unchanged. Saved detector/door history; requires full runtime and visual identity verification before adoption.')
    with a.output.open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
    print(json.dumps(dict(aliases=aliases,baseline=before['counts'],candidate=result['candidate']['counts'])))


if __name__ == '__main__':
    main()
