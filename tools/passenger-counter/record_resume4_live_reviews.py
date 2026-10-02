"""Record already viewed live event identities and compare frozen/live traces."""
import hashlib
import json
from pathlib import Path
from evaluate_events import evaluate_windows,evaluate_person_directions


def read(path):return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]


def main():
    truth=read(Path('reviews/green-development-windows.jsonl'))
    mappings={
        'green-osnet-observed-resume4-full':{8:'olive-shirt-white-bag',4:'brown-shirt-white-bag',
            60:'grey-hair-backpack',2:'teal-shirt',80:'yellow-bag-umbrella',85:'white-shirt-grey-shorts'},
        'green-left80-osnet-observed-resume4-full':{55:'olive-shirt-white-bag',3:'brown-shirt-white-bag',
            90:'grey-hair-backpack',1:'teal-shirt',111:'yellow-bag-umbrella',127:'white-shirt-grey-shorts'}}
    for name,mapping in mappings.items():
        root=Path('runs')/name;events=read(root/'events.jsonl')
        reviews=[dict(frame=e['frame'],track_id=e['track_id'],direction=e['direction'],
            person=mapping[e['track_id']],status='accepted',
            review_basis='actual complete live-run source event montage, including observation/commit frames; timing windows unchanged') for e in events]
        with (root/'identity-review-resume4.jsonl').open('x',encoding='utf-8') as f:
            for row in reviews:f.write(json.dumps(row)+'\n')
        (root/'reviewed-evaluation-resume4.json').open('x').write(json.dumps(evaluate_windows(events,truth,0,reviews),indent=2))
        (root/'person-direction-review.json').open('x').write(json.dumps(evaluate_person_directions(events,truth,reviews),indent=2))
    frozen=Path('runs/green-left80-osnet-simultaneous-resume4-replay');live=Path('runs/green-left80-osnet-observed-resume4-full')
    a,b=read(frozen/'tracks.jsonl'),read(live/'tracks.jsonl')
    fields=['frame','time_s','door','door_generation','raw_ids','raw_boxes','ids','boxes','points','raw_keypoints']
    mismatches=[i for i,(x,y) in enumerate(zip(a,b)) if any(x.get(k)!=y.get(k) for k in fields)]
    key=lambda e:(e['frame'],e['track_id'],e['direction'],e['time_s'],e.get('observation_frame'),e.get('commit_time_s'),e.get('anchor_evidence'))
    ae=json.loads((frozen/'replay.json').read_text())['events'];be=read(live/'events.jsonl')
    report=dict(frozen=str(frozen),live=str(live),frames=len(b),all_trace_fields_equal=len(a)==len(b) and not mismatches,
        compared_fields=fields,mismatched_frames=mismatches,event_parity=[key(e) for e in ae]==[key(e) for e in be],
        proof_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [frozen/'replay.json',frozen/'tracks.jsonl',live/'summary.json',live/'tracks.jsonl',live/'completion-audit.json']},
        full_live_detector_rerun=True,jetson_validated=False,independent_accuracy_validated=False)
    Path('runs/osnet-frozen-to-live-parity-resume4.json').open('x').write(json.dumps(report,indent=2))
    print(json.dumps(dict(frames=len(b),trace_equal=report['all_trace_fields_equal'],events_equal=report['event_parity'])))


if __name__=='__main__':main()
