"""Export explicit source-reviewed portal boxes, never detector pseudo-labels."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--annotations',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    records=[json.loads(x) for x in a.annotations.read_text().splitlines()]
    groups={};sources={};seen=set();tiles=[];manifest=[]
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'images').mkdir();(a.output/'labels').mkdir()
    for r in records:
        session,split=r['session_id'],r['split']
        if split not in ('train','val','test'):raise ValueError('Invalid split')
        if session in groups and groups[session]!=split:raise ValueError('Session leakage')
        groups[session]=split;source=Path(r['source'])
        digest=sources.setdefault(str(source),hashlib.sha256(source.read_bytes()).hexdigest())
        key=(digest,r['frame'])
        if key in seen:raise ValueError('Repeated source frame')
        seen.add(key)
        cap=cv2.VideoCapture(str(source))
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES,r['frame']);ok,im=cap.read()
            if not ok:raise ValueError('Cannot decode source frame')
        finally:cap.release()
        h,w=im.shape[:2];labels=[];preview=im.copy()
        for x1,y1,x2,y2 in r['boxes']:
            if not (0<=x1<x2<=w and 0<=y1<y2<=h):raise ValueError('Box outside image')
            labels.append(f'0 {(x1+x2)/(2*w):.8f} {(y1+y2)/(2*h):.8f} {(x2-x1)/w:.8f} {(y2-y1)/h:.8f}')
            cv2.rectangle(preview,(x1,y1),(x2,y2),(20,240,255),2)
        name=f"{session}-{r['frame']:06d}"
        if not cv2.imwrite(str(a.output/'images'/f'{name}.jpg'),im):raise ValueError('Cannot write image')
        (a.output/'labels'/f'{name}.txt').write_text('\n'.join(labels)+ ('\n' if labels else ''))
        manifest.append({'image':f'images/{name}.jpg','session_id':session,'split':split,
                         'source_sha256':digest,'review_status':'assistant_visual_bootstrap'})
        scale=min(420/w,550/h);small=cv2.resize(preview,(round(w*scale),round(h*scale)))
        tile=np.zeros((580,420,3),np.uint8);sh,sw=small.shape[:2];left=(420-sw)//2
        tile[30:30+sh,left:left+sw]=small
        cv2.putText(tile,f"{session} f{r['frame']} {split}",(4,21),0,.43,(255,255,255),1)
        tiles.append(tile)
    with (a.output/'manifest.csv').open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(manifest[0]));writer.writeheader();writer.writerows(manifest)
    while len(tiles)%3:tiles.append(np.zeros_like(tiles[0]))
    for i in range(0,len(tiles),6):
        subset=tiles[i:i+6]
        cv2.imwrite(str(a.output/f'review-{i//6}.jpg'),np.vstack([np.hstack(subset[j:j+3]) for j in range(0,len(subset),3)]))
    (a.output/'annotation-provenance.json').write_text(json.dumps({'annotations':records,'source_sha256':sources,
        'reviewer':'assistant visual review, no independent human verification',
        'label_definition':'whole bus passenger portal including threshold, open or closed; exclude glass-only leaf/window',
        'development_footage':True,'independent_accuracy_validated':False},indent=2))
    print(json.dumps({'images':len(manifest),'splits':{s:sum(r['split']==s for r in manifest) for s in ('train','val','test')}}))


if __name__=='__main__':main()
