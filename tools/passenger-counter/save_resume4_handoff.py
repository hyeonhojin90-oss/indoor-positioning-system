"""Refresh owned progress using captured process receipts and fresh usage input."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path


def current(path,text):
    old=path.read_text(encoding='utf-8');marker='\n## 2026-10-01'
    if not old.startswith('## 2026-10-02') or marker not in old:raise ValueError('Unexpected progress structure')
    path.write_text(text.rstrip()+'\n'+old[old.index(marker):],encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--used-percent',type=float,required=True)
    parser.add_argument('--tests',type=int,required=True);args=parser.parse_args()
    if not 0<=args.used_percent<=100:raise ValueError('Invalid fresh usage')
    now=datetime.now(timezone.utc).isoformat();remaining=100-args.used_percent;stop=args.used_percent>=95
    process_path=Path('runs/danfo-called-rtdetr-development-resume4-full.process.json')
    process=json.loads(process_path.read_text(encoding='utf-8'))
    phase=process['phase'];frame=process.get('last_reported_frame')
    process_note=f"RT-DETR 새 Danfo 전체 비교는 `{phase}`, 마지막 보고 frame{frame}, 실제 exit={process.get('process_returncode')}, full_run_verified={process.get('full_run_verified')}다. summary 없는 진행 상태를 전체 완료나 정답 회복으로 처리하지 않는다."
    integrity=json.loads(Path('runs/orin-handoff-resume4-r10-integrity.json').read_text())
    brief=f'''## 2026-10-02 승차 집계 {'사용량 중단점' if stop else '재개 진행 중'}

최신 계정5시간 확인 사용{args.used_percent:g}%·잔여{remaining:g}%, 확인UTC {now}. 사용자 중단 기준 잔여5% 이하 도달={stop}. Orin Nano 미연결, 실제 추론/학습은 Windows CPU이며 프로젝트 목표 전체 완료가 아니다.

기본513 전체 새 실행은 IN6/OUT0과 모든 사람 박스·ID·관측점·이벤트를 보존했다. `green-default-appearance-isolation-preservation-resume4.json` 통과. 선택 외형 기능은 기본 비활성이다. OSNet 전체 원본/왼쪽6/0·고정5/6, 오른쪽5/0·4/6, 반전1/4·3/6으로 기본 승격하지 않았다. 정지60 및 버스 없는341 전체 음성 회귀는0/0이다. 합성 이동/반전은 독립 촬영 정확도가 아니다.

Danfo 문 개발 학습8epoch 완료, 기존22사진 split/라벨 보존+4train프레임, test 평가 생략. 전체759의 IN1은 옆 패널을 문으로 잡고 행인을 센 것으로 원본에서 확인하여 정답0/1·미채택했다. RT-DETR와 일반 `a person.` 참조 모델은 실제30/50 표본의 원피스 승객을 검출했다. {process_note}

라이브/부분 로그 감사, 로컬 정답 검토 화면과 영상·정답 SHA 결합 평가를 추가했다. UI 실제30~80 이동·저장·브라우저 오류 없음, 디코더 위치 확인/순차 읽기 복구·반환 JPEG SHA 기록까지 검사했다. 카메라 수집 도구는 기존 파일로8프레임·읽기 시각 로그·전체 decode/해시 검사를 수행했다. 실제 카메라·RTSP 연결/노출 시각/버퍼 지연 검증은 아니다. 강의실 전용 설정은 버스 등장 조건을 제거했다. 공개 건물 사진 정지15프레임2개 전체 검사에서 문 잠금10/15 및0/0, 음성0/0이며 실제 강의실 영상 성공이 아니다.

스트림 문자열을 종료 때 로컬 파일로 해시하는 오류를 별도 고정 코드에서 재현했다(원본8프레임 뒤 OSError·exit1·summary 없음). 수정 후보는 실제8프레임 추론 exit0·summary/관측 감사·로컬 입력 시작/종료 SHA 무변경·동일 사람 박스/ID/점을 확인했다. `stream-input-fix-proof-resume4.json`; 실제 네트워크/카메라 접근 없음. 진행 중 전체 비교의 코드 SHA를 보존하려고 루트 run.py 적용은 아직 남겨두었다.

전체 단위 테스트{args.tests}개 통과. Orin 고정 r10 ZIP {integrity['bytes']}bytes, SHA `{integrity['sha256']}`, CRC/manifest 검증 통과. 이 묶음은 생성 시점 코드/7모델/27baseline이며 이후 카메라 수집·새 프레임 검토·강의실 설정·스트림 수정 후보를 자동 포함하지 않는다. 배포 전 새 snapshot이 필요하다. 실제 JetPack/GPU/TensorRT/온도/전력/FPS/독립 현장 정확도 미검증.
'''
    project=Path.cwd().parents[1]
    current(project/'docs/CURRENT_STATUS.md',brief)
    current(Path('STATUS.md'),brief.replace('승차 집계','승차 계수',1))
    next_steps='''
다음 재개 순서:

1. `runs/resume4-current-experiment-index.json` 및 `danfo-called-rtdetr-development-resume4-full.process.json` 확인. 전체 actual exit0·summary759·source/replay/시작 코드 SHA 감사를 확인한 뒤 원본의 이벤트와 문 위치를 검토한다.
2. 해당 프로세스 종료 후 `runs/stream-input-fix-candidate-resume4-runtime/run.py`의 네 군데 수정과 `runtime_input_evidence.py`를 루트 runtime에 적용한다. `prepare_stream_input_fix_candidate.py`가 정확한 변경 지점을 명시한다. 새 기본 전체513 박스/ID/점/이벤트 보존 및 file/live 부분 감사 회귀가 필요하다. 기존 감사 파일은 덮어쓰지 않는다.
3. 최신 검토/수집/강의실 도구 및 수정 runtime으로 별도 Orin snapshot 생성·SHA/CRC 검사. r10/r9를 최신 코드인 것처럼 사용하지 않는다.
4. Orin 수령 후 환경 읽기→동일 녹화 파일 GPU 전체 비교→장치 TensorRT 양성 박스/자세/전체 이벤트 대조→실제 고정 카메라 시험. 클래스룸 설정은 설치별 방향/통과 위치를 확인한다. 기존 버스 기본 설정을 강의실 시험용으로 덮어쓰지 않는다.
5. 사람이 모델 예측 전에 확인한 새 촬영별 정답/문 경계/행인·멈춤·되돌아감 자료 확보. 승차 우선 유지, 정류장 대기 규모와 승차 가능성은 후속 목표다.

검토 UI 시험 서버와 작업용 브라우저 탭은 종료했다. 실행을 다시 시작할 때는 새로운 output 폴더를 사용한다. 실패한 잘못된 음성 영상 경로의 process receipt와 의도적인 원본 스트림 실패 증거도 보존했다.
'''
    current(Path('CHECKPOINT.md'),brief.replace('승차 집계','작업 중단점',1)+next_steps)
    entry=f'## 2026-10-02 {now} 실제 검증 및 재개 기록\n\n'+brief[brief.index('\n\n')+2:]+next_steps
    for path in [Path('RESULTS.md'),project/'docs/WORKLOG.md']:
        old=path.read_text(encoding='utf-8').replace('기존26사진 평가 split을 바꾸지 않고 기존22+새4프레임','기존22사진 평가 split을 바꾸지 않고 기존22+새4프레임')
        path.write_text(entry+'\n\n'+old,encoding='utf-8')
    usage=dict(checked_at=now,used_percent=args.used_percent,remaining_percent=remaining,stop_threshold_met=stop,
               origin='Fresh account 5-hour tool result provided to this recorder; not inferred from token count')
    Path('runs/resume4-current-usage.json').write_text(json.dumps(usage,indent=2),encoding='utf-8')
    print(json.dumps(dict(status_saved=True,threshold_met=stop,remaining=remaining,active_comparison_phase=phase)))


if __name__=='__main__':main()
