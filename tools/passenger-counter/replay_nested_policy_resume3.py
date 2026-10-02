"""Diagnose the cost of unrestricted nested aliases on frozen current observations."""
import argparse,hashlib,json,copy
from pathlib import Path
from track_bridge import NestedTrackBridge
from person_anchor import measured_points
from replay_counter import replay_rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    s=json.loads((a.run/'summary.json').read_text());original=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
    assert hashlib.sha256(Path(s['source']).read_bytes()).hexdigest()==s['source_sha256']
    completion=json.loads((a.run/'completion-audit.json').read_text());assert completion['complete_source'] and completion['replay_parity']
    assert len(original)==s['frames'] and [r['frame'] for r in original]==list(range(s['frames']))
    options={k:v for k,v in s['config'].get('track_bridge',{}).items() if k not in ('enabled','bottom_approach_high')}
    bridge=NestedTrackBridge(**options);generation=None;rows=[];links=[]
    a.output.mkdir(parents=True,exist_ok=False)
    for row in original:
        if row['door'] is None or row['door_generation']!=generation:bridge.reset()
        generation=row['door_generation'];raw=list(zip(row['raw_ids'],row['raw_boxes']));before=len(bridge.audit)
        pairs=bridge.update(raw,row['time_s'],row['door']) if row['door'] is not None else raw
        links.extend(dict(event,frame=row['frame'],door_generation=generation) for event in bridge.audit[before:])
        poses={int(k):v for k,v in row.get('raw_keypoints',{}).items()}
        rows.append(dict(row,ids=[i for i,_ in pairs],boxes=[b for _,b in pairs],points=measured_points(pairs,raw,poses,s['config'])))
    cfg=copy.deepcopy(s['config']);cfg['track_bridge']['enabled']=False
    result=replay_rows(rows,cfg)
    with (a.output/'tracks.jsonl').open('x') as f:
        for row in rows:f.write(json.dumps(row)+'\n')
    report=dict(reference_run=str(a.run),source=s['source'],source_sha256=s['source_sha256'],config=cfg,**result,
                bridge_links=links,removed_approach_gate=True,frozen_detections=True,full_detector_rerun=False,
                independent_accuracy_validated=False,adopted=False,
                implementation_sha256={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in ['track_bridge.py','replay_nested_policy_resume3.py','person_anchor.py','counter.py','multi_anchor_counter.py','replay_counter.py']})
    with (a.output/'replay.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(dict(run=str(a.run),counts=result['counts'],links=len(links))))

if __name__=='__main__':main()
