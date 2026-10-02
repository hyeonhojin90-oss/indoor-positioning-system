"""Render and audit the offline room-segment study, without editing raw data."""
import hashlib
import json
import math
from collections import Counter
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir())/"indoor-room-segments-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "indoor/data/analysis/room-segments-20261002"
r = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
targets = [t for t in r["targets"] if t["platform"] == "android"]
sessions = {s["id"]: s for s in r["sessions"]}

def correlation(a, b):
    am, bm = sum(a) / len(a), sum(b) / len(b)
    aa = sum((v-am)**2 for v in a)
    bb = sum((v-bm)**2 for v in b)
    return sum((x-am)*(y-bm) for x,y in zip(a,b)) / math.sqrt(aa*bb) if aa*bb else None

correlations = []
for i, a in enumerate(targets):
    for b in targets[i+1:]:
        if a["direction"] == b["direction"]:
            correlations.append({"a":a["session"], "b":b["session"], "direction":a["direction"],
                                 "normR":correlation(a["canonicalNorm"], b["canonicalNorm"]),
                                 "mvR":correlation(a["canonicalMv"], b["canonicalMv"])})
(OUT / "repeat-correlations.json").write_text(json.dumps(correlations, ensure_ascii=False, indent=2), encoding="utf-8")

checks = []
def check(name, condition):
    checks.append({"name":name, "passed":bool(condition)})
    if not condition:
        raise AssertionError(name)

check("22 complete sessions and 1 excluded short session", len(sessions)==22 and sum(not m.get("included",False) for m in r["manifest"])==1)
check("8 Android and 14 iOS sessions", sum(s["platform"]=="android" for s in sessions.values())==8 and sum(s["platform"]=="ios" for s in sessions.values())==14)
check("analysis code SHA matches executed version", hashlib.sha256((ROOT/"indoor/tools/evaluate_room_segments_20261002.cjs").read_bytes()).hexdigest()==r["analysisCodeSha256"])
check("runtime SHA matches recorded detector", hashlib.sha256((ROOT/"indoor/web/src/positioning/runtime.js").read_bytes()).hexdigest()==r["runtimeCodeSha256"])
for m in r["manifest"]:
    check("raw SHA unchanged: "+Path(m["file"]).name, hashlib.sha256((ROOT/m["file"]).read_bytes()).hexdigest()==m["sha256"])
for s in sessions.values():
    check("monotonic step times: "+s["id"], all(b["time"]>a["time"] for a,b in zip(s["points"],s["points"][1:])))
    check("9 adjacent-room intervals: "+s["id"], len(s["segments"])==9)
    check("vertical magnitude physically bounded: "+s["id"], all(p["mv"] is None or p["norm"] is None or abs(p["mv"])<=p["norm"]+1e-6 for p in s["points"]))
    for t in s["segments"]:
        check("step count inside manual interval: "+s["id"]+"/"+t["pair"], sum(t["startTime"]<p["time"]<=t["endTime"] for p in s["points"])==t["steps"])
for e in r["evaluations"]+r["contextEvaluations"]:
    for p in e["predictions"]:
        check("query excluded from training", p["session"] not in p["trainingSessions"])
        if e["fold"]=="day":
            check("query date excluded from training", all(sessions[x]["date"]!=sessions[p["session"]]["date"] for x in p["trainingSessions"]))
        check("prediction credit finite", math.isfinite(p["credit"]) and 0<=p["credit"]<=1)
for a in r["arrivals"]:
    check("causal test source exclusion", a["session"] not in a["referenceSessions"])
    if a["fold"]=="day":
        check("causal test date exclusion", all(sessions[x]["date"]!=a["date"] for x in a["referenceSessions"]))
    if a["predictedSteps"] is not None:
        k=a["predictedSteps"]
        check("crossing confirmed using present and past only", k>=1 and a["history"][k-1]["progress"]>=1 and a["history"][k]["progress"]>=1)
