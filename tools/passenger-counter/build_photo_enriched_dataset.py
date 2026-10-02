"""Add frozen source-reviewed photographs without changing old splits/labels."""
import csv,hashlib,json,shutil
from pathlib import Path
import cv2,numpy as np
from probe_door_photos import validate_review

def main():
    old=Path('data/bus-portal-bootstrap-20260930')
    out=Path('data/bus-portal-photo-enriched-20261001-r2')
    out.mkdir(exist_ok=False);(out/'images').mkdir();(out/'labels').mkdir()
    rows=[];sources=[];seen=set();groups={}
    for r in csv.DictReader((old/'manifest.csv').open(encoding='utf-8-sig')):
        src=old/r['image'];name=src.name
        dest=out/'images'/name;shutil.copyfile(src,dest)
        label=old/'labels'/Path(name).with_suffix('.txt')
        shutil.copyfile(label,out/'labels'/label.name)
        rows.append(dict(image='images/'+name,session_id=r['session_id'],split=r['split']))
        seen.add(hashlib.sha256(src.read_bytes()).hexdigest());groups[r['session_id']]=r['split']
    specs=[('data/commons-door-photos-20261001-r2','boston-mbta57-20230630.jpg','train'),
           ('data/commons-door-photos-20261001-r2-extra','nigeria-boarding-20200215.jpg','train'),
           ('data/commons-door-photos-20261001-r2','vancouver-boarding-20111126.jpg','val'),
           ('data/commons-door-photos-20261001-r2-extra','kenya-matatu-20200320.jpg','test')]
    for root,name,split in specs:
        root=Path(root);review=root/('portal-review-validated-r2.json' if root.name.endswith('extra') else 'portal-review.json')
        items=validate_review(json.loads(review.read_text(encoding='utf-8')))
        r=next(x for x in items if x['name']==name);source=root/name
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        assert digest==r['sha256'] and digest not in seen
        group='commons-photo-'+Path(name).stem
        assert group not in groups;groups[group]=split;seen.add(digest)
        image=cv2.imdecode(np.fromfile(source,dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None:raise ValueError('Cannot decode source photograph')
        h,w=image.shape[:2]
        boxes=[r['target_box']]+[d['box'] for d in r.get('other_visible_doors',[])]
        if any(b is None for b in boxes):raise ValueError('Unlocalizable positive cannot be a negative training image')
        labels=[]
        for x1,y1,x2,y2 in boxes:
            assert 0<=x1<x2<=w and 0<=y1<y2<=h
            labels.append(f'0 {(x1+x2)/(2*w):.8f} {(y1+y2)/(2*h):.8f} {(x2-x1)/w:.8f} {(y2-y1)/h:.8f}')
        shutil.copyfile(source,out/'images'/name)
        (out/'labels'/Path(name).with_suffix('.txt')).write_text('\n'.join(labels)+'\n')
        rows.append(dict(image='images/'+name,session_id=group,split=split))
        sources.append(dict(image=name,split=split,source_sha256=digest,review_sha256=hashlib.sha256(review.read_bytes()).hexdigest(),boxes=boxes))
    with (out/'manifest.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['image','session_id','split']);writer.writeheader();writer.writerows(rows)
    report=dict(original_manifest_sha256=hashlib.sha256((old/'manifest.csv').read_bytes()).hexdigest(),
        original_images_and_labels_unchanged=True,new_sources=sources,
        split_counts={s:sum(r['split']==s for r in rows) for s in ['train','val','test']},
        assistant_annotations=True,human_reviewed=False,
        holdout_previously_diagnosed=True,blind_independent_accuracy_validation=False,
        unlocalizable_photos_excluded=True,
        note='Two new training recording groups; Vancouver validation and Kenya test never enter training. Existing splits unchanged. These photos were diagnosed before this training plan, so evaluation is not blind.')
    (out/'provenance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()
