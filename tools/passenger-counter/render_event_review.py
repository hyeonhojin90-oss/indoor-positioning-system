"""Render exact source frames and tracked boxes for a completed run's review."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np


def render(run, output, frames=None, track_id=None):
    summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
    source = Path(summary['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != summary['source_sha256']:
        raise ValueError('Source hash changed')
    events = [json.loads(x) for x in (run / 'events.jsonl').read_text().splitlines()]
    rows = {r['frame']: r for r in map(json.loads, (run / 'tracks.jsonl').read_text().splitlines())}
    if frames is None:
        frames = sorted({int(e[k]) for e in events for k in ('frame', 'observation_frame') if k in e})
    if not frames:
        raise ValueError('No event frames to render')
    cap = cv2.VideoCapture(str(source))
    tiles = []
    try:
        for fid in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
            ok, image = cap.read()
            if not ok:
                raise ValueError(f'Missing source frame {fid}')
            row = rows[fid]
            if row['door']:
                x1, y1, x2, y2 = map(round, row['door'])
                cv2.rectangle(image, (x1,y1), (x2,y2), (0,80,255), 2)
            for tid, box in zip(row['ids'], row['boxes']):
                if track_id is not None and tid != track_id:
                    continue
                x1, y1, x2, y2 = map(round, box)
                cv2.rectangle(image,(x1,y1),(x2,y2),(80,230,50),2)
                cv2.putText(image,str(tid),(x1,y1-4),cv2.FONT_HERSHEY_SIMPLEX,.6,(80,230,50),2)
            scale = min(480/image.shape[1], 780/image.shape[0])
            resized = cv2.resize(image, (round(image.shape[1]*scale), round(image.shape[0]*scale)))
            tile = np.zeros((30 + resized.shape[0],480,3), dtype=np.uint8)
            tile[30:30+resized.shape[0],:resized.shape[1]] = resized
            cv2.putText(tile,f'frame {fid}',(8,22),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1)
            tiles.append(tile)
    finally:
        cap.release()
    columns = min(3,len(tiles))
    tile_height = max(tile.shape[0] for tile in tiles)
    canvas = np.zeros((((len(tiles)+columns-1)//columns)*tile_height,columns*480,3),dtype=np.uint8)
    for i,tile in enumerate(tiles):
        top=(i//columns)*tile_height
        canvas[top:top+tile.shape[0],(i%columns)*480:(i%columns+1)*480] = tile
    ok, encoded = cv2.imencode(output.suffix,canvas)
    if not ok:
        raise ValueError('Cannot encode review')
    with output.open('xb') as f:
        f.write(encoded.tobytes())


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--frames',type=int,nargs='+')
    p.add_argument('--track-id',type=int)
    a=p.parse_args();render(a.run,a.output,a.frames,a.track_id)
