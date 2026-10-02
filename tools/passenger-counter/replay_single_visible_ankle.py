"""One measured ankle hypothesis on frozen raw poses; never invent hidden feet."""
import copy,json
from pathlib import Path
from person_anchor import measured_points
from replay_counter import replay_rows

names=['green-segment-trained-box','green-right80-segment-trained-box','green-left80-segment-trained-box','stationary-segment-trained-box']
reports=[]
keys=lambda events:[(e['frame'],e['track_id'],e['direction'],e['time_s'],e.get('observation_frame'),e.get('commit_time_s'),e.get('anchor_evidence')) for e in events]
for name in names:
    root=Path('runs')/(name+'-20261001-r2-full')
    s=json.loads((root/'summary.json').read_text());cfg=s['config']
    rows=[json.loads(x) for x in (root/'tracks.jsonl').read_text().splitlines()]
    events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]
    baseline=replay_rows(rows,cfg);assert keys(baseline['events'])==keys(events)
    modified=copy.deepcopy(cfg);modified['pose_anchor']['min_visible']=1
    extra_points=0;changed=[]
    for row in rows:
        raw=list(zip(row['raw_ids'],row['raw_boxes']));pairs=list(zip(row['ids'],row['boxes']))
        poses={int(k):v for k,v in row['raw_keypoints'].items()}
        reconstructed=measured_points(pairs,raw,poses,cfg)
        assert reconstructed==[tuple(p) if p is not None else None for p in row['points']],'Saved baseline pose reconstruction differs'
        pts=measured_points(pairs,raw,poses,modified)
        extra_points+=sum(a is None and b is not None for a,b in zip(reconstructed,pts))
        r=dict(row,points=pts);changed.append(r)
    candidate=replay_rows(changed,modified)
    before=set(keys(events));after=set(keys(candidate['events']))
    report=dict(run=str(root),frames=len(rows),baseline_counts=baseline['counts'],candidate_counts=candidate['counts'],
                additional_measured_points=extra_points,events=candidate['events'],
                added_events=[e for e in candidate['events'] if keys([e])[0] not in before],
                removed_events=[e for e in events if keys([e])[0] not in after],
                exact_event_parity=keys(events)==keys(candidate['events']))
    reports.append(report);print(name,baseline['counts'],candidate['counts'],'extra measured points',extra_points)
with Path('runs/single-visible-ankle-frozen-replay-r2.json').open('x') as f:json.dump(dict(runs=reports,full_model_rerun=False,independent_accuracy_validated=False,default_changed=False,note='Only min_visible2→1; conf.5, unique pose association, exact raw box membership and all passage thresholds unchanged. Baseline measured points reconstructed exactly before experiment.'),f,indent=2)
