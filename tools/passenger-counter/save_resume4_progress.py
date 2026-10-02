"""Update project progress without replacing unrelated project history."""
from pathlib import Path


def current(path,text):
    old=path.read_text(encoding='utf-8')
    marker='\n## 2026-10-01'
    if not old.startswith('## 2026-10-02') or marker not in old:
        raise ValueError('Unexpected current progress section: '+str(path))
    path.write_text(text.rstrip()+'\n'+old[old.index(marker):],encoding='utf-8')


def prepend(path,text):
    old=path.read_text(encoding='utf-8')
    if text.splitlines()[0] in old:
        raise ValueError('Progress entry already saved')
    path.write_text(text.rstrip()+'\n\n'+old,encoding='utf-8')


def main():
    project=Path.cwd().parents[1]
    brief='''## 2026-10-02 승차 집계 재개 진행 중

최신 확인 5시간 사용61%·잔여39%; 잔여5% 이하 중단 기준 미도달로 계속 진행한다. Orin Nano는 미연결이며 실제 실행은 Windows CPU다. 기존 기본 설정은 보존한다.

기본513 전체 실행에서 RTSP/CSI 시간 처리 수정 전후 모든 검출·ID·관측점·이벤트가 같고 IN6/OUT0을 유지했다. 파일은 frame/fps, 라이브 문자열 입력은 프레임을 읽은 호스트 실제 경과 시간으로 구분했다. 카메라 노출 시각·버퍼 지연·실제 CSI/RTSP 연결은 미검증이다.

공식 OSNet 외형 연결 선택 기능을 추가하여 원본과 왼쪽 이동513 전체 실제 추론/추적/집계 검사를 완료했다. 각각 IN6/OUT0, 실제 인물6명 대응이나 고정 시각 창 대조는5/6이다. 왼쪽은 저장 로그 재생과 새 전체 실행의 모든 raw/canonical box·ID·관측점·이벤트가 정확히 일치했다. 오른쪽/반전 전체 비교 중. 기본 승격·Orin 성능·독립 정확도 검증은 아니다.

새 Danfo759 기본/기존 generic 문은 잠금0·고정 승객0/1이었다. 4프레임만 train으로 추가한 문 모델은 전체 문224프레임·IN1이지만 옆 창문 선택 후 흰 옷 행인을 센 것으로 원본에서 확인했다. 무늬 원피스 정답은0/1이므로 미채택한다. 새 영상은 이후 개발 자료로 재분류하며 같은 저자 촬영의 독립성도 주장하지 않는다. 원본 split/라벨 보존, 학습 입력·라벨 SHA 및 종료 후 무변경 검사, 개발 시 test 평가 생략을 추가했다.

전체 단위 테스트231개 통과. 세부 상태와 다음 작업은 tools/passenger-counter/CHECKPOINT.md, 실험 결과는 RESULTS.md, 실행 증거 색인은 runs/resume4-current-experiment-index.json에 있다.
'''
    current(project/'docs/CURRENT_STATUS.md',brief)
    current(Path('STATUS.md'),brief.replace('승차 집계 재개 진행 중','승차 계수 진행 상태',1))
    checkpoint=brief.replace('승차 집계 재개 진행 중','작업 중단점 갱신',1)+'''
다음 실행 확인:

- `green-right80-osnet-observed-resume4-full`, `green-reverse-osnet-observed-resume4-full`의 소유 프로세스 종료 및 완료 감사 확인 후 실제 이벤트 인물 검토.
- `green-left80-osnet-observed-resume4-full`: raw 검출부터 집계까지 새 전체 실행 완료; `osnet-frozen-to-live-parity-resume4.json` 모든 trace/event 동일성 통과.
- `danfo-called-adapted-door-resume4-full`: 전체759 실제exit0, 고정 승객 미회복 및 옆 창문 오검출 확인. 총계1을 승차 성공으로 취급하지 않는다.
- 자동 버스 영역의 사람 확대 진단도 frame30/50의 원피스 승객을 못 잡았다. `danfo-called-auto-bus-person-crops-resume4/probe.json`; 런타임 미도입.
- 느린 참조 모델의 사람 검출 표본 진단 진행 중. 이후 기본 설정의 선택 기능 비활성 보존 전체 검사와 음성 회귀, 장치 전달 자료 갱신.

기존 Orin r9 ZIP은 이전 snapshot이며 최신 소스 변경을 자동 포함하지 않는다. 외형 후보는 명시적 `appearance_bridge` 설정만 사용하며 검증된 CPU ONNX 모델/양성 parity 파일이 필요하다. 실제 발/문 좌표를 새로 만들지 않는다. 인물 대응 수와 고정 시각 대응 수를 구별하며 정답 창을 넓히지 않았다.
'''
    current(Path('CHECKPOINT.md'),checkpoint)
    entry='''## 2026-10-02 04:52 UTC 추가 실제 검증

Danfo 기본 및 generic 문 전체759은0/0·문0·사전 정답0/1. 기존26사진 평가 split을 바꾸지 않고 기존22+새4프레임 train만 사용한 모델은8epoch 실제exit0, validation mAP50 .249·recall .2, test 재평가 없음. source/모델/manifest/이미지/라벨/학습 입력 목록 SHA를 시작·종료 검사했다. 전체759 문224·IN1(frame97 ID22)은 실제 옆 창문을 출입구로 잘못 선택한 뒤 흰옷 행인을 집계했다. 원피스 정답0/1, 미채택. called 영상은 이 시점부터 개발 자료다. 새4라벨은 assistant 원본/overlay 검토이며 가려진 경계의 픽셀 정확도·사람 독립 검수 미완료. 26장/11촬영그룹, train19/7·val3/2·test4/2, 기존 split/이미지/라벨 모두 보존했다.

SourceClock 수정 후 기본전체513 실제exit0/전체감사·IN6/OUT0, 모든 검출/ID/점/이벤트 동일성 통과. 파일 timestamp는 유지, 문자열 live입력 시간 계산 오류를 수정했다. 호스트 read 완료 시각이며 노출 시각/버퍼 지연을 추정하지 않는다.

OSNet 실제런타임 선택 후보 whole 원본/왼쪽 각513 실제exit0/전체감사·6/0. 인물 대응 각6명, 기존 고정창 각5/6(청록 원본249·왼쪽245가255보다 조기). `osnet-frozen-to-live-parity-resume4.json`: 왼쪽 모든 raw/canonical/point/event 정확히 동일. 특징 추론은 CPUExecutionProvider, 해당 whole실행의 외형 단계22.29/24.58초이며 Orin FPS 또는 전체 파이프라인 FPS가 아니다. 오른쪽/반전 진행 중, 기본 미채택.

OSNet 새 r2 export901043bytes 실제16양성 표본/입력 무변경 검사 통과. 전체513/2976 ONNX feature 비교도 실제exit0·maxabs2.071e-6·mincos .999999523·21.54초·입력 무변경 검사 통과. 이는 수치 재현성이며 인원/기기 정확도와 구별한다.

전체231 단위 테스트 통과. 새 인물 대응 평가에서도 같은 사람 여러 ID는 하나로 묶고 반복 예측을 별도 표시하며, 기존 시각 실패는 그대로 남긴다. 전체 GT가 아닌 부분 검토이므로 precision/독립 정확도를 산출하지 않는다.
'''
    prepend(Path('RESULTS.md'),entry)
    prepend(project/'docs/WORKLOG.md',entry)
    prepend(Path('SOURCES.md'),'''## 2026-10-02 Danfo 개발 자료 전환

`called.webm`은 처음 두 고정 설정 비교 때 학습하지 않은 자료였다. 실패를 확인한 뒤 called 파생 영상의0/50/100/150 네 프레임을 train에 추가했다. 이후 이 촬영에 대한 학습/평가는 개발 실험이며 독립 블라인드 결과가 아니다. 같은 저자의 boarding 영상도 촬영 독립성이 확인되지 않아 독립 holdout을 주장하지 않는다. 원본 저작자·CC BY-SA4.0·90도 회전/음성 생략/JPEG 추출/assistant 주석 변경 내역은 `bus-portal-danfo-development-resume4-r2/provenance.json`에 보존했다. 새 주석은 동일 CC BY-SA4.0, 사람이 독립 검수한 완전 정답이 아니다.
''')
    path=Path('README.md');old=path.read_text(encoding='utf-8')
    section='''## 2026-10-02 선택 외형 실험과 입력 시간

`bus-portal-measured-osnet-observed-resume4.json`은 공식 OSNet x0.25 ONNX 특징으로 현재 검출 박스의 짧은 가림 연결을 실험한다. `appearance_bridge`를 명시하지 않으면 기본은 사용하지 않는다. 실제 전체 실행에서 원본/왼쪽 각각6명을 인물별로 확인했지만 조기 집계1건씩 남아 공통 기본으로 승격하지 않았다. 모델 크기는901043bytes이며 CPU 수치 일치 검증만 완료했다.

```powershell
.venv/Scripts/python.exe run_experiment.py --source data/regression/green-shift-left80-20261001.mp4 --config configs/bus-portal-measured-osnet-observed-resume4.json --output runs/NEW-APPEARANCE-EXPERIMENT --device cpu
```

`run.py --source-kind auto`는 실제 로컬 파일을 frame/fps로 계산하고 숫자 카메라·RTSP URL·capture pipeline은 호스트 read 완료 경과 시간을 쓴다. `file`/`live`로 명시할 수도 있다. 결과 `source_timing`은 선택한 시간 기준을 기록한다. 저장되는 annotated.mp4는 고정 FPS이므로 라이브 시간 증거는 tracks/events의 time_s를 사용한다. 카메라 노출 시각·버퍼 지연·실제 RTSP/CSI 동작은 미검증이다.

개발용 `train_door.py --skip-test`는 validation으로 checkpoint를 선택하고 test를 평가하지 않는다. 학습 전후 manifest/이미지/라벨/초기 모델/학습 파일 무변경을 검사하며 `training-inputs.json`·`training-completion.json`을 남긴다. `--prepare-only`는 학습/검증 완료를 뜻하지 않는다.

'''
    path.write_text(old.replace('## 2026-10-01 재중단 복구와 현재 후보',section+'## 2026-10-01 재중단 복구와 현재 후보',1),encoding='utf-8')
    print('saved current status, checkpoint, results, worklog, sources, README')


if __name__=='__main__':main()
