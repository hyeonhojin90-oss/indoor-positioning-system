"""Derived training views only; holdout splits and recording identities stay intact."""
import argparse,csv,json,hashlib
from pathlib import Path
import cv2,numpy as np

def read_image(path):
    frame=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
    if frame is None:raise ValueError(f'Cannot decode image: {path}')
    return frame

def write_image(path,frame):
    ok,encoded=cv2.imencode(path.suffix,frame)
    if not ok:raise ValueError(f'Cannot encode image: {path}')
    encoded.tofile(path)

def moved_label(values,shift=0,flip=False):
    cls,cx,cy,w,h=values
    if flip:cx=1-cx
    left,right=max(0,cx-w/2+shift),min(1,cx+w/2+shift)
    if right<=left or (right-left)<.5*w:return None
    return [cls,(left+right)/2,cy,right-left,h]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);(a.output/'images').mkdir();(a.output/'labels').mkdir()
    rows=list(csv.DictReader(a.manifest.open(encoding='utf-8-sig')));generated=[];previews=[]
    for row in rows:
        image=(a.manifest.parent/row['image']).resolve();label=Path(str(image).replace('/images/','/labels/').replace('\\images\\','\\labels\\')).with_suffix('.txt')
        frame=read_image(image);height,width=frame.shape[:2]
        labels=[list(map(float,x.split())) for x in label.read_text().splitlines() if x.strip()]
        variants=[('original',0,False)] if row['split']!='train' else [('original',0,False),('left',-.15,False),('right',.15,False),('flip',0,True)]
        for name,offset,flip in variants:
            pixels=round(offset*width);actual_offset=pixels/width
            view=cv2.flip(frame,1) if flip else frame.copy()
            if pixels:view=cv2.warpAffine(view,np.float32([[1,0,pixels],[0,1,0]]),(width,height),borderValue=(114,114,114))
            adjusted=[v for values in labels if (v:=moved_label(values,actual_offset,flip)) is not None]
            stem=image.stem+'-'+name;dest=a.output/'images'/f'{stem}.jpg';lab=a.output/'labels'/f'{stem}.txt'
            if name=='original':dest.write_bytes(image.read_bytes())
            else:write_image(dest,view)
            if name=='original':lab.write_bytes(label.read_bytes())
            else:lab.write_text(''.join(' '.join(f'{v:.8f}' for v in value)+'\n' for value in adjusted))
            generated.append(dict(row,image='images/'+dest.name,augmentation=name,dx=pixels,parent_image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),parent_label_sha256=hashlib.sha256(label.read_bytes()).hexdigest()))
            if '32245403' in stem and not previews and name=='original':selected=image.stem
            if 'selected' in locals() and image.stem==selected:
                for _,cx,cy,w,h in adjusted:
                    cv2.rectangle(view,(round((cx-w/2)*width),round((cy-h/2)*height)),(round((cx+w/2)*width),round((cy+h/2)*height)),(0,255,255),3)
                preview=cv2.resize(view,(360,640));cv2.putText(preview,name,(10,25),0,.7,(0,0,255),2);previews.append(preview)
    with (a.output/'manifest.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(generated[0]));writer.writeheader();writer.writerows(generated)
    if len(previews)==4:write_image(a.output/'label-review.jpg',np.vstack([np.hstack(previews[:2]),np.hstack(previews[2:])]))
    summary=dict(original_manifest=str(a.manifest),original_manifest_sha256=hashlib.sha256(a.manifest.read_bytes()).hexdigest(),split_counts={s:sum(r['split']==s for r in generated) for s in ('train','val','test')},derived_not_independent=True,new_human_annotations=False,validation_test_images_unchanged=True)
    (a.output/'augmentation.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
