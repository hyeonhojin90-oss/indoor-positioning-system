"""Reuse reviewed source identities only after exact event/box/evidence correspondence."""
import argparse,json
from pathlib import Path
from audit_completed_run import audit
from evaluate_events import evaluate_windows

read=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def correspondence(reference,target):
    summaries=[json.loads((p/'summary.json').read_text()) for p in (reference,target)]
    if summaries[0]['source_sha256']!=summaries[1]['source_sha256'] or summaries[0]['source_fps']!=summaries[1]['source_fps']:
        raise ValueError('Reviewed source differs')
    audits=[audit(p) for p in (reference,target)]
    keys=lambda items:[(e['frame'],e['track_id'],e['direction'],e['time_s'],e.get('commit_time_s'),e.get('anchor_evidence')) for e in items]
    if keys(audits[0]['events'])!=keys(audits[1]['events']):raise ValueError('Events changed; review source again')
    rows=[read(p/'tracks.jsonl') for p in (reference,target)]
    for event in audits[1]['events']:
        observation=round(event['time_s']*summaries[1]['source_fps']);tid=event['track_id']
        a,b=rows[0][observation],rows[1][observation]
        if tid not in a['ids'] or tid not in b['ids']:raise ValueError('Observed identity is absent')
        ia,ib=a['ids'].index(tid),b['ids'].index(tid)
        if a['boxes'][ia]!=b['boxes'][ib]:raise ValueError('Observed box changed')
        if event.get('anchor_evidence')=='measured_ankle_deferred':
            pa,pb=a['points'][ia],b['points'][ib]
            if pa is None or pb is None or max(abs(x-y) for x,y in zip(pa,pb))>1:
                raise ValueError('Measured ankle evidence changed')
    return audits[1]['events']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--truth',type=Path,required=True);a=p.parse_args()
    events=correspondence(a.reference,a.run);reviews=read(a.reference/'identity-review.jsonl')
    for r in reviews:r['review_provenance']=dict(reference=str(a.reference),method='Same original scene; exact event/time/identity/box and measured ankle correspondence verified. Not a new independent reviewer.')
    with (a.run/'identity-review.jsonl').open('x') as f:
        for r in reviews:f.write(json.dumps(r)+'\n')
    evaluation=evaluate_windows(events,read(a.truth),0,reviews)
    with (a.run/'identity-evaluation.json').open('x') as f:json.dump(evaluation,f,indent=2)
    print(evaluation['matched_reviewed_events'])
