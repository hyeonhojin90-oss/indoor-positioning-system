"""Import published labels, splitting by filename date rather than nearby frames.

This audits structure and samples visually; it does not certify every annotation.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import zipfile
import cv2
import numpy as np


def main():
    dest = Path('data/public-doors-date-split')
    dest.mkdir(exist_ok=False)
    (dest/'images').mkdir()
    (dest/'labels').mkdir()
    rows, excluded, seen = [], [], set()
    with zipfile.ZipFile('data/doors-detection.zip') as z:
        names = set(z.namelist())
        for name in sorted(names):
            if not name.lower().endswith(('.jpg','.png','.jpeg')):
                continue
            date = re.search(r'20\d{6}',Path(name).name)
            label = name.replace('/images/','/labels/').rsplit('.',1)[0]+'.txt'
            if date is None or label not in names:
                excluded.append({'name':name,'reason':'unknown date or missing label'})
                continue
            raw = z.read(name)
            digest = hashlib.sha256(raw).hexdigest()
            if digest in seen:
                excluded.append({'name':name,'reason':'duplicate content'})
                continue
            im = cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
            if im is None:
                raise ValueError(name)
            lines = z.read(label).decode().splitlines()
            for line in lines:
                values = list(map(float,line.split()))
                if len(values)!=5 or values[0]!=0 or not all(np.isfinite(values)) or not all(0<=v<=1 for v in values[1:]) or min(values[3:])<=0:
                    raise ValueError(f'Bad label {label}')
            seen.add(digest)
            d = date.group()
            split = 'val' if d=='20190626' else 'test' if d=='20190701' else 'train'
            basename = Path(name).name
            (dest/'images'/basename).write_bytes(raw)
            (dest/'labels'/Path(basename).with_suffix('.txt')).write_text('\n'.join(lines),encoding='utf-8')
            rows.append({'image':f'images/{basename}','session_id':d,'split':split})
    with (dest/'manifest.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['image','session_id','split']); w.writeheader(); w.writerows(rows)
    audit={'source':'https://www.kaggle.com/datasets/sayedmohamed1/doors-detection',
           'source_zip_sha256':hashlib.sha256(Path('data/doors-detection.zip').read_bytes()).hexdigest(),
           'counts':{s:sum(r['split']==s for r in rows) for s in ['train','val','test']},
           'excluded':excluded,'annotation_review':'source labels; format checked; contact sheet sample only',
           'split_limit':'filename dates are proxy groups; same physical doors may recur across dates'}
    (dest/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    # Sample 16 images across dates, overlay labels before training.
    tiles=[]
    sample=[rows[i] for i in np.linspace(0,len(rows)-1,16,dtype=int)]
    for row in sample:
        file=dest/row['image']; im=cv2.imread(str(file)); h,w=im.shape[:2]
        for line in (dest/'labels'/file.with_suffix('.txt').name).read_text().splitlines():
            _,x,y,bw,bh=map(float,line.split())
            cv2.rectangle(im,(int((x-bw/2)*w),int((y-bh/2)*h)),(int((x+bw/2)*w),int((y+bh/2)*h)),(0,255,0),3)
        im=cv2.resize(im,(320,240)); cv2.putText(im,file.stem,(4,20),0,.35,(0,0,255),1);tiles.append(im)
    cv2.imwrite(str(dest/'review.jpg'),np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,16,4)]))
    print(json.dumps(audit['counts']))


if __name__=='__main__':
    main()
