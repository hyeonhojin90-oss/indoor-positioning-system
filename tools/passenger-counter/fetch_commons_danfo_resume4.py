"""Bounded author-published Commons videos for separate scene evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
import cv2

SOURCES = [
    ('called.webm', 'A passenger currently boarding a danfo bus after being called by the conductor VP8.webm'),
    ('boarding.webm', 'A passenger boarding a danfo-bus VP8.webm'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    for name, title in SOURCES:
        query = urllib.parse.urlencode(dict(action='query', format='json', prop='imageinfo',
                                            titles='File:' + title, iiprop='url|sha1|size|extmetadata'))
        request = urllib.request.Request('https://commons.wikimedia.org/w/api.php?' + query,
                                         headers={'User-Agent': 'PassengerCounterResearch/0.1 (public video evaluation)'})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        info = next(iter(payload['query']['pages'].values()))['imageinfo'][0]
        metadata = info['extmetadata']
        license_name = metadata['LicenseShortName']['value']
        if license_name != 'CC BY-SA 4.0' or not 0 < info['size'] <= 20 * 1024 * 1024:
            raise ValueError('Different licensed source or download bound')
        url = info['url']
        if not url.startswith('https://upload.wikimedia.org/wikipedia/commons/'):
            raise ValueError('Different original source host')
        dest = args.output / name
        partial = dest.with_suffix('.webm.part')
        downloaded = 0
        request = urllib.request.Request(url, headers={'User-Agent': 'PassengerCounterResearch/0.1'})
        with urllib.request.urlopen(request, timeout=45) as response, partial.open('xb') as stream:
            while chunk := response.read(256 * 1024):
                downloaded += len(chunk)
                if downloaded > info['size']:
                    raise ValueError('Unexpected original size')
                stream.write(chunk)
        data = partial.read_bytes()
        if downloaded != info['size'] or hashlib.sha1(data).hexdigest() != info['sha1']:
            raise ValueError('Original source size/SHA1 mismatch')
        partial.rename(dest)
        cap = cv2.VideoCapture(str(dest))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = 0
        while cap.read()[0]:
            frames += 1
        cap.release()
        if not frames or fps <= 0:
            raise ValueError('Original video cannot be decoded')
        report = dict(title=title, page=info['descriptionurl'], url=url,
                      author_html=metadata.get('Artist', {}).get('value'),
                      license=license_name, license_url=metadata['LicenseUrl']['value'],
                      bytes=len(data), sha1=info['sha1'], original_sha1_verified=True,
                      sha256=hashlib.sha256(data).hexdigest(), decoded_frames=frames, source_fps=fps,
                      dimensions=[info['width'], info['height']], alterations='Original source bytes retained',
                      training_used=False, whole_ground_truth_complete=False, inference_performed=False)
        dest.with_suffix('.source.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(dict(name=name, frames=frames, fps=fps, sha256=report['sha256'])), flush=True)


if __name__ == '__main__':
    main()
