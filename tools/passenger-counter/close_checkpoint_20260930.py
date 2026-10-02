"""Final checkpoint requested by the user; does not start new experiments."""
import json
from pathlib import Path
from evaluate_events import evaluate_windows

run=Path('runs/green-small-separate-dynamic-onnx-full-20260930')
read=lambda p:[json.loads(x) for x in Path(p).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
review=read('reviews/green-small-separate-bus-v2-full-20260930-identity.jsonl')
result=evaluate_windows(read(run/'events.jsonl'),read('reviews/green-development-windows.jsonl'),0,review)
result['identity_transfer_basis']='Complete 513-frame PT/ONNX boxes and exact event ID/frame/direction parity; original PT source montage reviewed.'
with (run/'identity-evaluation.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)

p=Path('CHECKPOINT.md');s=p.read_text(encoding='utf-8');a=s.index('최근 확인 사용량');b=s.index('다음 우선순위:',a)
s=s[:a]+'''마지막 확인5시간89%/주간30% 사용(잔여11%/70%). 사용자가 이번 작업을 마치고 나중에 재개하겠다고 지시해 중단한다. 목표 paused, 진행 중 학습/추론 없음. 최신 단위77·컴파일·git diff --check 통과.

완료: 초록 calibrated PT/동적 ONNX 전체513 각각 IN5·부분5/6; 사람S/버스M 별도 후보 PT 및 세 모델 모두 동적 ONNX 전체513도 문508·IN5/OUT0·부분5/6. `runs/green-small-separate-dynamic-export-parity-20260930.json` 전체 박스 차이0·정확한 이벤트 frame/ID/방향 일치. 최신 ONNX 실행 감사 implementation drift 없음, 각 CPU ORT intra2/inter1. 부정 영상341문0집계0. 기존 정적 square IN3 실패·도시S IN377 아이 반대 이벤트는 미채택. 도시 ReID도2/3이며 누락 회복 없음.

최신 코드 인공 소실/재등장105 전체 `reentry-margin-latest-full-20260930` IN2(frame26/96)·문77·감사 drift 없음. retrack_people 실제 모델/참조 summary/구현 hash와 전처리 rect 설정 보완 후 `reentry-frozen-provenance-full-20260930` 같은2명·전체105 감사 통과. 고정 문 재추적은 사람 모델 비교이며 문 검출 전체 검증과 구분한다. 합성 자료는 실제 두 버스/새 정차 증거가 아니다.

재현 후보: `configs/bus-portal-small-separate-dynamic-onnx-candidate.json`. 설정·모델/영상 hash·모든 이벤트·감사·실패 자료 보존. ORT FP32 CPU 변환 검증이며 TensorRT/Orin 속도·메모리·정확도 검증은 없다.

'''+s[b:];s=s.replace('목표는 active 상태다.','이번 작업 종료 시 목표 paused 상태이며 사용자의 재개 지시를 기다린다.');p.write_text(s,encoding='utf-8')
note='''2026-09-30 작업 종료: 사용자 요청에 따라 현재 실행을 모두 완료하고 중단. 사람S/버스M/문nano의 동적 ONNX 전체513에서 PT 대비 박스 차이0·이벤트 frame/ID/방향 일치, 문508·승차5/하차0·부분5/6. 최신 구현 해시 drift 없음. 최신 인공 재등장105 전체·고정 문 재추적 모두IN2·감사 통과, 추적 비교 모델/참조/구현 해시 보완. 단위77·컴파일 통과. 잔여 한도 마지막11%/70%, 진행 중 작업 없음. 갈색 상의·도시 회색 외투 누락과 독립촬영/Orin 검증은 다음 재개 과제.'''
for p in [Path('STATUS.md'),Path('RESULTS.md'),Path('../../docs/CURRENT_STATUS.md'),Path('../../docs/WORKLOG.md')]:
    s=p.read_text(encoding='utf-8-sig');first,rest=s.split('\n',1);p.write_text(first+'\n\n'+note+'\n'+rest,encoding='utf-8')
p=Path('README.md');s=p.read_text(encoding='utf-8');marker='## 현재 개발 후보와 내보내기 검증\n'
s=s.replace(marker,marker+'''\n사람 YOLO11s/버스 YOLO11m 간헐 검출을 분리한 `bus-portal-small-separate-dynamic-onnx-candidate.json`도 전체513프레임 IN5/OUT0·부분5/6이다. 세 모델의 동적 ONNX/PT 전체 박스 및 이벤트가 일치했다. 선택 의존성 기록은 `requirements-onnx-export-tested.txt`; 이는 CPU 개발 검증이며 Orin 환경 설치 잠금이 아니다.\n''',1);p.write_text(s,encoding='utf-8')
print('Checkpoint closed; no running experiments.')
