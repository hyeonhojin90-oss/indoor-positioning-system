"""Add one source-reviewed middle-door photo; preserve every original split and label."""
import csv,hashlib,json,shutil
from pathlib import Path
from probe_door_photos import validate_review

def main():
    old=Path('data/bus-portal-photo-enriched-20261001-r2');source=Path('data/commons-door-photo-batch-resume3-r2')
    out=Path('data/bus-portal-middle-door-enriched-resume3');out.mkdir(exist_ok=False)
    (out/'images').mkdir();(out/'labels').mkdir();rows=[]
    for r in csv.DictReader((old/'manifest.csv').open()):
        name=Path(r['image']).name;shutil.copyfile(old/r['image'],out/'images'/name)
        label=Path(name).with_suffix('.txt');shutil.copyfile(old/'labels'/label,out/'labels'/label);rows.append(r)
    review=json.loads((source/'portal-review.json').read_text());items=validate_review(review)
    added=next(r for r in items if r['name']=='london-middle-door-2020.jpg')
    name=added['name'];image=source/name
    if hashlib.sha256(image.read_bytes()).hexdigest()!=added['sha256']:raise ValueError('Photo hash differs')
    box=added['target_box'];w,h=1280,1690
    if not 0<=box[0]<box[2]<=w or not 0<=box[1]<box[3]<=h:raise ValueError('Photo label outside source')
    shutil.copyfile(image,out/'images'/name)
    x1,y1,x2,y2=box
    (out/'labels'/Path(name).with_suffix('.txt')).write_text(f'0 {(x1+x2)/(2*w):.8f} {(y1+y2)/(2*h):.8f} {(x2-x1)/w:.8f} {(y2-y1)/h:.8f}\n')
    rows.append(dict(image='images/'+name,session_id='commons-photo-london-middle-door-2020',split='train'))
    with (out/'manifest.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['image','session_id','split']);writer.writeheader();writer.writerows(rows)
    proof=dict(original_manifest_sha256=hashlib.sha256((old/'manifest.csv').read_bytes()).hexdigest(),
        original_images_labels_splits_preserved=True,added_train_recordings=1,added_train_images=1,
        new_image_sha256=added['sha256'],review_sha256=hashlib.sha256((source/'portal-review.json').read_bytes()).hexdigest(),
        excluded_unlocalizable=[r['name'] for r in items if r['target_box'] is None],
        split_counts={split:sum(r['split']==split for r in rows) for split in ['train','val','test']},
        commons_boarding_video_used_for_training=False,pink_test_recording_not_added_to_training=True,
        assistant_annotations=True,human_reviewed=False,independent_blind_accuracy_validated=False,
        note='One real extra recording, not a large dataset. Existing diagnosed validation/test stay unchanged; full-video regressions remain required.')
    (out/'provenance.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))

if __name__=='__main__':main()