verification = {"passed":len(checks), "failed":0, "groups":dict(Counter(c["name"] for c in checks))}
(OUT / "verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")

font_path=Path("C:/Windows/Fonts/malgun.ttf")
if font_path.exists():
    plt.rcParams["font.family"] = FontProperties(fname=str(font_path)).get_name()
plt.rcParams["axes.unicode_minus"] = False
fig, axes = plt.subplots(2,2,figsize=(12,7.6),constrained_layout=True)
for col,direction in enumerate(["forward","reverse"]):
    selected=[t for t in targets if t["direction"]==direction]
    for t in selected:
        a=t["canonicalNorm"]
        x=[i/(len(a)-1) for i in range(len(a))]
        stamp=t["session"].removeprefix("indoor_positioning_")
        label=f"{stamp[4:6]}/{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]} · {t['steps']}걸음"
        line,=axes[0,col].plot(x,a,label=label,linewidth=1.7)
        average=sum(a)/len(a)
        axes[1,col].plot(x,[v-average for v in a],color=line.get_color(),linewidth=1.7)
    axes[0,col].set_title(("정방향 4213 → 4212" if col==0 else "역방향 4212 → 4213 (곡선 방향 반전)")+" · Android")
    axes[0,col].set_ylabel("자기장 크기 |m| (µT)")
    axes[1,col].set_ylabel("구간 평균을 뺀 변화 (µT)")
    axes[0,col].legend(fontsize=8,loc="best")
    for ax in axes[:,col]:
        ax.set_xlabel("4213쪽 → 4212쪽 정규화 진행도 (m 아님)")
        ax.grid(alpha=.2)
fig.suptitle("4213–4212 반복 보행: 닮은 곡선과 회차별 편차",fontsize=15)
fig.savefig(OUT/"4213-4212-patterns.png",dpi=150)
plt.close(fig)

lines=["# 4층 오른쪽 복도: 자기장 구간 판단 + 걸음 연결 평가", "",
       "2026-10-02. 운영 엔진·지도·원본·APK를 바꾸지 않은 PC 실험이다. 도면 문 위치나 끝점 보간 거리를 정답으로 사용하지 않았다.", "",
       "## 결론", "",
       "4213–4212에는 반복되는 자기장 곡선이 있다. 그러나 모든 회차에서 똑같지 않고, 다른 복도 구간에도 비슷한 곡선이 있다. 알려진 시작점·실제 통로 순서·걸음을 유지하며 자기장을 보조로 쓰는 시험은 가능하지만, 자기장으로 전체 강의실 위치를 바로 확정하는 근거는 아직 부족하다.", "",
       "## 자료와 정답 범위", "",
       "- 후보 23파일 중 완료된 Android 8회(SM-S938N, 9/1·9/19·9/22), iOS 14회를 기기별로 분리했다. 9/19 11:15:21 짧은 시작 자료 1회는 완료/호실 랩 부족으로 제외했다. 파일 SHA와 제외 이유는 results.json에 있다.",
       "- Android는 4213~4204 사이 인접 호실 구간 9종×8회=72개, iOS는 126개다. Android 정방향 5회·역방향 3회다.",
       "- 수동 랩 시각을 해당 호실 통과의 관측 기준으로 사용한다. 실제 문 정면 좌표·정확한 탭 지연·실제 한 걸음은 독립 측정한 정답이 아니다. m 오차로 환산하지 않는다.",
       "- 현재 공용 런타임의 가속도 검출기로 걸음을 다시 검출했다. 원시 센서 단조 시각과 파일별 wall-time 차이의 하위 5%를 이용한 시각 정렬을 썼고, 기존 callback 시각 결과도 함께 저장했다. 목표 구간의 걸음 수는 두 시각 방식이 모두 같다.",
       "- |m|은 자기장 벡터 크기, m_v는 저역통과 가속도로 추정한 중력 방향에 자기장을 투영한 수직 성분이다. 휴대폰 원시 y축 my가 아니다. 이동 중 중력 추정은 별도 오차를 포함한다.", "",
       "## 4213–4212 원시 구간 결과", "",
       "초반/후반 값은 해당 구간 첫/마지막 두 걸음의 자기장 중앙값이다. 문 앞 정지 측정값으로 해석하지 않는다.", "",
       "| 파일 시각 | 방향 | 랩 간 시간 | 가속도 재검출 | 앱 카운터 차이 | |m| 초반→후반 (µT) |", "|---|---|---:|---:|---:|---:|" ]
