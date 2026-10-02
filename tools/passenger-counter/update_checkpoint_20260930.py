"""Add a dated project checkpoint without replacing other project work."""
from pathlib import Path

root=Path('../..')
summary='''2026-09-30 최신 승차 계수: 초록 전체513프레임에서 학습 출입구+문턱 보정+부분 추적 연결로 승차5/하차0·기존 부분 인물/시각5/6, 동적 ONNX 전체513도 PT와 이벤트/박스가 일치했다. 사람 YOLO11s 매프레임/버스 YOLO11m 5프레임 간격 분리 후보도 문508·승차5/하차0·5/6을 유지했고 버스 없는341프레임은 문0·집계0이다. 도시 전체761은 승차1/하차1·2/3, 작은 사람 모델의 추가 승차는 아이의 반대방향 오류라 미채택. 갈색 상의 승차/회색 외투 하차 누락, 새 독립 영상·사람 교정 라벨·Orin 실측은 남았다. 코드단위77 통과. 모든 수치는 개발 영상의 부분 검토이며 전체 정확도가 아니다.'''
for path,target in [(Path('STATUS.md'),'RESULTS.md'),(root/'docs/CURRENT_STATUS.md','../tools/passenger-counter/RESULTS.md')]:
    old=path.read_text(encoding='utf-8-sig'); first,rest=old.split('\n',1)
    path.write_text(first+'\n\n'+summary+' [실험 근거]('+target+'). 과거 기록은 아래에 보존한다.\n'+rest,encoding='utf-8')

