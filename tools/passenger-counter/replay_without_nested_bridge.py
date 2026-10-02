"""Frozen raw ID replay without nested aliases; isolate continuity tradeoffs."""
import copy,json
from pathlib import Path
from person_anchor import measured_points
from replay_counter import replay_rows

names=['green','green-right80','green-left80','green-reverse','stationary','people-negative']
reports=[]
keys=lambda events:[(e['frame'],e['track_id'],e['direction'],e['time_s'],e.get('observation_frame'),e.get('commit_time_s'),e.get('anchor_evidence')) for e in events]
for name in names:
    root=Path('runs')/(name+'-segment-trained-box-20261001-r2-full')
    s=json.loads((root/'summary.json').read_text());cfg=s['config']
    rows=[json.loads(x) for x in (root/'tracks.jsonl').read_text().splitlines()]
    old=replay_rows(rows,cfg);events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]
    assert keys(old['events'])==keys(events)
    modified=copy.deepcopy(cfg);modified['track_bridge']['enabled']=False
    candidate=[]
    for r in rows:
        pairs=list(zip(r['raw_ids'],r['raw_boxes']))
        poses={int(k):v for k,v in r['raw_keypoints'].items()}
        pts=measured_points(pairs,pairs,poses,cfg)
        candidate.append(dict(r,ids=r['raw_ids'],boxes=r['raw_boxes'],points=pts))
    new=replay_rows(candidate,modified)
    report=dict(run=str(root),baseline_counts=old['counts'],candidate_counts=new['counts'],events=new['events'],exact_event_parity=keys(old['events'])==keys(new['events']))
    reports.append(report);print(name,old['counts'],new['counts'])
with Path('runs/no-nested-bridge-frozen-replay-r2.json').open('x') as f:json.dump(dict(runs=reports,full_model_rerun=False,default_changed=False,independent_accuracy_validated=False,note='Use actual saved raw IDs/boxes and uniquely associated measured keypoints; remove nested aliases only. Numerical count increases are not accuracy proof.'),f,indent=2)
