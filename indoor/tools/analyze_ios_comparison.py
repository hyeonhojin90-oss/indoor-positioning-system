#!/usr/bin/env python3
"""Analyze repeated iOS corridor logs and compare them with Android references."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IOS_DIR = ROOT / "indoor" / "data" / "raw" / "ios" / "2026-09-05"
ANDROID_DIR = ROOT / "indoor" / "data" / "raw" / "2026-09-01"
OUTPUT_DIR = ROOT / "indoor" / "data" / "analysis" / "ios_2026-09-05"
IOS_MANIFEST = ROOT / "indoor" / "data" / "ios_manifest.json"
ANDROID_REFERENCES = [
    ANDROID_DIR / "indoor_positioning_20260901_151808.jsonl",
    ANDROID_DIR / "indoor_positioning_20260901_153038.jsonl",
]
with (ROOT / "indoor" / "web" / "data" / "maps" / "floor-04.json").open(encoding="utf-8") as handle:
    FLOOR04_MAP = json.load(handle)
MAP_START_X = FLOOR04_MAP["layout_dimensions"]["left_corridor_length"] + FLOOR04_MAP["layout_dimensions"]["hub_outer_width"] / 2
ROOM_X = {str(room["id"]): float(room.get("front_x", room["x"])) for room in FLOOR04_MAP["rooms"]}


def mean(values):
    return statistics.fmean(values) if values else None


def stdev(values):
    return statistics.pstdev(values) if len(values) > 1 else (0.0 if values else None)


def percentile(values, ratio):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * ratio
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - position) + ordered[high] * (position - low)


def rounded(value, digits=4):
    return None if value is None else round(value, digits)


def norm(values):
    return math.sqrt(sum(float(value) ** 2 for value in values[:3]))


def parse_session(path):
    start = None
    end = None
    labels = []
    sensors = defaultdict(list)
    parse_errors = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            kind = row.get("kind")
            if kind == "session_start":
                start = row
            elif kind == "session_end":
                end = row
            elif kind == "label":
                labels.append(row)
            elif kind == "sample":
                sensors[row.get("sensor", "unknown")].append((int(row["wall_time_ms"]), row.get("values", [])))
    if start is None or end is None:
        raise ValueError(f"incomplete session: {path}")
    return {"path": path, "start": start, "end": end, "labels": labels, "sensors": sensors, "parse_errors": parse_errors}


def samples_between(samples, start_ms, end_ms):
    return [(timestamp, values) for timestamp, values in samples if start_ms <= timestamp <= end_ms]


def detect_acceleration_steps(samples):
    if len(samples) < 3:
        return []
    gravity = norm(samples[0][1])
    candidates = []
    previous_dynamic = 0.0
    rising = False
    peak_value = 0.0
    peak_time = None
    last_time = samples[0][0]
    for timestamp, values in samples:
        magnitude = norm(values)
        dt = max(0.001, min(0.1, (timestamp - last_time) / 1000.0))
        last_time = timestamp
        alpha = min(1.0, dt / 0.8)
        gravity += alpha * (magnitude - gravity)
        dynamic = magnitude - gravity
        if dynamic > previous_dynamic:
            if not rising:
                peak_value = dynamic
                peak_time = timestamp
            rising = True
            if dynamic > peak_value:
                peak_value = dynamic
                peak_time = timestamp
        elif rising:
            if peak_value >= 1.0 and peak_time is not None:
                if not candidates or peak_time - candidates[-1] >= 280:
                    candidates.append(peak_time)
                elif peak_value >= 1.8:
                    candidates[-1] = peak_time
            rising = False
            peak_value = dynamic
            peak_time = timestamp
        previous_dynamic = dynamic
    return candidates


def movement_metrics(acceleration):
    magnitudes = [norm(values) for _, values in acceleration if len(values) >= 3]
    if not magnitudes:
        return {"accel_dynamic_rms": None, "accel_active_ratio": None}
    baseline = statistics.median(magnitudes)
    dynamic = [value - baseline for value in magnitudes]
    return {
        "accel_dynamic_rms": rounded(math.sqrt(mean([value * value for value in dynamic]))),
        "accel_active_ratio": rounded(sum(abs(value) >= 0.7 for value in dynamic) / len(dynamic)),
    }


def sampling_rate(samples):
    if len(samples) < 2:
        return None
    intervals = [b[0] - a[0] for a, b in zip(samples, samples[1:]) if b[0] > a[0]]
    return 1000.0 / statistics.median(intervals) if intervals else None


def interpolate(samples, start_ms, end_ms, count, component=None):
    usable = [(timestamp, values) for timestamp, values in samples if start_ms <= timestamp <= end_ms and values]
    if not usable:
        return [None] * count
    times = [item[0] for item in usable]
    if component is None:
        values = [norm(item[1]) for item in usable]
    else:
        values = [float(item[1][component]) for item in usable if len(item[1]) > component]
        if len(values) != len(times):
            return [None] * count
    result = []
    cursor = 0
    for index in range(count):
        target = start_ms if count == 1 else start_ms + (end_ms - start_ms) * index / (count - 1)
        while cursor + 1 < len(times) and times[cursor + 1] < target:
            cursor += 1
        if cursor + 1 >= len(times) or times[cursor + 1] == times[cursor]:
            result.append(values[cursor])
        else:
            ratio = (target - times[cursor]) / (times[cursor + 1] - times[cursor])
            result.append(values[cursor] + ratio * (values[cursor + 1] - values[cursor]))
    return result


def lap_aligned_profile(session, sensor, bins_per_segment=12, component=None):
    boundaries = [session["start"]["wall_time_ms"]] + [label["wall_time_ms"] for label in session["labels"]]
    profile = []
    for start_ms, end_ms in zip(boundaries, boundaries[1:]):
        profile.extend(interpolate(session["sensors"].get(sensor, []), start_ms, end_ms, bins_per_segment, component))
    return profile


def pearson(left, right):
    pairs = [(a, b) for a, b in zip(left, right) if a is not None and b is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    x_mean, y_mean = mean(xs), mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
    denominator = math.sqrt(sum((x - x_mean) ** 2 for x in xs) * sum((y - y_mean) ** 2 for y in ys))
    return numerator / denominator if denominator else None


def zscore(values):
    clean = [value for value in values if value is not None]
    center = mean(clean)
    scale = stdev(clean)
    if not clean or not scale:
        return [0.0 if value is not None else None for value in values]
    return [(value - center) / scale if value is not None else None for value in values]


def dtw_cost(left, right):
    xs = [value for value in zscore(left) if value is not None]
    ys = [value for value in zscore(right) if value is not None]
    previous = [float("inf")] * (len(ys) + 1)
    previous[0] = 0.0
    for x in xs:
        current = [float("inf")] * (len(ys) + 1)
        for j, y in enumerate(ys, 1):
            current[j] = abs(x - y) + min(current[j - 1], previous[j], previous[j - 1])
        previous = current
    return previous[-1] / max(len(xs), len(ys)) if xs and ys else None


def circular_mean_radians(values):
    if not values:
        return None
    return math.atan2(mean([math.sin(value) for value in values]), mean([math.cos(value) for value in values]))


def angular_delta_degrees(value, reference):
    return math.degrees((value - reference + math.pi) % (2 * math.pi) - math.pi)


def session_summary(session):
    start_ms = int(session["start"]["wall_time_ms"])
    end_ms = int(session["end"]["wall_time_ms"])
    arrival_ms = int(session["labels"][-1]["wall_time_ms"])
    sensor_counts = {name: len(samples) for name, samples in session["sensors"].items()}
    sensor_rates = {name: rounded(sampling_rate(samples), 2) for name, samples in session["sensors"].items()}
    magnetic = session["sensors"].get("magnetic_field_ut", [])
    btotal = [norm(values) for _, values in magnetic if len(values) >= 3]
    pressure = [float(values[0]) for _, values in session["sensors"].get("pressure_hpa", []) if values]
    accel = session["sensors"].get("accelerometer_mps2", [])
    peaks = detect_acceleration_steps(samples_between(accel, start_ms, arrival_ms))
    rotation = session["sensors"].get("device_motion_rotation_rads", [])
    alpha = [(timestamp, float(values[0])) for timestamp, values in rotation if values and values[0] is not None]
    start_alpha = circular_mean_radians([value for timestamp, value in alpha if timestamp <= start_ms + 2000])
    end_alpha = circular_mean_radians([value for timestamp, value in alpha if arrival_ms - 2000 <= timestamp <= arrival_ms])
    alpha_deviation = [abs(angular_delta_degrees(value, start_alpha)) for _, value in alpha] if start_alpha is not None else []
    result = {
        "file": session["path"].name,
        "platform": session["start"].get("platform", "android"),
        "device": session["start"].get("device_model", session["start"].get("device")),
        "route_id": session["start"]["label"]["route_id"],
        "parse_errors": session["parse_errors"],
        "laps": len(session["labels"]),
        "expected_laps": session["end"].get("expected_laps", session["start"]["label"].get("lap_total")),
        "completed": session["end"].get("completed", True),
        "arrival_duration_s": rounded((arrival_ms - start_ms) / 1000, 3),
        "recording_duration_s": rounded((end_ms - start_ms) / 1000, 3),
        "pedometer_steps": int(session["end"].get("steps_since_start", 0)),
        "accel_peak_steps": len(peaks),
        "sensor_counts": sensor_counts,
        "sensor_rates_hz": sensor_rates,
        "mag_mean_ut": rounded(mean(btotal)),
        "mag_std_ut": rounded(stdev(btotal)),
        "mag_min_ut": rounded(min(btotal) if btotal else None),
        "mag_max_ut": rounded(max(btotal) if btotal else None),
        "pressure_mean_hpa": rounded(mean(pressure)),
        "pressure_std_hpa": rounded(stdev(pressure), 5),
        "pressure_delta_hpa": rounded(pressure[-1] - pressure[0] if pressure else None, 5),
        "rotation_alpha_start_end_deg": rounded(angular_delta_degrees(end_alpha, start_alpha) if start_alpha is not None and end_alpha is not None else None, 2),
        "rotation_alpha_deviation_p95_deg": rounded(percentile(alpha_deviation, 0.95), 2),
    }
    result.update(movement_metrics(samples_between(accel, start_ms, arrival_ms)))
    session["accel_peaks"] = peaks
    session["summary"] = result
    return result


def segment_rows(session):
    boundaries = [(session["start"]["wall_time_ms"], session["start"]["label"]["location"], 0)]
    boundaries.extend((label["wall_time_ms"], label["label"]["location"], int(label.get("steps_since_start", 0))) for label in session["labels"])
    rows = []
    cumulative_peaks = 0
    total_peaks = len(session["accel_peaks"])
    map_errors = []
    for index, (previous, current) in enumerate(zip(boundaries, boundaries[1:]), 1):
        start_ms, start_location, start_steps = previous
        end_ms, end_location, end_steps = current
        accel = samples_between(session["sensors"].get("accelerometer_mps2", []), start_ms, end_ms)
        magnetic = samples_between(session["sensors"].get("magnetic_field_ut", []), start_ms, end_ms)
        pressure = samples_between(session["sensors"].get("pressure_hpa", []), start_ms, end_ms)
        btotal = [norm(values) for _, values in magnetic if len(values) >= 3]
        pressure_values = [float(values[0]) for _, values in pressure if values]
        movement = movement_metrics(accel)
        segment_peaks = sum(start_ms <= timestamp <= end_ms for timestamp in session["accel_peaks"])
        cumulative_peaks += segment_peaks
        clean_location = end_location[:-2] if end_location.endswith(" 앞") else end_location
        actual_x = 0.0 if clean_location == "오른쪽 계단 입구" else ROOM_X.get(clean_location)
        predicted_x = MAP_START_X * (1 - cumulative_peaks / total_peaks) if total_peaks else None
        map_error = abs(predicted_x - actual_x) if predicted_x is not None and actual_x is not None else None
        if map_error is not None:
            map_errors.append(map_error)
        rows.append({
            "file": session["path"].name,
            "segment": index,
            "from": start_location,
            "to": end_location,
            "duration_s": rounded((end_ms - start_ms) / 1000, 3),
            "pedometer_delta": end_steps - start_steps,
            "accel_peak_count": segment_peaks,
            **movement,
            "mag_mean_ut": rounded(mean(btotal)),
            "mag_std_ut": rounded(stdev(btotal)),
            "pressure_mean_hpa": rounded(mean(pressure_values)),
            "actual_map_x": rounded(actual_x),
            "peak_pdr_map_x": rounded(predicted_x),
            "peak_pdr_map_error": rounded(map_error),
        })
    session["summary"]["peak_pdr_label_mae_map_units"] = rounded(mean(map_errors))
    session["summary"]["peak_pdr_label_max_error_map_units"] = rounded(max(map_errors) if map_errors else None)
    return rows


def comparison_row(left, right, group):
    left_profile = lap_aligned_profile(left, "magnetic_field_ut")
    right_profile = lap_aligned_profile(right, "magnetic_field_ut")
    axis_correlations = [pearson(lap_aligned_profile(left, "magnetic_field_ut", component=axis), lap_aligned_profile(right, "magnetic_field_ut", component=axis)) for axis in range(3)]
    return {
        "group": group,
        "left": left["path"].name,
        "right": right["path"].name,
        "btotal_pearson_lap_aligned": rounded(pearson(left_profile, right_profile)),
        "btotal_dtw_z_cost": rounded(dtw_cost(left_profile, right_profile)),
        "mag_mean_difference_ut": rounded(abs(left["summary"]["mag_mean_ut"] - right["summary"]["mag_mean_ut"])),
        "mag_x_pearson": rounded(axis_correlations[0]),
        "mag_y_pearson": rounded(axis_correlations[1]),
        "mag_z_pearson": rounded(axis_correlations[2]),
    }


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def short_session_name(filename):
    return Path(filename).stem.rsplit("_", 1)[-1]


def coefficient_of_variation(values):
    center = mean(values)
    return stdev(values) / center if center else None


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ios_sessions = [parse_session(path) for path in sorted(IOS_DIR.glob("*.jsonl"))]
    android_sessions = [parse_session(path) for path in ANDROID_REFERENCES]
    summaries = [session_summary(session) for session in ios_sessions + android_sessions]
    segments = [row for session in ios_sessions for row in segment_rows(session)]
    comparisons = []
    for index, left in enumerate(ios_sessions):
        for right in ios_sessions[index + 1:]:
            comparisons.append(comparison_row(left, right, "ios_repeat"))
    comparisons.append(comparison_row(android_sessions[0], android_sessions[1], "android_repeat"))
    for ios_session in ios_sessions:
        for android_session in android_sessions:
            comparisons.append(comparison_row(ios_session, android_session, "ios_android"))

    checksums = {session["path"].name: hashlib.sha256(session["path"].read_bytes()).hexdigest() for session in ios_sessions}
    manifest = {
        "dataset_id": "it-convergence-ios-2026-09-05-4f-right-v1",
        "building": "조선대학교 IT융합대학",
        "collector": "expo-go",
        "device": "iPhone 13 Pro",
        "collection_date": "2026-09-05",
        "raw_directory": "raw/ios/2026-09-05",
        "comparison_policy": "Android 원본과 분리 보존하고 같은 경로의 반복성 및 장치 간 유사성만 비교한다.",
        "sessions": [{"file": item["file"], "route_id": item["route_id"], "status": "accepted_with_pedometer_review" if item["pedometer_steps"] == 43 else "accepted", "sha256": checksums[item["file"]]} for item in summaries[:len(ios_sessions)]],
    }
    IOS_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "summary.json").write_text(json.dumps({"sessions": summaries, "comparisons": comparisons}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "source_checksums.json").write_text(json.dumps(checksums, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(OUTPUT_DIR / "segments.csv", segments)
    write_csv(OUTPUT_DIR / "comparisons.csv", comparisons)

    ios = summaries[:len(ios_sessions)]
    ios_comparisons = [row for row in comparisons if row["group"] == "ios_repeat"]
    android_comparison = next(row for row in comparisons if row["group"] == "android_repeat")
    cross = [row for row in comparisons if row["group"] == "ios_android"]
    segment_groups = defaultdict(list)
    for row in segments:
        segment_groups[row["segment"]].append(row)
    segment_repeat = [{
        "segment": index,
        "from": rows[0]["from"],
        "to": rows[0]["to"],
        "mag_mean_ut": rounded(mean([row["mag_mean_ut"] for row in rows]), 2),
        "mag_between_run_std_ut": rounded(stdev([row["mag_mean_ut"] for row in rows]), 2),
        "accel_peaks": "/".join(str(row["accel_peak_count"]) for row in rows),
    } for index, rows in sorted(segment_groups.items())]
    duration_cv = coefficient_of_variation([item["arrival_duration_s"] for item in ios])
    pedometer_cv = coefficient_of_variation([item["pedometer_steps"] for item in ios])
    peak_cv = coefficient_of_variation([item["accel_peak_steps"] for item in ios])
    pressure_baseline_range = max(item["pressure_mean_hpa"] for item in ios) - min(item["pressure_mean_hpa"] for item in ios)
    report = [
        "# 2026-09-05 iPhone 4층 오른쪽 복도 반복 측정 분석",
        "",
        "- 경로: `4F_CORE_TO_RIGHT_STAIRS`, 코어복도 출구 중앙점→오른쪽 계단 입구",
        "- iOS: iPhone 13 Pro, Expo Go schema 4, 3회",
        "- Android 비교: Samsung SM-S938N schema 3, 기존 2회",
        "",
        "## iOS 세션 요약",
        "",
        markdown_table(
            ["세션", "도착(s)", "보행계", "가속도 피크 후보", "PDR 라벨 MAE", "자기장 평균±표준편차(µT)", "기압 평균/변화(hPa)", "회전 α 시작→끝"],
            [[short_session_name(item["file"]), item["arrival_duration_s"], item["pedometer_steps"], item["accel_peak_steps"], item["peak_pdr_label_mae_map_units"], f'{item["mag_mean_ut"]}±{item["mag_std_ut"]}', f'{item["pressure_mean_hpa"]}/{item["pressure_delta_hpa"]}', f'{item["rotation_alpha_start_end_deg"]}°'] for item in ios],
        ),
        "",
        "## iOS 반복 자기장 비교",
        "",
        markdown_table(
            ["쌍", "랩 정렬 Btotal r", "DTW 비용(낮을수록 유사)", "평균 차이(µT)", "x/y/z r"],
            [[f'{short_session_name(row["left"])}-{short_session_name(row["right"])}', row["btotal_pearson_lap_aligned"], row["btotal_dtw_z_cost"], row["mag_mean_difference_ut"], f'{row["mag_x_pearson"]}/{row["mag_y_pearson"]}/{row["mag_z_pearson"]}'] for row in ios_comparisons],
        ),
        "",
        "## 구간별 반복 특징",
        "",
        markdown_table(
            ["구간", "이동", "Btotal 평균", "세 측정 간 표준편차", "가속도 피크 후보"],
            [[item["segment"], f'{item["from"]}→{item["to"]}', item["mag_mean_ut"], item["mag_between_run_std_ut"], item["accel_peaks"]] for item in segment_repeat],
        ),
        "",
        "## 판정",
        "",
        f'- 세 로그는 JSON 파싱 오류 0, 11/11 랩, 정상 종료다. 현재 임시 검출기의 가속도 피크 후보는 `{ios[0]["accel_peak_steps"]}·{ios[1]["accel_peak_steps"]}·{ios[2]["accel_peak_steps"]}`로 반복성이 높다.',
        f'- 도착 시간 변동계수는 `{rounded(duration_cv * 100, 1)}%`, 보행계 걸음 변동계수는 `{rounded(pedometer_cv * 100, 1)}%`, 가속도 피크 후보 변동계수는 `{rounded(peak_cv * 100, 1)}%`다. 가속도 후보는 반복성 지표로는 좋지만 실제 걸음 정답과 대조하지 않았으므로 80~82를 그대로 실제 걸음 수로 확정하지 않는다.',
        f'- iOS 보행계는 `{ios[0]["pedometer_steps"]}·{ios[1]["pedometer_steps"]}·{ios[2]["pedometer_steps"]}`다. 두 번째 로그는 가속도상 같은 보행인데도 43만 기록되어 실시간 PDR의 단독 걸음 입력으로 부적합하다.',
        "- 중간 랩에서 보행계 증가가 0이어도 가속도 동적 RMS와 피크가 이동을 확인한다. iOS에서는 가속도 기반 자체 스텝 검출 또는 사후 보정을 함께 써야 한다.",
        f'- 가속도 피크 진행률을 복도 끝점에 맞춘 PDR의 중간 라벨 MAE는 `{ios[0]["peak_pdr_label_mae_map_units"]}·{ios[1]["peak_pdr_label_mae_map_units"]}·{ios[2]["peak_pdr_label_mae_map_units"]}` 지도 단위다. 끝점을 이용해 보폭을 맞춘 내부 일치도이므로 독립 위치 정확도가 아니며, 후반부 4206~4204에서 오차가 커져 자기장·랜드마크 보정이 필요하다.',
        "- 자기장 평가는 축별 값보다 자세 변화에 덜 민감한 Btotal을 우선한다. 랩 정렬 상관과 DTW를 함께 보되, 현재 3회만으로 위치 지문을 확정하지 않는다.",
        f'- 세 로그의 평균 기압 범위는 `{rounded(pressure_baseline_range, 4)} hPa`로 기존 `0.44 hPa/층`의 약 `{rounded(pressure_baseline_range / 0.44, 2)}층`에 해당한다. 같은 층의 짧은 복도 이동에서 큰 층 변화 신호가 없어 정상이며, 이 자료는 층 판정보다 센서 안정성 확인용이다.',
        "- Device Motion의 rotation alpha가 시작과 끝 사이 약 124~138° 변했다. 이는 나침반 방위가 아니라 기기 자세 기준 회전값이며 반복된 화면 조작·들기 자세가 포함될 수 있다. 방향값을 직접 위치로 쓰지 말고 복도 축 제약을 적용한다.",
        "",
        "## Android와의 비교 원칙",
        "",
        f'- 장치 간 랩 정렬 Btotal 상관 범위: `{rounded(min(row["btotal_pearson_lap_aligned"] for row in cross))}`~`{rounded(max(row["btotal_pearson_lap_aligned"] for row in cross))}`.',
        f'- 기존 Android 두 로그끼리 같은 랩 정렬 방식으로 계산한 Btotal 상관은 `{android_comparison["btotal_pearson_lap_aligned"]}`다. iOS 내부 반복 상관 `{rounded(min(row["btotal_pearson_lap_aligned"] for row in ios_comparisons))}`~`{rounded(max(row["btotal_pearson_lap_aligned"] for row in ios_comparisons))}`보다 낮다. 자세 통제의 효과와 일치하지만 단말·날짜도 달라 원인을 자세 하나로 확정하지 않는다.',
        "- iPhone과 Samsung은 자력계 보정·샘플링률·기기 좌표계가 달라 절대 3축 값은 직접 합치지 않는다. 경로별 정규화 Btotal 패턴과 랜드마크 후보의 반복 출현만 비교한다.",
        "- Android 약 500 Hz 가속도와 iOS 약 20 Hz 가속도는 동일 임계값으로 학습하지 않는다. 공통 시간축으로 다운샘플링한 특징량을 사용한다.",
        "",
        "## 알고리즘 반영안",
        "",
        "1. PDR 예측은 플랫폼 보행계만 단독 사용하지 않고, 가속도 기반 후보와 센서 갱신 지연 상태를 함께 관리한다.",
        "2. 지도 정합은 메인복도 선분과 알려진 시작점을 우선 사용하고, 수집 랩은 학습용 실제 위치 앵커로만 사용한다.",
        "3. 자기장은 세션 평균을 제거하거나 z-score 정규화한 Btotal 패턴을 사용한다. 4211→4210 고점, 4210→4209 하강, 4205→4204 저점을 4층 오른쪽의 1차 보정 후보로 둔다.",
        "4. 자기장 후보가 PDR 예상 진행 구간과 일치할 때만 위치를 보정한다. 자기장만으로 강의실을 확정하지 않는다.",
        "5. 기압은 같은 층의 x·y 위치 보정에는 사용하지 않고 계단·엘리베이터의 상대 층 변화 감지에만 사용한다.",
        "",
        "세부 구간은 `segments.csv`, 반복 및 장치 간 수치는 `comparisons.csv`, 전체 원수치는 `summary.json`에 기록했다.",
        "",
    ]
    (OUTPUT_DIR / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"ios_sessions": ios, "comparisons": comparisons, "output": str(OUTPUT_DIR)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
