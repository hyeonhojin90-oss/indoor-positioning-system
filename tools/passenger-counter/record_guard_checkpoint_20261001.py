"""Close the completed experiments with verified counts, reviews and usage."""
import json
from pathlib import Path
from latest_usage import latest

session=Path('C:/Users/20222967/.codex/sessions/2026/09/18/rollout-2026-09-18T20-25-08-01a0b417-a35f-7f33-a8e7-d28bc7398f3d_01a0b443-5bc9-7c11-80e2-c2c99e610aac.jsonl')
usage=latest(session)
Path('runs/usage-resume-latest.json').write_text(json.dumps(usage,indent=2),encoding='utf-8')
names=[
 'green-aux-pose-latest-20261001-full','green-shift-right80-aux-20261001-full','green-shift-left80-aux-20261001-full',
 'green-lost-reid-guard-20261001-full','green-shift-right80-lost-reid-guard-20261001-full','people-lost-reid-guard-20261001-full',
 'green-partial-door-20261001-full','green-shift-left80-partial-door-20261001-full',
 'green-partial-retry-20261001-full','green-shift-right80-partial-retry-20261001-full','green-shift-left80-partial-retry-20261001-full',
 'green-shift-left80-guard-combined-20261001-full','green-shift-right80-small-door-20261001-full',
 'green-small-last-door-20261001-full','green-shift-left80-small-last-door-20261001-full','green-shift-right80-small-last-door-20261001-full']
comparison=[]
for name in names:
    run=Path('runs')/name
    summary=json.loads((run/'summary.json').read_text())
    audits=list(run.glob('completion-audit*.json'))
    if not audits:raise ValueError(f'No completed audit: {name}')
    audit=json.loads(audits[0].read_text())
    if not audit['complete_source'] or not audit['replay_parity'] or audit['counts']!=summary['counts']:
        raise ValueError(f'Incomplete or inconsistent run: {name}')
    evaluation=run/'identity-evaluation.json'
    matched=json.loads(evaluation.read_text())['matched_reviewed_events'] if evaluation.exists() else None
    comparison.append(dict(run=name,frames=summary['frames'],counts=summary['counts'],
                           source_sha256=summary['source_sha256'],matched_fixed_partial=matched,
                           completion_audit=str(audits[0]),model_sha256=summary['model_sha256'],
                           config=summary['config'],independent_accuracy_validated=False,jetson_validated=False))
Path('runs/resume-guard-comparison-20261001.json').write_text(json.dumps(dict(usage=usage,runs=comparison,
    note='Saved completion audits describe checks at their writing time; later implementation changes are not a new deployment validation.'),indent=2),encoding='utf-8')