for t in targets:
    stamp=t["session"].removeprefix("indoor_positioning_")
    label=f"{stamp[4:6]}/{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}"
    lines.append(f"| {label} | {'4213→4212' if t['direction']=='forward' else '4212→4213'} | {t['durationS']:.2f}s | {t['steps']} | {t['rawCounterSteps']} | {t['startMag']:.1f}→{t['endMag']:.1f} |")
lines += ["", "정방향 재검출은 6~11걸음(중앙값10), 역방향은8~9걸음(중앙값9)이다. 최근 9/19·9/22만 보아도 정방향6·10·9걸음이다. 단일 9걸음 또는10걸음을 정답으로 고정하면 이 차이가 남는다.",
          "앱 카운터가0인 회차가 있어 그대로 차분하면 안 된다. 정상적으로 증가한 카운터도 재검출과 차이가 있다(9/1은7·8 대11·11). 어느 쪽도 실제 발걸음 정답으로 단정하지 않았다. 랩 시각을 양 끝 각각±0.5초 바꾼 재검출 민감도도 results.json에 기록했다.", "",
          "같은 방향으로 정렬한 |m| 변화곡선 상관계수는 정방향0.210~0.997, 역방향0.160~0.982다. 9/22 19:14 대20:27 정방향은0.9967, 9/19 11:13 대9/22 20:29 역방향은0.9823이다. 9/22 19:15 역방향은 다른 역방향 둘과0.233·0.160으로 다르다. 높은 상관계수는 같은 구간이 닮았다는 근거이며 다른 구간과 구별된다는 증거는 아니다.", "",
          "![자기장 곡선](4213-4212-patterns.png)", "",
          "## 구간 식별: 평가 회차/날짜 제외", "",
          "평가 파일은 참조에서 빼고 같은 기기·같은 진행 방향의 나머지 자료로9개 인접 구간 중 하나를 고른다. 날짜 제외는 같은 날 왕복도 모두 참조에서 뺀다. 시작·끝 랩으로 잘라 준 구간을 분류하는 유리한 조건이며 실시간 호실 인식 정확도가 아니다.",
          "평균 제거 비교와 V2와 같은 정규화/DTW 함수 비교를 분리했다. DTW는 변화 모양과 걷는 속도 차이를 비교하나 짧은 구간을16점 보간한 시험이며 운영8걸음 V2의 재생 결과와 동일하지 않다.", "",
          "| 방식 | 회차 제외 4213–4212 | 회차 제외 전체 인접 구간 | 날짜 제외 4213–4212 |", "|---|---:|---:|---:|" ]
names={"mag_norm":"절대 |m| 곡선", "mag_shape":"평균 제거 |m| 변화", "mag_dtw":"정규화 DTW |m|", "mag_dtw_mv":"정규화 DTW |m|+m_v", "mag_dtw_steps":"정규화 DTW |m|+걸음", "mag_dtw_mv_steps":"정규화 DTW |m|+m_v+걸음"}
for key,name in names.items():
    a=next(e for e in r["evaluations"] if e["platform"]=="android" and e["fold"]=="session" and e["directionPolicy"]=="same" and e["method"]==key)
    b=next(e for e in r["evaluations"] if e["platform"]=="android" and e["fold"]=="day" and e["directionPolicy"]=="same" and e["method"]==key)
    lines.append(f"| {name} | {a['target']['correct']}/{a['target']['total']} | {a['correct']}/{a['total']} | {b['target']['correct']}/{b['target']['total']} |")
