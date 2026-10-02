from pathlib import Path
import hashlib,json,zipfile,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
NATIVE=Path(r'C:\Users\20222967\AndroidStudioProjects\IndoorPositioningPrototype')
HERE=Path(__file__).resolve().parent
APK=ROOT/'exports/android/indoor-20261002-event-ap.apk'
digest=lambda b:hashlib.sha256(b).hexdigest()
report={'apk':str(APK),'apk_sha256':digest(APK.read_bytes()),'device_installation':'not_performed_no_device',
        'field_accuracy':'not_validated','source':[],'assets':[],'tests':[]}
for staged in (HERE/'source').glob('*.kt'):
    scope='test' if staged.name.endswith('Test.kt') else 'main'
    actual=NATIVE/f'app/src/{scope}/java/com/example/indoorpositioning'/staged.name
    assert actual.read_bytes()==staged.read_bytes(),f'source differs: {staged.name}'
    report['source'].append({'name':staged.name,'sha256':digest(staged.read_bytes())})
assert (HERE/'build.gradle.kts').read_bytes()==(NATIVE/'app/build.gradle.kts').read_bytes()
with zipfile.ZipFile(APK) as z:
    assert z.testzip() is None
    for path in list((ROOT/'indoor/web/src/positioning').glob('*.js'))+list((ROOT/'indoor/web/data/positioning').glob('*.json'))+list((ROOT/'indoor/web/data/maps').glob('*.json'))+[ROOT/'indoor/web/data/navigation/areas-v1.json',ROOT/'indoor/web/fusion-experiment.html',ROOT/'indoor/web/fusion-route-runtime.html']:
        rel=path.relative_to(ROOT/'indoor/web').as_posix()
        assert z.read('assets/'+rel)==path.read_bytes(),f'APK asset differs: {rel}'
        report['assets'].append({'name':rel,'sha256':digest(path.read_bytes())})
for file in (NATIVE/'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    suite=ET.parse(file).getroot()
    row={k:suite.attrib[k] for k in ['name','tests','failures','errors']}
    assert int(row['failures'])==int(row['errors'])==0
    report['tests'].append(row)
issues=ET.parse(NATIVE/'app/build/reports/lint-results-debug.xml').getroot()
report['lint_errors']=[x.attrib['id'] for x in issues if x.attrib.get('severity') in ['Error','Fatal']]
report['lint_warnings']=[x.attrib['id'] for x in issues if x.attrib.get('severity')=='Warning']
assert not report['lint_errors']
report['browser']=json.loads((HERE/'browser-verification.json').read_text())
report['backup']=[{'name':p.name,'sha256':digest(p.read_bytes())} for p in (HERE/'before').glob('*')]
(HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'source_files':len(report['source']),'apk_assets_verified':len(report['assets']),
    'tests':sum(int(r['tests']) for r in report['tests']),'lint_errors':report['lint_errors'],
    'lint_warning_count':len(report['lint_warnings']),'sha256':report['apk_sha256']},ensure_ascii=False))
