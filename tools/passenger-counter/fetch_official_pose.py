"""Bounded official model download with source/hash provenance."""
import argparse,hashlib,json,urllib.request
from pathlib import Path

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--variant',choices=['n','m'],required=True);a=p.parse_args()
    dest=Path('models')/f'yolo11{a.variant}-pose.pt'
    if dest.exists():raise FileExistsError(dest)
    url=f'https://github.com/ultralytics/assets/releases/download/v8.3.0/{dest.name}'
    total=0
    with urllib.request.urlopen(url,timeout=45) as r,dest.open('xb') as f:
        while chunk:=r.read(1024*1024):
            total+=len(chunk)
            if total>64*1024*1024:raise ValueError('Unexpected model size')
            f.write(chunk)
    info=dict(url=url,file=str(dest),bytes=total,sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    with Path(f'runs/yolo11{a.variant}-pose-download-20261001.json').open('x') as f:json.dump(info,f,indent=2)
    print(json.dumps(info))