lines += ["", "전체 비율과 동점 후보를 등분한 accuracy는 results.json을 참조한다. m_v나 걸음을 추가할수록 항상 좋아지는 것은 아니다. 위 표는1위로 고른 정수 건수다.", "",
          "목표 구간을 맞힌 건수와 잘못 그 구간이라고 부른 건수도 나눠야 한다. 크기+수직성분 DTW+걸음에서 목표8회 중7회는 맞았지만 다른64구간 중5개도4213–4212라고 불렀다. 이 구간이라고 고른12건 중 맞은 것은7건(58.3%)이다. 날짜 제외에서는 다른 구간7개를 이 구간으로 불러14건 중7건(50%)이다. 7/8만으로 강의실 도착을 확정할 수 없다.", "",
          "iOS 자료도 별도 평가했다. 같은 회차 제외 크기+수직성분 DTW+걸음에서 목표 구간14/14, 전체93/126이었다. 기기와 수집 조건이 다른 결과이므로 Android 성능으로 옮겨 말하지 않는다.", "",
          "2·3구간을 연결한 긴 곡선도 비교했다. 경계가 주어지고 후보 수가8/7종으로 줄어드는 별도 조건이므로1구간과 동일 조건의 성능으로 비교하지 않는다.", "",
          "| 연속 랩 구간 수 | 크기+수직성분 DTW 회차 제외 | 날짜 제외 | 걸음 점수 추가·회차 제외 |", "|---|---:|---:|---:|" ]
for width in [2,3]:
    a=next(e for e in r["contextEvaluations"] if e["width"]==width and e["fold"]=="session" and e["method"]=="mag_dtw_mv")
    b=next(e for e in r["contextEvaluations"] if e["width"]==width and e["fold"]=="day" and e["method"]=="mag_dtw_mv")
    c=next(e for e in r["contextEvaluations"] if e["width"]==width and e["fold"]=="session" and e["method"]=="mag_dtw_mv_steps")
    lines.append(f"| {width} | {a['correct']}/{a['total']} | {b['correct']}/{b['total']} | {c['correct']}/{c['total']} |")
lines += ["", "걸음을 구간 이름의 독립 점수로 강하게 더하는 것과 현재 위치에서 다음으로 진행하는 연결에 쓰는 것은 다르다. 긴 구간에 고정된 걸음 점수를 추가한 설정은 악화됐다. 걸음으로 진행을 연결하고 자기장을 보조 관측으로 쓰는 시험을 별도로 수행했다.", "",
          "## 시작점만 알려준 도착 시점 시험", "",
          "정방향4213/역방향4212의 첫 랩만 초기화에 사용했다. 목표 랩은 모델에 주지 않고 채점에만 사용했다. 다음 호실 랩(정방향4211, 역방향코어)까지의 입력에서 목표 도달을 판단했다. 실제 비콘이 그 시작 호실에 설치됐다는 뜻은 아니다. 진행 방향은 경로로 알려 주고 휴대폰 방위는 사용하지 않았다. 중간 U턴이 있는 자유이동 자료 시험은 아니다.",
          "걸음은 참조 구간 걸음수 중앙값으로 진행을 연결했다. 자기장 결합은 같은 진행축 후보를 가중했다. DTW결합은 현재까지의 최대8걸음 창을 쓰며5걸음부터 비교했다. 도달은 두 연속 관측으로 확인하고 첫 교차 걸음의 오차를 기록한다(실제 발표는1걸음 뒤).", "",
          "| 방식 | 회차 제외 도달/8 | 도달한 회차의 평균 오차 | 최대 오차 | 날짜 제외 도달/8·평균 오차 |", "|---|---:|---:|---:|---:|" ]
