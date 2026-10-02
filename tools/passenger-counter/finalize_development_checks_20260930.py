"""Persist reviewed development comparisons; does not claim independent accuracy."""
import json
from pathlib import Path
from audit_completed_run import audit
from evaluate_events import evaluate_windows

def read(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]

def write(path, value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2)

cases = [
 ('green-small-separate-bus-v2-full-20260930','green-development-windows.jsonl',read('reviews/green-person-small-frozen-identity.jsonl')),
 ('green-person-small-full-20260930','green-development-windows.jsonl',[
  dict(frame=f,track_id=t,direction='in',status='accepted',person=p,note='Original event montage and unchanged review window; development only.')
  for f,t,p in [(173,73,'grey-hair-backpack'),(260,1,'teal-shirt'),(332,91,'yellow-bag-umbrella'),(375,95,'white-shirt-grey-shorts')]]),
 ('city-person-small-full-20260930','city-independent-windows.jsonl',[
  dict(frame=368,track_id=46,direction='out',status='accepted',person='pink-hat-child',note='Original montage; child leaving behind red coat.'),
  dict(frame=377,track_id=46,direction='in',status='uncertain',note='Same child ID reverses after 9 frames; no supported reboarding in source montage. Reject additional success.'),
  dict(frame=421,track_id=2,direction='in',status='accepted',person='red-coat',note='Source event montage; unchanged review window.')]),
 ('city-reid-occlusion-frozen-20260930','city-independent-windows.jsonl',[
  dict(frame=365,track_id=21,direction='out',status='accepted',person='pink-hat-child',note='Same source event as previously reviewed m/ReID, original time retained.'),
  dict(frame=422,track_id=2,direction='in',status='accepted',person='red-coat',note='Same source event as previously reviewed m/ReID, original time retained.')]),
]
for name,truth,identities in cases:
    run=Path('runs')/name
    write(run/'completion-audit-final.json',audit(run))
    review=Path('reviews')/(name+'-identity.jsonl')
    with review.open('x',encoding='utf-8') as f:
        for item in identities:f.write(json.dumps(item)+'\n')
    result=evaluate_windows(read(run/'events.jsonl'),read(Path('reviews')/truth),0,identities)
    write(run/'identity-evaluation-final.json',result)
    print(name,result['matched_reviewed_events'],result['reviewed_events'])
for name in ['people-small-separate-bus-negative-20260930','shift-margin-onnx-full-20260930']:
    write(Path('runs')/name/'completion-audit-final.json',audit(Path('runs')/name))