detail='''
## 2026-09-30 — 배포 전 변환·경량화·회귀 비교 최종 갱신

- calibrated custom 전체513: 문508, IN5/OUT0(frame61 ID15,181 ID30,267 ID2,332 ID68,355 ID66). 기존 인물 구간5/6, 갈색 셔츠 누락. 사람/문 동적 FP32 ONNX도 전체513 박스/ID/이벤트 동일(`green-dynamic-export-parity-20260930.json`). 고정 square ONNX는 IN3으로 악화해 초록 후보에 채택하지 않는다. 표본 변환 성공과 전체 집계 동일성은 별도로 검사했다.
- 별도 YOLO11s 사람/YOLO11m 버스 후보 v2 전체513: 문508, IN5(frame64 ID26,173 ID71,260 ID1,331 ID89,358 ID93), OUT0, 검토5/6. 원본 이벤트 모음·전체 해시·재생 감사·identity 평가 저장. 버스 강한 검출 없이 약한 후보만으로 시작하지 않으며, 약한 재확인은 최근 관측/특징점 연속성과 강한 앵커로부터 최대3초 제한을 요구한다. 버스 없는341프레임: 문0·IN0/OUT0. 사람S 단독 전체는 버스 class가 초반 끊겨 문442·IN4·4/6; 모델 분리로 첫 승객 회복. 두 모델의 장치 메모리/실시간 비용은 Orin에서 아직 측정하지 않았다.
- 도시 사람S 전체761: OUT368 ID46/IN377 ID46/IN421 ID2. 원본에서 아이의 하차 뒤9프레임 반대 이벤트를 확인해 IN377 uncertain으로 제외; 유효 부분 대응2/3이며 개선 미채택. ReID proximity .1 고정 문 재추적도 OUT365 ID21/IN422 ID2·2/3으로 회색 외투를 회복하지 못했다.
- 원본 x방향 정적 PT/ONNX 전체109는 IN1 frame28 ID2와 박스/ID/이벤트 일치. 정지60 IN0/OUT0, 역재생109 OUT1 frame96, 검정 공백/재등장105 IN2(frame29/98) 회귀 통과. 합성 수평 이동109는 문을 찾았으나 내부 경계 .25를8픽셀 못 넘어 IN0이었고 .3/.4 보정 후 IN1 frame27 ID1. 위치 이동·역재생·재등장 자료는 같은 원본의 인공 변형이며 독립 정차/실제 하차 증거가 아니다.
- 혼합 학습 nbs64 완료: public30 mAP50 .269825/bus개발3 .252307. 버스12장 반복16 후보: .363229/.221111. 후자는 분홍 표본4개 모두conf .1 이상 문 없음; 전자는 초기3표본 없음/후반 약한 잘못된 후보. 합산 지표만으로 새 모델을 채택하지 않는다. bus 반복은 고유 사진12를 늘리지 않는다.
- ONNX CPU 세션 intra2/inter1·출력 IO binding 재연결을 실제 반복 추론으로 검사했고 CUDA 세션은 변경하지 않는다. 사람이 통과할 두 구역이 화면 밖이면 진단을 남긴다. 실제 카메라에서는 처리 FPS가 낮아도 시간 기준으로 문/버스 검사 주기가 잠금 TTL/게이트 grace보다 길어지지 않도록 추가했으며 시간 모의 단위검사만 완료; 실제 카메라 미검증. 단위77 통과.
- public 데이터 추가 조사: PCDS는 버스문 위 Kinect 자료로 카메라 각도/라이선스가 다르며 새 원시 자료를 확보하지 않았다. 공개 bus-door 페이지에 모델/버전이 없는 사례도 있어 즉시 학습 가능하다고 말하지 않는다. 사람 교정 라벨과 새로운 촬영 회차가 다음 일반화 개선의 우선순위다.
- CPU를 공유한 관측 FPS는 공정 성능 비교가 아니며 TensorRT/FP16/INT8/Orin 측정은 없다. 선택 옵션을 추가한 개발 후보이고 전체 서비스 방향은 변경하지 않았다. 결과 폴더의 completion-audit는 시작 뒤 run.py 변경 drift를 별도로 표시한다.
'''
p=Path('RESULTS.md');old=p.read_text(encoding='utf-8-sig');first,rest=old.split('\n',1);p.write_text(first+'\n'+detail+'\n'+rest,encoding='utf-8')
p=root/'docs/WORKLOG.md';old=p.read_text(encoding='utf-8-sig');first,rest=old.split('\n',1);p.write_text(first+'\n'+detail+'\n'+rest,encoding='utf-8')
p=Path('CHECKPOINT.md');old=p.read_text(encoding='utf-8-sig');a=old.index('### 가장 최신 재개 위치');b=old.index('추가 갱신: 사용량5시간27%',a)
checkpoint='''### 가장 최신 재개 위치

최근 확인 사용량5시간84%/주간29% 사용(10% 잔여 경계는90% 사용). 최신 단위77 통과. 아래는 최신 결과이며 이후 기록은 과거 실행이다. 모든 새 학습/전체 영상 비교가 완료됐고 성공·실패를 RESULTS에 기록했다. `green-small-separate-bus-v2-full-20260930`513문508 IN5, 부분5/6; `people-small-separate-bus-negative-20260930`341문0집계0. 감사/인물 평가 완료. 동적 ONNX 전체513 PT 일치·5/6, 정적 square는3/6으로 미채택. 도시S 추가IN377은 아이 반대방향 오류; 두 ReID 후보도2/3로 미채택.

최신 run.py에는 시간 기반 카메라 검사 주기 helper가 추가돼 이전 실행에는 run.py hash drift가 표시된다. 최신 코드 전체 재실행 `reentry-margin-latest-full-20260930`(세션59827)105프레임: 마지막96에서IN2/OUT0, 종료 summary·완전성 감사 필요. x 경계 .3/.4·ONNX이며 동일 원본 인공 공백 회귀다. 나머지 학습/추론 백그라운드 작업 없음.

다음 우선순위: (1) 최신 코드 재등장 회귀 종료/감사, (2) 갈색 상의85~105의 가림/ID4 소실을 원본으로 교정한 tracklet 자료로 다루되 인물을 추측해 이어붙이지 않기, (3) 도시 회색 외투 하차 인물 분리, (4) 사람이 교정한 버스/강의실 출입구 및 새 독립 촬영 확보, (5) Orin 환경/카메라 FPS·메모리·TensorRT 변환/집계 동일성. 모델 확대·기본 ReID·문 주변 ROI·학습 비중 반복만으로 누락은 해결되지 않았다. 결과 창을 움직여 맞추지 않는다. 한도90% 도달 시 기록을 갱신하고 멈춘다.

'''
p.write_text(old[:a]+checkpoint+old[b:],encoding='utf-8')
p=Path('README.md');old=p.read_text(encoding='utf-8-sig');old=old.replace('가변 입력 전체 검증은 진행 중이다','가변 입력 전체513프레임은 PT와 박스/ID/이벤트가 일치해 IN5를 유지했다');p.write_text(old,encoding='utf-8')
print('Updated checkpoint, status, results, README and project worklog.')
