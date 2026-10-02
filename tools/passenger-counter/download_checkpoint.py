"""Stream a bounded official asset; keep incomplete bytes explicitly separate."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--expected-bytes',type=int,required=True)
    p.add_argument('--deadline-seconds',type=int,default=10800)
    a=p.parse_args()
    if not a.url.startswith('https://github.com/ultralytics/assets/releases/download/'):
        raise ValueError('Use a published official Ultralytics asset URL')
    if not 0<a.expected_bytes<=768*1024*1024 or not 1<=a.deadline_seconds<=10800:
        raise ValueError('Download exceeds task bounds')
    if a.output.exists() or a.output.with_suffix('.source.json').exists():
        raise FileExistsError('Complete checkpoint/provenance already exists')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    partial=a.output.with_suffix(a.output.suffix+'.part')
    state_path=a.output.with_suffix(a.output.suffix+'.download.json')
    offset=partial.stat().st_size if partial.exists() else 0
    if offset:
        state=json.loads(state_path.read_text())
        if state['url']!=a.url or state['expected_bytes']!=a.expected_bytes:
            raise ValueError('Partial-file source mismatch')
    if offset>a.expected_bytes:raise ValueError('Partial file exceeds expected size')
    state=dict(url=a.url,expected_bytes=a.expected_bytes,status='incomplete',bytes=offset)
    state_path.write_text(json.dumps(state,indent=2))
    started=time.monotonic();last_report=started
    try:
        if offset<a.expected_bytes:
            headers={'Range':f'bytes={offset}-'} if offset else {}
            request=urllib.request.Request(a.url,headers=headers)
            with urllib.request.urlopen(request,timeout=45) as response:
                if offset and (response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-')):
                    raise ValueError('Server did not confirm requested resume range')
                declared=response.headers.get('Content-Length')
                if declared is not None and int(declared)!=a.expected_bytes-offset:
                    raise ValueError('Remote file length changed')
                with partial.open('ab' if offset else 'xb') as output:
                    while True:
                        if time.monotonic()-started>a.deadline_seconds:
                            raise TimeoutError('Overall download deadline exceeded')
                        chunk=response.read(256*1024)
                        if not chunk:break
                        if offset+len(chunk)>a.expected_bytes:
                            raise ValueError('Remote bytes exceed expected file size')
                        output.write(chunk);offset+=len(chunk)
                        if time.monotonic()-last_report>=30:
                            output.flush();last_report=time.monotonic()
                            state.update(bytes=offset,elapsed_s=round(last_report-started,1))
                            state_path.write_text(json.dumps(state,indent=2))
                            print(json.dumps(state),flush=True)
        if offset!=a.expected_bytes:raise ValueError('Incomplete response')
        sha=hashlib.sha256()
        with partial.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):sha.update(chunk)
        # Exclusive destination check again before marking bytes as a usable model.
        if a.output.exists():raise FileExistsError('Destination created during download')
        partial.rename(a.output)
        metadata=dict(url=a.url,bytes=offset,sha256=sha.hexdigest(),complete=True,
                      purpose='Official pretrained-model comparison; Orin performance unvalidated')
        a.output.with_suffix('.source.json').write_text(json.dumps(metadata,indent=2))
        state.update(status='complete',bytes=offset)
        state_path.write_text(json.dumps(state,indent=2))
        print(json.dumps(metadata),flush=True)
    except BaseException as exc:
        state.update(status='incomplete',bytes=partial.stat().st_size if partial.exists() else 0,
                     error=f'{type(exc).__name__}: {exc}')
        state_path.write_text(json.dumps(state,indent=2))
        raise


if __name__=='__main__':main()
