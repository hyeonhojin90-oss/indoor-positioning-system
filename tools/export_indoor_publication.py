"""Prepare an indoor-only GitHub checkout while preserving the full workspace.

Does not push, rewrite remote history, or delete workspace files. Output must be
a new directory under this workspace's ignored exports directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REMOTE = 'https://github.com/hyeonhojin90-oss/indoor-positioning-system.git'
DOCS = {
    'INDOOR_AGREEMENT_AUDIT_20261002.md', 'INDOOR_POSITIONING_PRODUCT_PLAN.md',
    'MEASUREMENT_20260914.md', 'POSITIONING_CHECKLIST.md',
    'RADIO_SURVEY_ANALYSIS.md', 'IMPLEMENTATION_20260909.md',
    'EVIDENCE_REVIEW_20260909.md', 'GITHUB_ANDROID_VERIFICATION_20261003.json',
}
TOOLS = {
    'export_indoor_publication.py', 'export_android_source_copy.py',
    'sync_android_source.py', 'verify_android_repository.py',
    'test_indoor_snapshot.cjs', 'update_android_2f_corrected_laps_20260922.py',
    'update_android_4f_restroom_lap_20260922.py', 'update_android_room_labels_20260922.py',
}
GENERATED = {
    'README.md', 'AGENTS.md', 'app/README.md', 'docs/CURRENT_STATUS.md',
    'docs/DECISIONS.md', 'docs/WORKLOG.md', 'docs/GITHUB_SNAPSHOT_20261003.md',
    'docs/PUBLICATION_SCOPE.json', 'indoor/tools/requirements-analysis.txt',
}

def allowed(path):
    return (path.startswith(('indoor/', 'app/'))
            or path in {'.gitattributes','.gitignore','package.json','package-lock.json'}
            or path in GENERATED
            or path in {'docs/'+name for name in DOCS}
            or path in {'tools/'+name for name in TOOLS})

README = '''# 실내지도 제작 및 실내측위

조선대학교 IT융합대학의 실내 2D·3D 지도와 휴대폰 센서를 이용한 실내 위치 추정 연구·개발 자료다. 진현호가 담당한 지도 제작, 실내 측위 및 현장 수집·분석 내용을 증빙하기 위한 저장소다.

## 포함한 작업

- 피난안내도·현장 사진·GLB/LiDAR·실측을 활용한 1~10층 2D·3D 지도
- 실제 복도 거리표와 도면 표시 좌표의 변환, 층별 이동 가능 범위
- PDR·파티클·지도 제약, 자기장 격자/8걸음 패턴, BLE·AP 보정 코드
- Android 지도·강의실 안내·경로 라벨·센서 기준점 수집 앱과 이전 Expo 실험 앱
- 보행·기준점 측정 원본/정정본, 보폭·RoNIN·센서 조합 비교와 실패 사례

## 코드와 자료 찾기

| 경로 | 내용 |
|---|---|
| `indoor/web` | 2D·3D 지도, 공용 지도 자료와 측위 엔진 |
| `app/android-native` | Android Studio 앱 소스와 단위검사 |
| `app/expo-sensor-collector` | 이전 센서 수집·재생 실험 앱 |
| `app/android-updates` | Android 수정 및 검증 기록 |
| `indoor/data/raw`, `curated` | 측정 원본과 정정 자료 |
| `indoor/data/analysis` | 실험 조건·결과·오차·실패 사례 |
| `indoor/tools`, `tools` | 분석·재생·지도 검사·앱 동기화 도구 |
| `docs`, `indoor/docs` | 실내측위 진행상황·설계 결정·지도 근거 |

## 실행

Git LFS를 설치한 뒤 저장소를 복제한다.

```powershell
git clone https://github.com/hyeonhojin90-oss/indoor-positioning-system.git
cd indoor-positioning-system
git lfs pull
python -m http.server 4175 --bind 127.0.0.1 --directory indoor/web
```

2D 지도는 `http://127.0.0.1:4175/index.html`, 3D 지도는 `http://127.0.0.1:4175/clay.html`에서 확인한다. 3D 표시에는 인터넷으로 불러오는 Three.js가 필요하다.

Android Studio에서 `app/android-native`를 연다. SDK/JDK 및 빌드 방법은 [앱 안내](app/android-native/README.md)를 따른다. Node.js를 준비하면 `npm test`로 실내 검사 스크립트 14개를 실행한다. 브라우저 검사는 `npm ci`, 위 지도 서버와 Windows Edge를 준비한 뒤 `npm run test:browser`로 실행한다. Python 분석은 필요한 경우 `python -m pip install -r indoor/tools/requirements-analysis.txt`로 분석 패키지를 준비한다. RoNIN 학습 모델은 [출처·설치 안내](indoor/tools/ronin/README.md)에 따라 별도로 받는다.

## 현재 결과와 한계

지도·수집 앱·센서 융합 실험 코드를 구현했다. 자기장 보정으로 일부 기록의 평균 오차가 소폭 줄었지만 큰 누적 오차가 남아 있다. 같은 기록을 다시 계산한 개발 평가와 독립 현장 정확도를 구분한다. 전 층 자동 초기 위치·층 이동 종료 판정·설치 비콘 연동 등은 완료한 것으로 주장하지 않는다.

[현재 상태](docs/CURRENT_STATUS.md), [분석 자료](indoor/data/analysis), [미완료 항목](docs/INDOOR_AGREEMENT_AUDIT_20261002.md), [공개 범위](docs/GITHUB_SNAPSHOT_20261003.md)를 함께 확인한다. APK·개인 보고서·SDK 경로·개인키·빌드 캐시는 포함하지 않는다.
'''

STATUS = '''# 실내지도·실내측위 공개 자료 상태 — 2026-10-03

이 저장소의 범위는 실내지도 제작과 실내측위다. 상세 지도 변경 및 센서 실험은 [실내 상태](../indoor/docs/STATUS.md)와 `indoor/data/analysis`에서 확인한다.

## 구현

1~10층 2D·3D 지도, 실측 거리표, 층별 추적 범위와 Android 수집·안내 앱을 포함한다. 현재 Android 버전은 1.0.20261002.1 / versionCode 8이다. PDR·파티클의 같은 후보에 자기장·BLE·AP를 제한적으로 반영한다. 고정보폭 기본은 약0.62m/검출 걸음이며 모든 사람의 실제 보폭 측정값은 아니다. m 저장 좌표는 선택 비교 버전이고 기본 승격하지 않았다.

## 평가

실내 검사 스크립트14개 및 Android 단위검사37개·Lint 오류0의 빌드 검증 기록이 있다. 센서 조합·보폭·RoNIN 비교, 자기장 지도 및 구간 패턴 평가를 보존했다. 최신 코드의 공개와 빌드 성공은 새 기기 설치·현장 보행 정확도 검증을 의미하지 않는다.

## 미완료

큰 누적 오차의 자동 복구, 자동 초기 위치, 계단 층 확정 후 재개, 설치 비콘 등록, 일부 2·3층 추가 영역 상태 연결, AP·BLE 공동 확인 등은 [합의 대조](INDOOR_AGREEMENT_AUDIT_20261002.md)를 따른다.
'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve()
    if not out.is_relative_to((ROOT/'exports').resolve()) or out.exists():
        raise ValueError('Output must be a NEW directory under workspace exports.')
    env=os.environ.copy()
    git_home=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/mingw64'
    env['PATH']=str(git_home/'libexec/git-core')+os.pathsep+str(git_home/'bin')+os.pathsep+env['PATH']
    env['GIT_EXEC_PATH']=str(git_home/'bin')
    env['GIT_LFS_SKIP_SMUDGE']='1'
    env['GIT_TERMINAL_PROMPT']='0'
    env['GCM_INTERACTIVE']='Never'

    def git(*args,cwd=ROOT,data=None):
        return subprocess.check_output(['git',*args],cwd=cwd,env=env,input=data,stderr=subprocess.PIPE)

    source_head=git('rev-parse','HEAD').decode().strip()
    out.parent.mkdir(parents=True,exist_ok=True)
    git('clone','--no-checkout','--no-hardlinks',str(ROOT),str(out))
    git('remote','set-url','origin',REMOTE,cwd=out)
    git('fetch','origin','main',cwd=out)
    parent=git('rev-parse','origin/main',cwd=out).decode().strip()
    git('symbolic-ref','HEAD','refs/heads/main',cwd=out)
    git('update-ref','refs/heads/main',parent,cwd=out)
    git('read-tree','HEAD',cwd=out)
    git('lfs','install','--local',cwd=out)
    for setting in ('user.name','user.email'):
        value=git('config',setting).decode().strip()
        git('config',setting,value,cwd=out)
    tracked=set(filter(None,git('ls-files','-z').decode().split('\0')))
    selected={p for p in tracked if allowed(p)}
    selected.add('tools/export_indoor_publication.py')
    base=set(filter(None,git('ls-files','-z',cwd=out).decode().split('\0')))
    excluded=sorted(base-(selected|GENERATED))
    if excluded:
        git('update-index','--force-remove','-z','--stdin',cwd=out,data=('\0'.join(excluded)+'\0').encode())
    for rel in sorted(selected):
        dest=out/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/rel,dest)

    def write(rel,text):
        dest=out/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(text.rstrip()+'\n',encoding='utf-8')

    write('README.md',README)
    write('AGENTS.md','# 실내지도·실내측위 저장소 지침\n\n이 저장소는 실내지도·측위·수집·분석 자료를 다룬다. 작업 전 README, docs/CURRENT_STATUS.md, 해당 영역 AGENTS.md와 상태 문서를 읽는다. 공용 지도 자료를 중복 작성하지 않고 확인된 2D를 3D의 기준으로 유지한다. 실측과 도면 표시 좌표를 구분하며 PDR·신호·지도 후보를 근거 없이 확정하지 않는다. 원시 기록과 기존 사용자 변경을 보존하고 단위검사·빌드·현장 정확도를 구분해 기록한다. 변경 후 영향 범위의 검사를 수행하고 실내 상태와 작업 기록을 갱신한다. 사용자 승인 없이 원격 푸시나 과거 기록 재작성을 하지 않는다. 상세 지도·앱 규칙은 indoor/AGENTS.md와 app/AGENTS.md를 따른다.')
    write('app/README.md','# 실내측위·센서 수집 앱\n\n현재 Android Studio 소스는 [android-native](android-native/README.md)에 있다. 공용 indoor/web 지도와 PDR·파티클 엔진을 재사용하며 경로 라벨·센서 기준점 수집, 지도 표시와 실내 안내 실험을 포함한다. Expo 앱은 이전 수집·재생 비교 자료다. android-updates는 수정·검증 기록이다. 버전별 구현과 현장 검증 상태는 [현재 상태](../docs/CURRENT_STATUS.md)와 [합의 대조](../docs/INDOOR_AGREEMENT_AUDIT_20261002.md)를 따른다.')
    write('docs/CURRENT_STATUS.md',STATUS)
    app_rules=(ROOT/'app/AGENTS.md').read_text(encoding='utf-8')
    app_rules='\n'.join(line for line in app_rules.splitlines() if 'T-Beam' not in line and '실외·실내 전환' not in line)
    write('app/AGENTS.md',app_rules)
    ignore=(ROOT/'.gitignore').read_text(encoding='utf-8').split('# GPS disposable')[0]
    write('.gitignore',ignore+'\n# Indoor-only public repository scope\n/gps/\n/tools/passenger-counter/\n/tools/school-ai-mcp/\n')
    decisions=(ROOT/'docs/DECISIONS.md').read_text(encoding='utf-8')
    parts=re.split(r'(?=^## DEC-)',decisions,flags=re.MULTILINE)
    filtered=[p for p in parts if re.match(r'## DEC-(\d+)',p) and int(re.match(r'## DEC-(\d+)',p).group(1)) not in {1,6,9,24,34}]
    write('docs/DECISIONS.md','# 실내지도·측위 설계 결정\n\n전체 개발 기록 중 실내지도·측위 관련 결정만 발췌했다.\n\n'+'\n'.join(filtered))
    write('docs/WORKLOG.md','# 실내지도·측위 공개 정리 — 2026-10-03\n\n기존 공개 저장소의 최신 파일 구성을 실내지도·측위 자료로 한정했다. 전체 개발 원본을 로컬에 보존하고 별도 체크아웃에서 공개할 파일을 선별했다. 지도·측위 알고리즘과 Android 소스를 보존하고 설명 및 독립 실행 안내를 정리했다. 과거 Git 기록을 재작성하지 않는다. 실제 검사 결과는 GITHUB_ANDROID_VERIFICATION_20261003.json과 PUBLICATION_SCOPE.json에서 확인한다.')
    write('indoor/tools/requirements-analysis.txt','# Optional offline analysis packages; Android and Node tests do not require them.\nnumpy\nscipy\nmatplotlib\ntorch')
    adaptations=[]
    for rel in sorted(selected):
        if rel=='tools/export_indoor_publication.py' or (out/rel).suffix not in {'.md','.py'}:
            continue
        text=(out/rel).read_text(encoding='utf-8')
        changed=text.replace("& 'tools/passenger-counter/.venv/Scripts/python.exe'",'python').replace('tools/passenger-counter/.venv/Scripts/python.exe','python')
        changed=changed.replace('이 Python 환경이나 승차 집계 코드/데이터는 수정하지 않았다.','분석에는 위 Python 패키지 환경이 필요하며 원시 측정 자료는 수정하지 않는다.')
        if changed!=text:
            write(rel,changed)
            adaptations.append(rel)
    report={'source_commit':source_head,'remote_parent_commit':parent,'scope':'indoor maps, positioning, Android/Expo collection, measurements and analyses','selected_source_files':len(selected),'removed_from_current_public_tree':len(excluded),'excluded_domains':['gps','tools/passenger-counter','tools/school-ai-mcp','report generation tools','whole-project documents'],'instruction_path_adaptations':adaptations,'workspace_source_files_deleted':0,'remote_history_rewritten':False,'verification':'pending'}
    write('docs/PUBLICATION_SCOPE.json',json.dumps(report,ensure_ascii=False,indent=2))
    write('docs/GITHUB_SNAPSHOT_20261003.md','# 실내지도·측위 공개 범위\n\n공개 저장소: https://github.com/hyeonhojin90-oss/indoor-positioning-system\n\n현재 파일 구성은 1~10층 2D·3D 지도, 실내 측위 엔진, Android/Expo 수집 앱, 실측·보행·기준점 원본과 분석 결과다. GPS·승차 집계·학교 AI 도구·개인/팀 보고서 제작 도구·전체 프로젝트 문서는 현재 파일 구성에서 제외했다. 전체 개발 원본은 로컬 작업 폴더에 보존했다. 과거 커밋 기록은 그대로 남는다.\n\n공용 웹/Android 알고리즘은 범위 정리를 위해 변경하지 않았다. 일부 분석 실행 안내가 제외한 도구의 Python 환경을 참조하고 있어 독립 Python 실행 안내로 바꿨다. 복제 시 Git LFS가 필요하다. 정확한 선별 범위와 검사 결과는 PUBLICATION_SCOPE.json을 따른다.\n\n후속 전체 작업 폴더에서 공개본을 갱신할 때는 tools/export_indoor_publication.py --output exports/새폴더로 준비한 뒤 검토·검사·커밋·푸시한다. 전체 개발 저장소의 파일을 그대로 공개 저장소에 푸시하지 않는다.')
    git('add','--all',cwd=out)
    paths=set(filter(None,git('ls-files','-z',cwd=out).decode().split('\0')))
    assert all(allowed(p) for p in paths), sorted(p for p in paths if not allowed(p))
    assert not any(p.startswith(('gps/','tools/passenger-counter/','tools/school-ai-mcp/')) for p in paths)
    git('diff','--cached','--check',cwd=out)
    print(json.dumps({'output':str(out),'source_commit':source_head,'parent_commit':parent,'public_files':len(paths),'removed_files':len(excluded),'adaptations':adaptations},ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
