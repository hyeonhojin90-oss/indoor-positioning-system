"""Frozen full-video ID continuity experiment; leaves live detection/counting unchanged."""
import argparse,copy,hashlib,json
from pathlib import Path
from stable_observation_bridge import StableObservationBridge
from track_bridge import NestedTrackBridge
from person_anchor import measured_points
from replay_counter import replay_rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    s=json.loads((a.run/'summary.json').read_text());audit=json.loads((a.run/'completion-audit.json').read_text())
    if not audit['complete_source'] or not audit['replay_parity']:raise ValueError('Completed source audit required')
    if hashlib.sha256(Path(s['source']).read_bytes()).hexdigest()!=s['source_sha256']:raise ValueError('Changed source')
    original=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
    if len(original)!=s['frames'] or [r['frame'] for r in original]!=list(range(s['frames'])):raise ValueError('Incomplete trace')
    bridge=StableObservationBridge();nested=NestedTrackBridge(**{k:v for k,v in s['config'].get('track_bridge',{}).items() if k!='enabled'})
    rows=[];generation=None;links=[];a.output.mkdir(parents=True,exist_ok=False)
    for row in original:
        if row['door'] is None or row['door_generation']!=generation:bridge.reset();nested.reset()
        generation=row['door_generation'];raw=list(zip(row['raw_ids'],row['raw_boxes']));before=len(bridge.audit)
        pairs=bridge.update(raw,row['time_s']) if row['door'] is not None else raw
        links.extend(dict(e,frame=row['frame'],door_generation=generation) for e in bridge.audit[before:])
        pairs=nested.update(pairs,row['time_s'],row['door']) if row['door'] is not None else pairs
        poses={int(k):v for k,v in row.get('raw_keypoints',{}).items()}
        rows.append(dict(row,ids=[i for i,_ in pairs],boxes=[b for _,b in pairs],points=measured_points(pairs,raw,poses,s['config'])))
    config=copy.deepcopy(s['config']);result=replay_rows(rows,config)
    with (a.output/'tracks.jsonl').open('x') as f:
        for row in rows:f.write(json.dumps(row)+'\n')
    report=dict(reference_run=str(a.run),source=s['source'],source_sha256=s['source_sha256'],config=config,**result,
        temporal_links=links,frozen_detections=True,full_detector_rerun=False,adopted=False,
        independent_accuracy_validated=False,implementation_sha256={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in ['stable_observation_bridge.py','temporal_nested_bridge.py','replay_stable_observation.py','track_bridge.py','counter.py','multi_anchor_counter.py','person_anchor.py']})
    (a.output/'replay.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(run=str(a.run),counts=result['counts'],links=links)))

if __name__=='__main__':main()
