"""Qualitative door-only check on a separate, untrained scene."""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(__file__).resolve().parent/'runs'/'settings'))
import cv2
from grounding_detector import GroundingDoorDetector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='data/wiki-man-boarding.webm')
    parser.add_argument('--output', required=True, help='New output directory')
    parser.add_argument('--frames', type=int, nargs='+', default=[50,75,100,125])
    parser.add_argument('--resize-width', type=int, default=0,
                        help='Resize decoded frames before inference; 0 keeps original size')
    args = parser.parse_args()
    if args.resize_width < 0 or any(frame < 0 for frame in args.frames):
        raise ValueError('Frame indices and resize width must be nonnegative')
    source = Path(args.source)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    model = GroundingDoorDetector(
        'models/hf/models--IDEA-Research--grounding-dino-tiny/snapshots/a2bb814dd30d776dcf7e30523b00659f4f141c71',
        'a bus door.')
    cap = cv2.VideoCapture(str(source))
    rows = []
    for n in args.frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, n)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f'Cannot decode frame {n}')
        if args.resize_width:
            h, w = frame.shape[:2]
            frame = cv2.resize(frame, (args.resize_width, round(h*args.resize_width/w)))
        result = model.predict(frame, conf=.35)[0]
        boxes = result.boxes.xyxy.cpu().tolist()
        scores = result.boxes.conf.cpu().tolist()
        for box, score in zip(boxes, scores):
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,255), 3)
            cv2.putText(frame, f'door {score:.2f}', (x1,y1), 0, .8, (0,0,255), 2)
        cv2.imwrite(str(out/f'frame-{n}.jpg'), frame)
        rows.append({'frame': n, 'size': [frame.shape[1],frame.shape[0]],
                     'boxes': boxes, 'scores': scores})
        print(n, boxes, scores, flush=True)
    cap.release()
    (out/'detections.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
