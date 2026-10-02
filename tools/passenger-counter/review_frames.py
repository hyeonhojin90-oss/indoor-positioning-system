"""Extract numbered source frames for event review, without detector overlays."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--stop', type=int, default=0)
    parser.add_argument('--step', type=int, default=15)
    args = parser.parse_args()
    if args.start < 0 or args.stop < 0 or args.step < 1:
        parser.error('Frame bounds must be nonnegative and step positive')
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(str(args.source))
    if not cap.isOpened():
        raise RuntimeError('Cannot open source')
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    stop = min(args.stop or total, total)
    if args.start >= stop or fps <= 0:
        cap.release()
        raise ValueError('Empty frame range or invalid FPS')
    args.output.mkdir(parents=True, exist_ok=False)
    tiles = []
    try:
        for frame_id in range(args.start, stop, args.step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f'Cannot decode frame {frame_id}')
            if not cv2.imwrite(str(args.output/f'frame-{frame_id:04d}.jpg'), frame):
                raise RuntimeError('Cannot save review frame')
            h,w = frame.shape[:2]
            scale = min(270/w, 452/h)
            preview = cv2.resize(frame, (max(1,round(w*scale)),max(1,round(h*scale))))
            tile = np.zeros((480,270,3),dtype=np.uint8)
            ph,pw = preview.shape[:2]
            left = (270-pw)//2
            tile[28:28+ph,left:left+pw] = preview
            cv2.rectangle(tile,(0,0),(270,28),(0,0,0),-1)
            cv2.putText(tile,f'{frame_id} / {frame_id/fps:.3f}s',(5,20),
                        cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1)
            tiles.append(tile)
            if len(tiles) == 12:
                sheet = np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,12,4)])
                cv2.imwrite(str(args.output/f'sheet-{frame_id:04d}.jpg'),sheet)
                tiles = []
        if tiles:
            last = frame_id
            tiles.extend([np.zeros_like(tiles[0]) for _ in range(12-len(tiles))])
            sheet = np.vstack([np.hstack(tiles[i:i+4]) for i in range(0,12,4)])
            cv2.imwrite(str(args.output/f'sheet-{last:04d}.jpg'),sheet)
    finally:
        cap.release()


if __name__ == '__main__':
    main()
