"""Persist original-frame identity reviews for completed development comparisons."""
import json
from pathlib import Path
from evaluate_events import evaluate_windows

cases={
 'green-person-small960-resume-frozen':[
  (41,17,'in','uncertain',None,'Olive-shirt approach before unchanged window; early foot clipping.'),
  (46,17,'out','uncertain',None,'Same olive-shirt waiting/boarding; no supported alighting.'),
  (65,17,'in','accepted','olive-shirt-white-bag','Original source montage and unchanged window.'),
  (68,36,'in','uncertain',None,'Partial box overlapping entrance; brown-shirt still outside. Does not recover brown boarding.'),
  (179,88,'in','accepted','grey-hair-backpack','Original montage.'),
  (332,122,'in','accepted','yellow-bag-umbrella','Original montage.'),
  (355,127,'in','accepted','white-shirt-grey-shorts','Original montage.')],
 'green-person-pose-resume-frozen':[
  (66,19,'in','accepted','olive-shirt-white-bag','Original montage.'),
  (182,40,'in','accepted','grey-hair-backpack','Original montage.'),
  (333,50,'in','accepted','yellow-bag-umbrella','Original montage.'),
  (357,52,'in','accepted','white-shirt-grey-shorts','Original montage.')]
}
read=lambda p:[json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
for name,items in cases.items():
    identities=[dict(frame=f,track_id=t,direction=d,status=s,person=p,note=n) for f,t,d,s,p,n in items]
    review=Path('reviews')/(name+'-identity.jsonl')
    with review.open('x',encoding='utf-8') as f:
        for item in identities:f.write(json.dumps(item)+'\n')
    run=Path('runs')/name
    result=evaluate_windows(read(run/'events.jsonl'),read(Path('reviews/green-development-windows.jsonl')),0,identities)
    with (run/'identity-evaluation.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(name,result['matched_reviewed_events'],result['reviewed_events'])
