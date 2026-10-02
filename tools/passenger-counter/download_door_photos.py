"""Bounded public image acquisition with per-source attribution, no access bypass."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request


def acquire(row, root):
    path = root / row['name']
    if path.name != row['name'] or path.exists():
        raise ValueError('Unsafe name or existing destination')
    try:
        req = urllib.request.Request(row['url'],headers={'User-Agent':'PassengerCounterResearch/0.1 (public image evaluation)'})
        with urllib.request.urlopen(req,timeout=25) as response:
            content = response.read(8*1024*1024+1)
        if len(content)>8*1024*1024:
            raise ValueError('Image exceeds download bound')
        import cv2
        import numpy as np
        im = cv2.imdecode(np.frombuffer(content,dtype=np.uint8),cv2.IMREAD_COLOR)
        if im is None:
            raise ValueError('Response is not a decodable image')
        path.write_bytes(content)
        result = dict(row,status='downloaded',sha256=hashlib.sha256(content).hexdigest(),
                      bytes=len(content),dimensions=[im.shape[1],im.shape[0]],
                      alterations='Wikimedia-provided 1280px thumbnail; file bytes retained')
    except Exception as exc:
        result = dict(row,status='failed',error=f'{type(exc).__name__}: {exc}')
    print(json.dumps(result,ensure_ascii=True),flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    rows=json.loads(a.sources.read_text())
    if not 1<=len(rows)<=10:
        raise ValueError('Bound this acquisition to ten sources')
    a.output.mkdir(parents=True,exist_ok=False)
    with ThreadPoolExecutor(max_workers=3) as executor:
        result=list(executor.map(lambda r:acquire(r,a.output),rows))
    (a.output/'provenance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':main()