for key,name in {"steps":"걸음 연결", "mag_norm_steps":"절대 |m|+걸음", "mag_relative_steps":"시작 대비 |m| 변화+걸음", "mag_relative_mv_steps":"시작 대비 |m|+m_v 변화+걸음", "mag_dtw_steps":"진행 중 DTW |m|+걸음", "mag_dtw_mv_steps":"진행 중 DTW |m|+m_v+걸음"}.items():
    a=next(e for e in r["arrivalSummary"] if e["platform"]=="android" and e["fold"]=="session" and e["method"]==key)
    b=next(e for e in r["arrivalSummary"] if e["platform"]=="android" and e["fold"]=="day" and e["method"]==key)
    lines.append(f"| {name} | {a['detected']} | {a['maeSteps']:.2f}걸음 | {a['maxErrorSteps']}걸음 | {b['detected']}·{b['maeSteps']:.2f}걸음 |")
lines += ["", "평균은 도달을 검출한 회차만의 조건부 평균이다. 미검출을 제외한 작은 평균만으로 개선을 주장하지 않는다. 시작점/수동 랩이 알려진 예비 시험이며 전체 경로 종점m 오차가 아니다.", "",
          "## 판단과 다음 구현 경계", "",
          "- 4213–4212의 구간별 걸음 분포와 자기장 패턴을 기존 자료로 추출하는 것은 가능하다. 복도의 상세 위치 후보를 유지하는 참조로 쓸 수 있다.",
          "- 기준점 비콘으로 코어/계단 위치를 확인한 뒤 통로 진행 상태와 걸음으로 연결하고, 자기장 곡선의 일치가 유효할 때 주변 후보만 조정하는 시험을 이어갈 근거는 있다. 강의실을 특정 걸음 수로 확정하거나 자기장 하나로 순간 이동시키는 근거는 없다.",
          "- m_v가 도움이 되는 구간 식별과 도움이 없는 도착 시점 조건을 분리한다. 이동 중 자기장 패턴을 버리거나 모든 구간에 동일한 큰 가중치를 주는 것으로 결론내리지 않는다.",
          "- 참조 신호 보정의 신뢰도/판단 보류, 실제 코어 시작으로 이어진 전 경로 상태 추적, U턴과 파지 변경 자료는 별도 검증이 남는다. 이번 결과로 운영 엔진의 PDR을 제거하지 않았다.", "",
          "## 재현·검증", "", "```powershell", "node indoor/tools/evaluate_room_segments_20261002.cjs", "& 'tools/passenger-counter/.venv/Scripts/python.exe' -X utf8 indoor/tools/report_room_segments_20261002.py", "```", "",
          "Node 평가기는 별도 패키지가 필요 없다. 그림은 이미 설치된 프로젝트 Python의 matplotlib를 재사용했다. 이 Python 환경이나 승차 집계 코드/데이터는 수정하지 않았다.", "",
          f"원본 SHA, 실행 코드 SHA, 회차/날짜 참조 제외, 걸음/구간 경계, m_v 물리 범위, 현재/과거 입력으로만 도달 확인한 것을 검사했다. {len(checks)}개 검증 통과. 수치·원본 manifest·예측별 참조 회차는 results.json, 원시 대상 구간 표는target-segments.csv, 무결성 검사는verification.json에 있다." ]
report="\n".join(lines)+"\n"
# Escape magnitude bars within Markdown table cells.
report=report.replace("| |m| 초반", "| 자기장 초반").replace("| 절대 |m|", "| 절대 크기").replace("| 평균 제거 |m|", "| 평균 제거 크기").replace("| 정규화 DTW |m|", "| 정규화 DTW 크기").replace("| 시작 대비 |m|", "| 시작 대비 크기").replace("| 진행 중 DTW |m|", "| 진행 중 DTW 크기")
(OUT / "REPORT.md").write_text(report, encoding="utf-8")
print(json.dumps({"verificationPassed":len(checks), "report":str(OUT/"REPORT.md"), "plot":str(OUT/"4213-4212-patterns.png")}, ensure_ascii=False))
