"""Verify local bundle file hashes before running its models; no network access."""
import argparse,hashlib,json
from pathlib import Path,PurePosixPath

def verify(root):
    root=root.resolve();manifest=json.loads((root/'handoff-manifest.json').read_text())
    errors=[]
    for row in manifest['files']:
        relative=PurePosixPath(row['path'])
        if relative.is_absolute() or '..' in relative.parts or '\\' in row['path']:raise ValueError('Unsafe manifest path')
        p=(root/Path(*relative.parts)).resolve()
        if not p.is_relative_to(root):raise ValueError('Manifest target escapes root')
        if not p.is_file():errors.append(dict(path=row['path'],reason='missing'));continue
        if p.stat().st_size!=row['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            errors.append(dict(path=row['path'],reason='changed'))
    return dict(passed=not errors,checked_files=len(manifest['files']),errors=errors,
                hardware_validated=False,note='Integrity relative to this local manifest only; not a trusted signature or runtime compatibility proof.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args();r=verify(a.root);print(json.dumps(r,indent=2))
    if not r['passed']:raise SystemExit(1)
