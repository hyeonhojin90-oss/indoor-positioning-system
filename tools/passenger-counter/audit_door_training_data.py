"""Count actual unique observations and recording groups, with immutable split/hash evidence."""
import argparse,csv,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path

def audit(manifest):
    manifest=Path(manifest)
    with manifest.open(encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream))
    if not rows:raise ValueError('Empty dataset')
    groups={};digests={};split_rows=defaultdict(list);evidence=[]
    for row in rows:
        group,split=row['session_id'],row['split']
        if not group or split not in ('train','val','test'):raise ValueError('Missing group/split')
        if group in groups and groups[group]!=split:raise ValueError('Recording group leaks between splits')
        groups[group]=split;image=(manifest.parent/row['image']).resolve()
        parts=list(image.parts)
        if 'images' not in parts:raise ValueError('Expected images/labels layout')
        parts[len(parts)-1-parts[::-1].index('images')]='labels';label=Path(*parts).with_suffix('.txt')
        image_hash=hashlib.sha256(image.read_bytes()).hexdigest()
        if image_hash in digests:raise ValueError('Duplicate actual observation; repeated sampling is not new data')
        digests[image_hash]=group;labels=[]
        for line in label.read_text().splitlines():
            values=list(map(float,line.split()))
            if len(values)!=5 or values[0]!=0 or not all(math.isfinite(v) and 0<=v<=1 for v in values[1:]) or min(values[3:])<=0:raise ValueError('Invalid normalized door label')
            _,x,y,w,h=values
            if min(x-w/2,y-h/2)<-1e-6 or max(x+w/2,y+h/2)>1+1e-6:
                raise ValueError('Door label extends outside image')
            if values in labels:
                raise ValueError('Duplicate box label is not an extra observed door')
            labels.append(values)
        record=dict(image=str(image),label=str(label),session_id=group,split=split,image_sha256=image_hash,label_sha256=hashlib.sha256(label.read_bytes()).hexdigest(),positive_boxes=len(labels),empty_label=not labels)
        evidence.append(record);split_rows[split].append(record)
    return dict(manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),unique_images=len(evidence),unique_recording_groups=len(groups),
        splits={s:dict(images=len(split_rows[s]),recording_groups=len({r['session_id'] for r in split_rows[s]}),positive_boxes=sum(r['positive_boxes'] for r in split_rows[s]),empty_label_images=[r['image'] for r in split_rows[s] if r['empty_label']]) for s in ['train','val','test']},
        recording_split={group:split for group,split in sorted(groups.items())},observations=evidence,
        split_leakage_detected=False,duplicate_image_detected=False,
        label_visual_correctness_validated=False,complete_visible_doors_validated=False,human_reviewed=False,
        independent_blind_accuracy_validated=False,
        note='Structural/hash split audit only; synthetic augmentation/repeated sampling is not extra observed people or recording groups. Empty labels must be reviewed visually; unknown/occluded door geometry is not proof of absence.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=audit(a.manifest)
    with a.output.open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:report[k] for k in ['unique_images','unique_recording_groups','splits']}))

if __name__=='__main__':main()
