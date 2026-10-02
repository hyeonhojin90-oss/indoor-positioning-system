"""Build a clean ASCII-path copy of repository Android sources on Windows.

Uses the configured local SDK/JDK and writes results under exports (not tracked).
The active Android Studio project is never modified.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports/github-20261003'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='indoor-github-'))
    project = temporary / 'app/android-native'
    shutil.copytree(ROOT / 'app/android-native', project,
                    ignore=shutil.ignore_patterns('.gradle', '.kotlin', 'build', 'local.properties'))
    shutil.copytree(ROOT / 'indoor/web', temporary / 'indoor/web')
    env = os.environ.copy()
    env.setdefault('JAVA_HOME', r'C:\Program Files\Android\Android Studio\jbr')
    env.setdefault('ANDROID_HOME', str(Path.home() / 'AppData/Local/Android/Sdk'))
    env['PATH'] = str(Path(env['JAVA_HOME']) / 'bin') + os.pathsep + env['PATH']
    command = [str(project / 'gradlew.bat'), '--offline', '--console=plain',
               'testDebugUnitTest', 'lintDebug', 'assembleDebug']
    print(f'Building repository copy at {temporary}', flush=True)
    with (OUT / 'android-build.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=project, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=900)
    print((OUT / 'android-build.log').read_text(encoding='utf-8')[-2200:], flush=True)
    if result.returncode:
        raise RuntimeError(f'Gradle failed: {result.returncode}')
    suites = [ET.parse(f).getroot() for f in (project / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
    tests = sum(int(s.attrib['tests']) for s in suites)
    failures = sum(int(s.attrib.get('failures', 0)) + int(s.attrib.get('errors', 0)) for s in suites)
    assert tests >= 37 and failures == 0, (tests, failures)
    lint = ET.parse(project / 'app/build/reports/lint-results-debug.xml').getroot()
    lint_errors = sum(i.attrib.get('severity') in {'Error', 'Fatal'} for i in lint.findall('issue'))
    assert lint_errors == 0, lint_errors
    apk = project / 'app/build/outputs/apk/debug/app-debug.apk'
    recorded = json.loads((ROOT / 'app/android-updates/20261002/verification.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(apk) as z:
        assert z.testzip() is None
        for item in recorded['assets']:
            actual = hashlib.sha256(z.read('assets/' + item['name'])).hexdigest()
            current = hashlib.sha256((ROOT / 'indoor/web' / item['name']).read_bytes()).hexdigest()
            assert actual == current, item['name']
    report = {'gradle_exit': 0, 'unit_tests': tests, 'failures': failures,
              'lint_errors': lint_errors,
              'lint_warnings': sum(i.attrib.get('severity') == 'Warning' for i in lint.findall('issue')),
              'matched_shared_assets': len(recorded['assets']), 'apk_crc': 'passed',
              'apk_sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
              'device_installation': 'not_performed', 'field_accuracy': 'not_validated'}
    (OUT / 'android-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    shutil.copy2(apk, OUT / 'app-debug.apk')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
