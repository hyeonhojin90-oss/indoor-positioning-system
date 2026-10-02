"""Render saved canonical/raw tracks over source frames for identity review."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np


def render(source, tracks, frames, output,region=None,track_ids=None):
    if region is not None and not (len(region)==4 and 0<=region[0]<region[2]<=1 and 0<=region[1]<region[3]<=1):
        raise ValueError('Invalid review region')
    wanted=set(frames)
    rows={r['frame']:r for r in tracks if r['frame'] in wanted}
    if set(rows)!=wanted:
        raise ValueError('Missing requested track frames')
    cap=cv2.VideoCapture(str(source))
    if not cap.isOpened():raise ValueError('Cannot open source')
    tiles=[]
    try:
        for frame in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,frame)
            ok,im=cap.read()
            if not ok:raise ValueError(f'Cannot decode {frame}')
            row=rows[frame]
            for tid,b in zip(row.get('raw_ids',[]),row.get('raw_boxes',[])):
                if track_ids is not None and tid not in track_ids:continue
                p=tuple(round(v) for v in b)
                cv2.rectangle(im,p[:2],p[2:],(200,120,30),1)
                cv2.putText(im,f'raw {tid}',(p[0],p[1]+15),0,.45,(200,120,30),1)
            for tid,b in zip(row['ids'],row['boxes']):
                if track_ids is not None and tid not in track_ids:continue
                p=tuple(round(v) for v in b)
                cv2.rectangle(im,p[:2],p[2:],(30,220,80),2)
                cv2.putText(im,str(tid),(p[0],p[1]-5),0,.6,(30,220,80),2)
            for tid,point in zip(row['ids'],row.get('points',[])):
                if track_ids is not None and tid not in track_ids:continue
                if point is not None:cv2.circle(im,tuple(round(v) for v in point),7,(255,0,255),-1)
            if row['door']:
                p=tuple(round(v) for v in row['door'])
                cv2.rectangle(im,p[:2],p[2:],(30,70,255),2)
            if region is not None:
                h,w=im.shape[:2];x1,y1,x2,y2=region
                im=im[round(y1*h):round(y2*h),round(x1*w):round(x2*w)]
            scale=min(540/im.shape[1],800/im.shape[0])
            preview=cv2.resize(im,(round(im.shape[1]*scale),round(im.shape[0]*scale)))
            tile=np.zeros((preview.shape[0]+30,540,3),dtype=np.uint8)
            h,w=preview.shape[:2];left=(540-w)//2
            tile[30:30+h,left:left+w]=preview
            cv2.putText(tile,f'frame {frame}',(8,22),0,.6,(255,255,255),1)
            tiles.append(tile)
        while len(tiles)%3:tiles.append(np.zeros_like(tiles[0]))
        sheet=np.vstack([np.hstack(tiles[i:i+3]) for i in range(0,len(tiles),3)])
        output.parent.mkdir(parents=True,exist_ok=True)
        if not cv2.imwrite(str(output),sheet):raise ValueError('Cannot write image')
    finally:cap.release()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--frames',type=int,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--region',type=float,nargs=4,help='Display-only normalized crop; never changes detection/counting')
    p.add_argument('--track-ids',type=int,nargs='+',help='Display only selected IDs; does not change inference')
    a=p.parse_args()
    rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
    render(a.source,rows,a.frames,a.output,a.region,a.track_ids)
