"""Copy the active Android project into the repository without machine state.

The repository copy reuses indoor/web as assets; the active project is untouched.
Run with --source if the active Android Studio project lives elsewhere.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=Path.home() / 'AndroidStudioProjects/IndoorPositioningPrototype')
    args = parser.parse_args()
    source = args.source.resolve()
    destination = ROOT / 'app/android-native'
    excluded = {'.gradle', '.idea', '.kotlin', 'build', 'local.properties', '.git'}
    files = []
    for original in sorted(source.rglob('*')):
        relative = original.relative_to(source)
        if not original.is_file() or any(part in excluded for part in relative.parts):
            continue
        if original.suffix.lower() in {'.jks', '.keystore'}:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
        adaptation = None
        if relative.as_posix() == 'gradle/libs.versions.toml':
            text = target.read_text(encoding='utf-8')
            target.write_text(text.rstrip() + '\n', encoding='utf-8')
            adaptation = 'Trailing empty lines removed only'
        if relative.as_posix() == 'app/build.gradle.kts':
            text = target.read_text(encoding='utf-8')
            old = 'assets.srcDir(file("../../../Documents/ChatGPT/자율설계 2/indoor/web"))'
            new = 'assets.srcDir(rootProject.file("../../indoor/web"))'
            if text.count(old) != 1:
                raise RuntimeError('Expected exactly one active-project asset path')
            target.write_text(text.replace(old, new).rstrip() + '\n', encoding='utf-8')
            adaptation = 'Repository-relative shared web assets path; trailing empty lines removed only'
        files.append({'path': relative.as_posix(), 'source_sha256': original_hash,
                      'repository_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                      'adaptation': adaptation})
    manifest = {'source': 'AndroidStudioProjects/IndoorPositioningPrototype',
                'shared_assets': '../../indoor/web',
                'excluded': sorted(excluded | {'*.jks', '*.keystore'}), 'files': files}
    (destination / 'SOURCE_MANIFEST.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Copied {len(files)} source files; active project unchanged')


if __name__ == '__main__':
    main()