stop='사용자 기준95% 도달을 확인해 이번 작업을 중단한다. 실행 중인 학습/영상 작업은 없다.' if usage['fresh'] and usage['stop_reached'] else '사용자95% 중단 기준에는 아직 도달하지 않았다. 다음 사용량 확인까지 새 장시간 실행은 시작하지 않고 결과 기록을 점검한다.'
note=f'''## 2026-10-01 최종 전체 비교와 다음 재개 지점

{stop} 마지막 계정 확인: 5시간 사용량{usage['primary_used_percent']}%·잔여{usage['primary_remaining_percent']}%, 관측UTC `{usage['timestamp']}`. 원시 토큰 잔량과 계정 사용률은 다른 값이다.

현재 보존 기준은 `configs/bus-portal-aux-pose-gated-onnx-candidate.json`이다. 모든 수치는 기존 개발 영상과 합성 파생 영상의 전체513프레임 실행이다. 고정 부분 인물/시각 구간6개를 변경하지 않았다.

| 후보 | 원본 IN/OUT·일치 | 오른쪽80 IN/OUT·일치 | 왼쪽80 IN/OUT·일치 |
| --- | --- | --- | --- |
| 기존 all-ONNX | 6/0·6/6 | 4/0·2/6 | 4/0·3/6 |
| 부분 문 거부만 | 6/0·6/6 | 미실행 | 4/0·3/6 |
| 부분 문 거부+빠른 재확인 | 6/0·6/6 | 4/0·2/6 | 5/0·4/6 |
| 사라진 ID의 외형 불일치 거부 | 6/0·6/6 | 5/0·2/6 | 미실행 |
| 위 두 보정의 조합 | 미실행 | 미실행 | 5/0·4/6 |
| 새 small 문 best(epoch1) | 미실행 | 3/1·1/6 | 미실행 |
| 새 small 문 last(epoch11) | 2/0·1/6 | 3/1·2/6 | 3/0·2/6 |

실제 개선은 왼쪽 이동에서 문 가림 이후 갈색 승객의 실측 발목 관측88을 잃지 않고117에서 확정한 부분이다. 빠른 재확인 후보 `configs/bus-portal-aux-pose-partial-retry-candidate.json`은 부분 박스를 누락으로 취급한 뒤 확인 간격을15→5프레임으로 줄여 정상 문을 다시 관측한다. 유효 문과 마지막 정상 관측 TTL=1.5초를 무기한 연장하지 않는다. 양의 위치 이동은 기존대로 즉시 잠금을 무효화한다. 실제 부분 후보95/100 뒤105/110 누락을 거쳐115 정상 문으로 돌아왔다. 원본6명과 오른쪽 기존4명을 유지했다. 청록색 누락과 노란 가방304의1프레임 이른 집계는 남았다. 동작 기본값은 비활성이며 기존 기준 모델을 임의 승격하지 않았다.

외형 거부는 오른쪽 ID3 갈색→올리브 재연결을 막았지만 올리브 승객 누락과 다른 이른 이벤트가 남아 인물/시각2/6이다. 원본6/6 및 버스 없는 실제341프레임 자동 문0·IN0/OUT0·보조 자세0회를 확인했다. native PyTorch 특징에 의존하므로 all-ONNX나 TensorRT 배포 가능성을 검증한 것으로 취급하지 않는다. 두 보정 조합도 왼쪽5명·4/6으로 단독 빠른 재확인을 넘지 못했다.

새 small 문 학습은 같은12개 원래 학습 이미지의 위치/반전 증강48장을 사용하고11epoch에서 조기 종료했다. 검증2장이 고른 best는epoch1이었다. 마지막 모델의 학습 장면 사각형 경계는 좋아도 전체 계수는 나빠졌다. `door-small-last-bootstrap-shift-quality-20261001.json`의 원본/왼쪽/오른쪽 mean top IoU=0.933/0.912/0.877은 학습용 assistant bootstrap 사각형의 진단값이고 독립 정확도가 아니다. 마지막 모델 검증 mAP50=0.02044, 기존 시험3장 mAP50=0.07134; best 시험 mAP50=0.06690이다. 다른 소스에 적용할 근거가 부족하다. 원본에서 활성 문은508→408프레임, 문 세대는1→15 이상으로 자주 바뀌어 계수 상태가 초기화됐다. 표본의 박스 오차만으로 전체 추적/계수 개선을 판정하지 않는다.

완료 감사·실제 관측 프레임 이미지·인물 리뷰·평가는 각 `runs/*/`에 있다. 이번 비교 요약은 `runs/resume-guard-comparison-20261001.json`. 단위 테스트103개와 수정 Python 컴파일 검사 통과. 과거 감사의 실행 당시 구현 불변 기록은 보존했다. 마지막 실행은 모두 종료되어 미완료 작업을 완료로 둔 것이 없다.

다음 재개는 `partial-retry` 후보의 버스 없음/정지/기존 대각 카메라 음성 회귀를 먼저 추가하고, 오른쪽 위치의 초기 문 하단 오차와 청록 승객 ID 단절을 분리한다. 단순 모델 크기 증가나 임계값/정답 구간 조정으로 해결됐다고 하지 않는다. 새 문 학습에는 더 다양한 촬영의 검증 자료와 사람이 확인한 문 사각형이 필요하며, 현재17장 bootstrap·작은 반복 시험은 현장 일반화 근거가 아니다. Orin 장치·실제 정류장/강의실 카메라 실험은 여전히 미검증이다.

버스 승차 계수1순위와 대기 줄 규모→탑승 가능성 후속 목표는 보존했다. 기존 다른 작업의 DEC-032와 번호가 중복되어 우리 승차 목표 항목만 DEC-034로 정리했고 설계 내용은 변경하지 않았다. 다른 영역 변경은 되돌리지 않았고 원격 push/commit을 하지 않았다.

목표 UI는 여전히 blocked다. 도구에는 active로 재개하는 기능이 없고 computer-use 지침은 ChatGPT 데스크톱 UI 자동화를 금지하므로 UI 버튼을 조작하지 않았다. 실제 수정·학습·전체 비교는 위 기록처럼 재개하여 완료했으며 정확도 전체 해결로 표시하지 않았다.

'''
for name in ('STATUS.md','RESULTS.md','CHECKPOINT.md'):
    p=Path(name);p.write_text(note+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
brief=f'''## 2026-10-01 승차 계수 재개 결과와 중단점

문 가림 후 빠른 재확인으로 합성 왼쪽 이동의 전체 승차4→5명·고정 부분 인물/시각3/6→4/6으로 개선했다. 원본6/6을 유지하며 오른쪽 누락은 남았다. 외형 ID 거부·small 문 학습·보정 조합도 전체 비교했고 개선을 넘지 못해 기존 기본 설정을 보존했다. 단위 테스트103개 통과. 상세/다음 재개는 `tools/passenger-counter/CHECKPOINT.md`, 비교 증거는 `RESULTS.md`와 `runs/resume-guard-comparison-20261001.json`에 있다. 계정 사용량{usage['primary_used_percent']}% 확인. {stop} 승차 목표의 중복 결정 번호만 DEC-034로 정리했다. Orin/현장 정확도와 목표 UI 재개 상태는 검증되지 않았다.

'''
for name in ('../../docs/CURRENT_STATUS.md','../../docs/WORKLOG.md'):
    p=Path(name);p.write_text(brief+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
p=Path('README.md');s=p.read_text(encoding='utf-8-sig');addition='''
### 문 가림 재확인 개발 후보

`configs/bus-portal-aux-pose-partial-retry-candidate.json`은 부분 문 검출을 정상 관측으로 갱신하지 않고 빠르게 재확인한다. 전체 원본6/6·오른쪽2/6 유지, 왼쪽3/6→4/6(4→5명)이다. 기존 기본 후보를 자동 대체하지 않았다. 오른쪽 누락·왼쪽 청록 누락·독립 촬영·Orin 실행은 다음 검증 대상이다. 외형 거부 결합과 새 small 문 학습도 전체 비교했지만 추가 개선은 없었다.
''';p.write_text(s+addition,encoding='utf-8')
print(json.dumps(dict(usage=usage,completed_runs=len(comparison))))
