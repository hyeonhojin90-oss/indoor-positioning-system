"""Add four reviewed frames to TRAIN only; preserve original grouped val/test."""
import csv
import hashlib
import json
from pathlib import Path
import shutil


def main():
    import cv2
    base = Path('data/bus-portal-middle-door-enriched-resume3')
    output = Path('data/bus-portal-danfo-development-resume4-r2')
    source = Path('data/commons-danfo-resume4/called-upright.mp4')
    provenance = json.loads(source.with_suffix('.source.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != provenance['sha256']:
        raise ValueError('Source changed')
    # Assistant annotations from raw frames, after baseline inference. They are
    # development labels, neither human-verified nor independent test evidence.
    labels = {0: [100,49,150,142], 50: [99,50,153,148],
              100: [115,19,169,112], 150: [51,26,99,116]}
    output.mkdir(parents=True,exist_ok=False)
    (output/'images').mkdir(); (output/'labels').mkdir(); (output/'overlays').mkdir()
    with (base/'manifest.csv').open(encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    before = {}
    for row in rows:
        image = base/row['image']
        label = base/'labels'/Path(row['image']).with_suffix('.txt').name
        shutil.copy2(image,output/row['image'])
        shutil.copy2(label,output/'labels'/label.name)
        before[row['image']] = dict(split=row['split'], session_id=row['session_id'],
            image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
            label_sha256=hashlib.sha256(label.read_bytes()).hexdigest())
    cap = cv2.VideoCapture(str(source)); added = []
    try:
        for fid,box in labels.items():
            cap.set(cv2.CAP_PROP_POS_FRAMES,fid); ok,frame=cap.read()
            if not ok:raise ValueError('Cannot read training source')
            h,w=frame.shape[:2]; x1,y1,x2,y2=box
            if not 0<=x1<x2<=w or not 0<=y1<y2<=h:raise ValueError('Invalid label')
            name=f'commons-danfo-called-{fid:06d}.jpg'
            image=output/'images'/name
            if not cv2.imwrite(str(image),frame):raise ValueError('Cannot save training frame')
            values=[(x1+x2)/(2*w),(y1+y2)/(2*h),(x2-x1)/w,(y2-y1)/h]
            label=output/'labels'/Path(name).with_suffix('.txt')
            label.write_text('0 '+' '.join(f'{v:.9f}' for v in values)+'\n')
            row=dict(image='images/'+name,session_id='commons-orekoko-danfo-session-unknown',split='train')
            rows.append(row)
            cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),1)
            if not cv2.imwrite(str(output/'overlays'/name),frame):raise ValueError('Cannot save overlay')
            added.append(dict(**row,frame=fid,box=box,
                image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                label_sha256=hashlib.sha256(label.read_bytes()).hexdigest()))
    finally:cap.release()
    for row in rows:
        if row['image'] in before:
            old=before[row['image']]
            image=output/row['image'];label=output/'labels'/image.with_suffix('.txt').name
            if row['split']!=old['split'] or row['session_id']!=old['session_id'] or hashlib.sha256(image.read_bytes()).hexdigest()!=old['image_sha256'] or hashlib.sha256(label.read_bytes()).hexdigest()!=old['label_sha256']:
                raise ValueError('Original source/split/label changed')
    with (output/'manifest.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['image','session_id','split']);writer.writeheader();writer.writerows(rows)
    report=dict(source=str(source),source_sha256=digest,source_provenance=provenance,
        annotations=added,originals=before,original_data_and_splits_preserved=True,
        same_author_danfo_videos_grouped_conservatively=True,
        called_video_becomes_development=True, boarding_video_independent_holdout_claim=False,
        author='Oreoluwa Adetimehin (Orekoko)',license='CC BY-SA 4.0',
        alterations='clockwise90 video derivative, selected JPEG frames, assistant door annotations',
        annotation_license='CC BY-SA 4.0',human_reviewed=False,
        labels_after_baseline_inference=True, annotation_bounds_approximate=True,
        occluded_frame_edges_not_pixel_verified=True, independent_accuracy_validated=False)
    (output/'provenance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(images=len(rows),added=len(added),train_only=True)))


if __name__=='__main__':main()
