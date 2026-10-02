"""Create and verify a local source/data checkpoint; never overwrite a backup.

Run with Python 3. Uses only the standard library. No source files are modified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', '.gradle', '.kotlin', '.idea', '.expo', '.codex',
             '.pnpm-store', 'node_modules', '__pycache__', 'build', 'dist'}
SKIP_SUFFIXES = {'.pyc', '.log', '.tmp', '.jks', '.keystore', '.pem', '.key'}


def digest(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def verify(archive):
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('CHECKPOINT_MANIFEST.json'))
        names = z.namelist()
        expected = {r['path'] for r in manifest['files']} | {'CHECKPOINT_MANIFEST.json'}
        if len(names) != len(set(names)) or set(names) != expected:
            raise RuntimeError('Archive inventory mismatch')
        for row in manifest['files']:
            with z.open(row['path']) as f:
                if digest(f) != row['sha256']:
                    raise RuntimeError('Hash mismatch: ' + row['path'])
            if z.getinfo(row['path']).file_size != row['bytes']:
                raise RuntimeError('Size mismatch: ' + row['path'])
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--android', type=Path)
    parser.add_argument('--inbox', type=Path)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    if args.verify:
        m = verify(args.verify)
        print(json.dumps({'verified': True, 'files': len(m['files'])}))
        return
    if not args.android or not args.android.is_dir():
        parser.error('--android must name the existing Android project')
    now = datetime.now().astimezone()
    output = ROOT / 'backups' / now.strftime('%Y%m%d-%H%M%S-%f')
    output.mkdir(parents=True, exist_ok=False)
    archive = output / 'indoor-checkpoint.zip'
    records, excluded = [], []
    sources = [('repository', ROOT), ('android', args.android.resolve())]
    manifest = {'created_at': now.isoformat(), 'scope': 'working files, not full git history',
                'roots': {k: str(v) for k, v in sources}, 'files': records,
                'excluded': excluded, 'verification': 'see adjacent VERIFICATION.json'}
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        def add(path, name):
            before = path.stat()
            with path.open('rb') as f:
                sha = digest(f)
            z.write(path, name)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError('Source changed during backup: ' + str(path))
            records.append({'path': name, 'source': str(path), 'bytes': before.st_size,
                            'mtime_ns': before.st_mtime_ns, 'sha256': sha})

        def generated(name, data):
            raw = data.encode('utf-8')
            z.writestr(name, raw)
            records.append({'path': name, 'source': 'generated git metadata',
                            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

        for prefix, root in sources:
            for directory, dirs, files in os.walk(root, followlinks=False):
                base = Path(directory)
                for d in list(dirs):
                    p = base / d
                    if (d in SKIP_DIRS or (base == ROOT and d in {'backups', 'exports', 'tmp'})
                            or p.is_symlink() or getattr(p, 'is_junction', lambda: False)()):
                        excluded.append(str(p))
                        dirs.remove(d)
                for name in sorted(files):
                    p = base / name
                    if (name.startswith('.env') or name == 'local.properties'
                            or p.suffix.lower() in SKIP_SUFFIXES or p.is_symlink()):
                        excluded.append(str(p))
                        continue
                    add(p, prefix + '/' + p.relative_to(root).as_posix())
        apk = args.android / 'app/build/outputs/apk/debug/app-debug.apk'
        if apk.is_file():
            add(apk, 'artifacts/app-debug.apk')
        if args.inbox:
            if not args.inbox.is_dir():
                raise RuntimeError('Inbox directory missing')
            for p in sorted(args.inbox.iterdir()):
                if (p.is_file() and p.name.startswith(('barometer_', 'indoor_positioning'))
                        and p.suffix.lower() in {'.csv', '.jsonl'}):
                    add(p, 'external_sensor_files/' + p.name)
        if args.evidence:
            add(args.evidence, 'evidence/floor02-user-annotated.png')
        for label, command in [('head', ['rev-parse', 'HEAD']),
                               ('status', ['status', '--porcelain=v1', '-uall']),
                               ('unstaged', ['diff', '--binary']),
                               ('staged', ['diff', '--cached', '--binary'])]:
            result = subprocess.run(['git', '-C', str(ROOT), *command],
                                    capture_output=True, check=True)
            generated('git/' + label + '.txt', result.stdout.decode('utf-8', errors='replace'))
        z.writestr('CHECKPOINT_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    checked = verify(archive)
    with archive.open('rb') as f:
        archive_hash = digest(f)
    report = {'verified': True, 'verified_at': datetime.now().astimezone().isoformat(),
              'archive': archive.name, 'archive_sha256': archive_hash,
              'archive_bytes': archive.stat().st_size, 'file_count': len(checked['files']),
              'source_bytes': sum(r['bytes'] for r in records)}
    (output / 'CHECKPOINT_MANIFEST.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'VERIFICATION.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'directory': str(output), **report}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
