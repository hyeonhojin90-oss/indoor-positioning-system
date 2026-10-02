"""Record completed, assistant-visual development reviews; never tune truth windows."""
import hashlib
import argparse
import json
from pathlib import Path
from evaluate_events import evaluate_windows

def read(p):
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]

def save(p,value):
    with p.open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--yoloe',action='store_true')
    parser.add_argument('--exit-guard',action='store_true')
    parser.add_argument('--photo-enriched',action='store_true')
    parser.add_argument('--medium-person',action='store_true')
    args=parser.parse_args()
    truth=read(Path('reviews/green-development-windows.jsonl'))
    people=[r['person'] for r in truth]
    specs={
        'green-door-median5': [1,2,3,4,5],
        'green-right80-door-median5': [None,None,2,4,5],
        'green-left80-door-median5': [0,1,2,4,5],
        'green-right80-door640': [None,2,4,5],
        'green-two-arrivals-baseline': [0,1,2,3,4,5,0,4,5],
        'green-two-arrivals-partial-retry': [0,1,2,3,4,5,0,1,2,4,5],
    }
    if args.yoloe:
        specs={name:[0,0,1,2,3,4,5] for name in
               ['green-yoloe-person','green-left80-yoloe-person','green-right80-yoloe-person']}
    if args.exit_guard:
        specs={'green-person-seg-exit-guard':[0,1,2,3,4,5],
               'green-right80-person-seg-exit-guard':[None,2,3,4,5],
               'green-left80-person-seg-exit-guard':[0,1,2,4,5]}
    if args.photo_enriched:
        specs={'green-photo-enriched-confidence':[0,2,3,4,5],
               'green-photo-enriched-unweighted':[0,2,3,4,5],
               'green-left80-photo-enriched-confidence':[1,2,4,5],
               'green-right80-photo-enriched-confidence':[0,None,None,None,2,3,4,5]}
        roots=[Path('runs')/(n+'-20261001-r2-full') for n in
               ['green-photo-enriched-confidence','green-photo-enriched-unweighted']]
        a,b=[read(r/'tracks.jsonl') for r in roots]
        assert len(a)==len(b)==513
        assert all(all(x.get(k)==y.get(k) for k in ('ids','boxes','points','door','door_generation')) for x,y in zip(a,b))
    if args.medium_person:
        specs={'green-medium-person-exit-guard':[0,1,2,3,4,5],
               'green-right80-medium-person-exit-guard':[None,2,3,4,5],
               'green-left80-medium-person-exit-guard':[0,1,2,4,5]}
    for name,labels in specs.items():
        run=Path('runs')/(name+'-20261001-r2-full')
        summary=json.loads((run/'summary.json').read_text())
        audit=json.loads((run/'completion-audit.json').read_text())
        assert audit['complete_source'] and audit['replay_parity']
        assert hashlib.sha256(Path(summary['source']).read_bytes()).hexdigest()==summary['source_sha256']
        events=read(run/'events.jsonl');assert len(events)==len(labels)
        arrivals='two-arrivals' in name
        windows=truth
        if arrivals:
            windows=[]
            for phase,offset in [('first',0),('second',603)]:
                for t in truth:
                    r=dict(t,person=phase+'/'+t['person'],
                           start_s=t['start_s']+offset/30,end_s=t['end_s']+offset/30,
                           frames=[f+offset for f in t['frames']])
                    windows.append(r)
        reviews=[]
        for e,idx in zip(events,labels):
            r={k:e[k] for k in ('frame','track_id','direction')}
            r.update(status='uncertain' if idx is None else 'accepted',
                     note='Assistant source-frame visual review; identity acceptance does not validate timing or direction. Fixed truth windows unchanged.')
            if idx is not None:
                phase=('first/' if e['frame']<513 else 'second/') if arrivals else ''
                r['person']=phase+people[idx]
            else:
                r['note']+=' Interior-person OUT, overlapping mixed-person box or canonical identity switch remains unclassified.'
            reviews.append(r)
        with (run/'identity-review.jsonl').open('x') as f:
            for r in reviews:f.write(json.dumps(r)+'\n')
        result=evaluate_windows(events,windows,0,reviews)
        result.update(source_sha256=summary['source_sha256'],assistant_review=True,human_reviewed=False)
        save(run/'identity-evaluation.json',result)
        if arrivals:
            rows=read(run/'tracks.jsonl')
            for r in rows:
                assert len(r['raw_ids'])==len(r['raw_boxes'])==len(r['raw_confidences'])
                assert all(0<=v<=1 for v in r['raw_confidences'])
            gap=[r for r in rows if 513<=r['frame']<603]
            gap_events=[e for e in events if 513<=e['frame']<603 or 513<=e['observation_frame']<603]
            report=dict(negative_segment=[513,602],events=gap_events,
                        active_door_frames=[r['frame'] for r in gap if r['door']],
                        first_segment_events=sum(e['frame']<513 for e in events),
                        second_segment_events=sum(e['frame']>=603 for e in events),
                        raw_confidence_alignment_checked=True,
                        synthetic_hard_cuts=True,independent_footage=False)
            assert not gap_events
            save(run/'arrival-segments.json',report)
        print(name,summary['counts'],result['matched_reviewed_events'],len(windows))

if __name__=='__main__':main()
