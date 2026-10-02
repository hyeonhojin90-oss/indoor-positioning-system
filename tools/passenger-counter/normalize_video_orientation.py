"""Keep original bytes; make an explicit constant-rotation video derivative."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--clockwise', type=int, choices=[90, 180, 270], required=True)
    a = p.parse_args()
    if a.output.exists() or a.output.with_suffix('.source.json').exists():
        raise FileExistsError('Preserve existing derivative')
    metadata = json.loads(a.source.with_suffix('.source.json').read_text(encoding='utf-8'))
    original_sha = hashlib.sha256(a.source.read_bytes()).hexdigest()
    if original_sha != metadata['sha256']:
        raise ValueError('Changed original source')
    cap = cv2.VideoCapture(str(a.source))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width, height = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    shape = (height, width) if a.clockwise in (90, 270) else (width, height)
    writer = cv2.VideoWriter(str(a.output), cv2.VideoWriter_fourcc(*'mp4v'), fps, shape)
    if not writer.isOpened():
        raise ValueError('Cannot create derivative')
    rotation = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[a.clockwise]
    count = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            writer.write(cv2.rotate(frame, rotation))
            count += 1
    finally:
        cap.release()
        writer.release()
    if count != metadata['decoded_frames'] or original_sha != hashlib.sha256(a.source.read_bytes()).hexdigest():
        raise ValueError('Different original sequence or changed source')
    cap = cv2.VideoCapture(str(a.output))
    actual = 0
    while cap.read()[0]:
        actual += 1
    cap.release()
    if actual != count:
        raise ValueError('Incomplete encoded derivative')
    report = dict(original_source=str(a.source), original_sha256=original_sha,
                  page=metadata['page'], author_html=metadata['author_html'], license=metadata['license'],
                  license_url=metadata['license_url'], clockwise_degrees=a.clockwise,
                  alterations='Constant rotation and mp4v encoding; audio omitted; no frame selection or retiming',
                  frames=count, source_fps=fps, dimensions=list(shape),
                  sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(), training_used=False,
                  source_identity_preserved=True, whole_ground_truth_complete=False)
    a.output.with_suffix('.source.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(output=str(a.output), frames=count, fps=fps)))


if __name__ == '__main__':
    main()
