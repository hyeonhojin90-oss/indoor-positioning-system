#!/usr/bin/env python3
"""Analyze Android indoor-positioning JSONL logs without third-party packages."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "indoor" / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
MAP_DIR = ROOT / "indoor" / "web" / "data" / "maps"
OUTPUT_DIR = DATA_DIR / "analysis"
FIXED_STRIDE_M = 0.75


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


def round_or_none(value, digits=4):
    return None if value is None else round(value, digits)


def vector_norm(values):
    return math.sqrt(sum(float(v) ** 2 for v in values[:3]))


def yaw_degrees(rotation_vector):
    if len(rotation_vector) < 3:
        return None
    x, y, z = (float(v) for v in rotation_vector[:3])
    if len(rotation_vector) >= 4:
        w = float(rotation_vector[3])
    else:
        w = math.sqrt(max(0.0, 1.0 - x * x - y * y - z * z))
    yaw = math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))
    return (yaw + 360.0) % 360.0


def angle_delta(angle, reference):
    return (angle - reference + 180.0) % 360.0 - 180.0


def circular_mean(values):
    if not values:
        return None
    sine = mean([math.sin(math.radians(v)) for v in values])
    cosine = mean([math.cos(math.radians(v)) for v in values])
    return (math.degrees(math.atan2(sine, cosine)) + 360.0) % 360.0


def strip_location(location):
    return location[:-2] if location.endswith(" 앞") else location


def load_floor_map(floor):
    path = MAP_DIR / f"floor-{int(floor):02d}.json"
    with path.open(encoding="utf-8") as handle:
        floor_map = json.load(handle)
    if "layout_dimensions" not in floor_map:
        with (MAP_DIR / "floor-04.json").open(encoding="utf-8") as handle:
            base = json.load(handle)
        floor_map["layout_dimensions"] = base["layout_dimensions"]
        floor_map.setdefault("corridors", base.get("corridors", []))
        floor_map.setdefault("facilities", base.get("facilities", []))
    return floor_map


def map_reference(floor_map, route_id):
    rooms = {str(room["id"]): float(room["front_x"]) for room in floor_map.get("rooms", []) if "front_x" in room}
    layout = floor_map["layout_dimensions"]
    start_x = float(floor_map.get("routing", {}).get("hub_junction", {}).get(
        "x", float(layout["left_corridor_length"]) + float(layout["hub_outer_width"]) / 2.0
    ))
    if "CORE_TO_LEFT_STAIRS" in route_id:
        return {"available": True, "start_x": start_x, "end_x": 135.407, "direction": 1.0, "rooms": rooms}
    if "CORE_TO_RIGHT_STAIRS" in route_id:
        return {"available": True, "start_x": start_x, "end_x": 0.0, "direction": -1.0, "rooms": rooms}
    return {"available": False, "rooms": rooms}


def parse_session(path):
    start = None
    end = None
    labels = []
    sensors = defaultdict(list)
    parse_errors = 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
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
    if start is None:
        raise ValueError(f"session_start missing: {path}")
    return start, end, labels, sensors, parse_errors


def samples_between(samples, start_ms, end_ms):
    return [values for timestamp, values in samples if start_ms <= timestamp <= end_ms]


def latest_value(samples, timestamp):
    if not samples:
        return None
    times = [item[0] for item in samples]
    index = bisect_right(times, timestamp) - 1
    return samples[index][1] if index >= 0 else None


def movement_metrics(acceleration_values):
    magnitudes = [vector_norm(values) for values in acceleration_values if len(values) >= 3]
    if not magnitudes:
        return {"accel_samples": 0, "dynamic_rms": None, "active_ratio": None, "motion_evidence": "missing"}
    baseline = statistics.median(magnitudes)
    dynamic = [value - baseline for value in magnitudes]
    rms = math.sqrt(mean([value * value for value in dynamic]))
    active_ratio = sum(abs(value) >= 0.7 for value in dynamic) / len(dynamic)
    evidence = "moving" if rms >= 0.8 and active_ratio >= 0.12 else "weak_or_stationary"
    return {
        "accel_samples": len(magnitudes),
        "dynamic_rms": round_or_none(rms),
        "active_ratio": round_or_none(active_ratio),
        "motion_evidence": evidence,
    }


def detect_acceleration_steps(acceleration_samples):
    """Return approximate step timestamps from acceleration magnitude peaks.

    This supplies event timing when Android TYPE_STEP_COUNTER batches updates. It
    is a baseline detector, not a replacement for later user-specific tuning.
    """
    if len(acceleration_samples) < 3:
        return []
    gravity = vector_norm(acceleration_samples[0][1])
    candidates = []
    previous_dynamic = 0.0
    rising = False
    peak_value = 0.0
    peak_time = None
    last_time = acceleration_samples[0][0]
    for timestamp, values in acceleration_samples:
        magnitude = vector_norm(values)
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
                if not candidates or peak_time - candidates[-1][0] >= 280:
                    candidates.append((peak_time, peak_value))
                elif peak_value >= 1.8:
                    candidates[-1] = (peak_time, peak_value)
            rising = False
            peak_value = dynamic
            peak_time = timestamp
        previous_dynamic = dynamic
    return candidates


def sensor_window_metrics(sensors, start_ms, end_ms):
    accel = samples_between(sensors.get("accelerometer_mps2", []), start_ms, end_ms)
    magnetic = samples_between(sensors.get("magnetic_field_ut", []), start_ms, end_ms)
    pressure = samples_between(sensors.get("pressure_hpa", []), start_ms, end_ms)
    rotation = samples_between(sensors.get("rotation_vector", []), start_ms, end_ms)
    motion = movement_metrics(accel)
    btotal = [vector_norm(values) for values in magnetic if len(values) >= 3]
    pressures = [float(values[0]) for values in pressure if values]
    headings = [heading for values in rotation if (heading := yaw_degrees(values)) is not None]
    return {
        **motion,
        "mag_samples": len(btotal),
        "mag_mean_ut": round_or_none(mean(btotal)),
        "mag_std_ut": round_or_none(stdev(btotal)),
        "mag_min_ut": round_or_none(min(btotal) if btotal else None),
        "mag_max_ut": round_or_none(max(btotal) if btotal else None),
        "pressure_samples": len(pressures),
        "pressure_mean_hpa": round_or_none(mean(pressures)),
        "pressure_delta_hpa": round_or_none((pressures[-1] - pressures[0]) if len(pressures) >= 2 else None),
        "heading_samples": len(headings),
        "heading_mean_deg": round_or_none(circular_mean(headings), 2),
    }


def build_pdr(sensors, start, labels, reference):
    step_samples = sensors.get("step_counter", [])
    rotation_samples = sensors.get("rotation_vector", [])
    start_count = start.get("start_step_counter")
    hardware_increments = []
    previous = float(start_count) if start_count is not None else 0.0
    for timestamp, values in step_samples if start_count is not None else []:
        if not values:
            continue
        current = float(values[0])
        delta = max(0, int(round(current - previous)))
        if delta:
            for _ in range(delta):
                hardware_increments.append(timestamp)
        previous = max(previous, current)
    acceleration_candidates = detect_acceleration_steps(sensors.get("accelerometer_mps2", []))
    if hardware_increments and len(acceleration_candidates) >= len(hardware_increments):
        strongest = sorted(acceleration_candidates, key=lambda item: item[1], reverse=True)[:len(hardware_increments)]
        acceleration_increments = sorted(timestamp for timestamp, _ in strongest)
    else:
        acceleration_increments = [timestamp for timestamp, _ in acceleration_candidates]
    increments = acceleration_increments or hardware_increments
    if not increments:
        return [], {"available": False, "reason": "no detected steps"}

    initial_headings = []
    first_step_ms = increments[0]
    for timestamp, values in rotation_samples:
        if first_step_ms - 1500 <= timestamp <= first_step_ms + 4000:
            heading = yaw_degrees(values)
            if heading is not None:
                initial_headings.append(heading)
    heading_zero = circular_mean(initial_headings)
    if heading_zero is None:
        heading_zero = 0.0

    map_distance = abs(reference.get("end_x", 0.0) - reference.get("start_x", 0.0)) if reference["available"] else None
    calibrated_stride = map_distance / len(increments) if map_distance is not None and increments else FIXED_STRIDE_M
    points = []
    relative_headings = []
    fixed_x = calibrated_x = reference.get("start_x", 0.0)
    fixed_y = calibrated_y = 0.0
    direction = reference.get("direction", 1.0)
    for step_index, timestamp in enumerate(increments, 1):
        rotation = latest_value(rotation_samples, timestamp)
        heading = yaw_degrees(rotation) if rotation else heading_zero
        relative = math.radians(angle_delta(heading, heading_zero))
        relative_headings.append(abs(math.degrees(relative)))
        fixed_x += direction * FIXED_STRIDE_M * math.cos(relative)
        fixed_y += FIXED_STRIDE_M * math.sin(relative)
        calibrated_x += direction * calibrated_stride * math.cos(relative)
        calibrated_y += calibrated_stride * math.sin(relative)
        points.append({
            "wall_time_ms": timestamp,
            "step_index": step_index,
            "heading_deg": round(heading, 3),
            "relative_heading_deg": round(math.degrees(relative), 3),
            "fixed_x": fixed_x,
            "fixed_y": fixed_y,
            "calibrated_x": calibrated_x,
            "calibrated_y": calibrated_y,
            "matched_x": min(135.407, max(0.0, reference.get("start_x", 0.0) + direction * calibrated_stride * step_index)) if reference["available"] else calibrated_x,
            "matched_y": 0.0,
        })

    label_errors = []
    if reference["available"]:
        point_times = [point["wall_time_ms"] for point in points]
        for label in labels:
            room_id = strip_location(label["label"]["location"])
            expected_x = reference["rooms"].get(room_id)
            if expected_x is None or not point_times:
                continue
            index = max(0, bisect_right(point_times, int(label["wall_time_ms"])) - 1)
            estimated_x = points[index]["matched_x"]
            label_errors.append({"location": room_id, "expected_x": expected_x, "estimated_x": estimated_x, "error_m": abs(estimated_x - expected_x)})

    final_fixed_error = None
    final_calibrated_error = None
    cross_track = []
    if reference["available"] and points:
        final_fixed_error = math.hypot(points[-1]["fixed_x"] - reference["end_x"], points[-1]["fixed_y"])
        final_calibrated_error = math.hypot(points[-1]["calibrated_x"] - reference["end_x"], points[-1]["calibrated_y"])
        cross_track = [abs(point["calibrated_y"]) for point in points]
    metrics = {
        "available": True,
        "steps": len(increments),
        "step_source": "android_count_with_accelerometer_timing" if hardware_increments and acceleration_increments else ("accelerometer_peak" if acceleration_increments else "android_step_counter"),
        "accelerometer_detected_steps": len(acceleration_increments),
        "accelerometer_candidate_peaks": len(acceleration_candidates),
        "android_step_counter_increments": len(hardware_increments),
        "initial_heading_deg": round_or_none(heading_zero, 2),
        "relative_heading_abs_p95_deg": round_or_none(percentile(relative_headings, 0.95), 2),
        "fixed_stride_m": FIXED_STRIDE_M,
        "calibrated_stride_m": round_or_none(calibrated_stride),
        "map_reference_available": reference["available"],
        "fixed_stride_endpoint_error_m": round_or_none(final_fixed_error),
        "calibrated_endpoint_error_m": round_or_none(final_calibrated_error),
        "matched_endpoint_error_m": round_or_none(abs(points[-1]["matched_x"] - reference["end_x"]) if reference["available"] and points else None),
        "cross_track_mean_m": round_or_none(mean(cross_track)),
        "cross_track_p95_m": round_or_none(percentile(cross_track, 0.95)),
        "label_error_mean_m": round_or_none(mean([item["error_m"] for item in label_errors])),
        "label_error_max_m": round_or_none(max([item["error_m"] for item in label_errors]) if label_errors else None),
        "label_errors": [{**item, "expected_x": round(item["expected_x"], 3), "estimated_x": round(item["estimated_x"], 3), "error_m": round(item["error_m"], 3)} for item in label_errors],
        "calibration_warning": "지도 끝점과 복도 진행 방향을 사용한 보폭·스냅 결과는 독립 정확도 검증값이 아님" if reference["available"] else None,
    }
    return points, metrics


def session_suffix(filename):
    return Path(filename).stem.rsplit("_", 1)[-1].lower()


def write_trajectory(route_id, points, source_file):
    if not points:
        return None
    filename = f"trajectory_{route_id.lower()}_{session_suffix(source_file)}.csv"
    with (OUTPUT_DIR / filename).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(points[0]))
        writer.writeheader()
        writer.writerows(points)
    return filename


def write_sensor_profile(route_id, sensors, start_ms, end_ms, source_file, bins=100):
    duration = max(1, end_ms - start_ms)
    magnetic_bins = [[] for _ in range(bins)]
    pressure_bins = [[] for _ in range(bins)]
    heading_bins = [[] for _ in range(bins)]
    for timestamp, values in sensors.get("magnetic_field_ut", []):
        index = min(bins - 1, max(0, int((timestamp - start_ms) * bins / duration)))
        magnetic_bins[index].append(vector_norm(values))
    for timestamp, values in sensors.get("pressure_hpa", []):
        if values:
            index = min(bins - 1, max(0, int((timestamp - start_ms) * bins / duration)))
            pressure_bins[index].append(float(values[0]))
    for timestamp, values in sensors.get("rotation_vector", []):
        heading = yaw_degrees(values)
        if heading is not None:
            index = min(bins - 1, max(0, int((timestamp - start_ms) * bins / duration)))
            heading_bins[index].append(heading)
    filename = f"profile_{route_id.lower()}_{session_suffix(source_file)}.csv"
    with (OUTPUT_DIR / filename).open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = ["progress", "time_s", "magnetic_total_mean_ut", "magnetic_total_std_ut", "pressure_mean_hpa", "heading_mean_deg"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(bins):
            writer.writerow({
                "progress": round((index + 0.5) / bins, 4),
                "time_s": round(duration / 1000.0 * (index + 0.5) / bins, 3),
                "magnetic_total_mean_ut": round_or_none(mean(magnetic_bins[index])),
                "magnetic_total_std_ut": round_or_none(stdev(magnetic_bins[index])),
                "pressure_mean_hpa": round_or_none(mean(pressure_bins[index])),
                "heading_mean_deg": round_or_none(circular_mean(heading_bins[index]), 2),
            })
    return filename


def analyze_session(entry, raw_dir):
    path = raw_dir / entry["file"]
    start, end, labels, sensors, parse_errors = parse_session(path)
    route_id = start["label"]["route_id"]
    floor = start["label"]["floor"]
    floor_map = load_floor_map(floor)
    reference = map_reference(floor_map, route_id)
    points, pdr = build_pdr(sensors, start, labels, reference)
    trajectory_file = write_trajectory(route_id, points, entry["file"])

    boundaries = [(int(start["wall_time_ms"]), start["label"]["location"], 0, 0)]
    for label in labels:
        boundaries.append((int(label["wall_time_ms"]), label["label"]["location"], label.get("steps_since_start"), label["label"].get("lap_index")))
    session_end_ms = int(end["wall_time_ms"]) if end else boundaries[-1][0]
    profile_file = write_sensor_profile(route_id, sensors, int(start["wall_time_ms"]), session_end_ms, entry["file"])
    segments = []
    for index in range(1, len(boundaries)):
        start_ms, from_location, previous_steps, _ = boundaries[index - 1]
        end_ms, to_location, current_steps, lap_index = boundaries[index]
        metrics = sensor_window_metrics(sensors, start_ms, end_ms)
        segments.append({
            "file": entry["file"],
            "route_id": route_id,
            "floor": floor,
            "lap_index": lap_index,
            "from": from_location,
            "to": to_location,
            "duration_s": round((end_ms - start_ms) / 1000.0, 3),
            "step_delta": None if previous_steps is None or current_steps is None else current_steps - previous_steps,
            **metrics,
        })

    whole = sensor_window_metrics(sensors, int(start["wall_time_ms"]), session_end_ms)
    pressure_values = [float(values[0]) for _, values in sensors.get("pressure_hpa", []) if values]
    pressure_altitude_change = None
    if len(pressure_values) >= 2:
        pressure_altitude_change = -8.3 * (pressure_values[-1] - pressure_values[0])
    result = {
        "file": entry["file"],
        "route_id": route_id,
        "floor": floor,
        "status": entry["status"],
        "status_note": entry.get("note"),
        "duration_s": round((session_end_ms - int(start["wall_time_ms"])) / 1000.0, 3),
        "labels_recorded": len(labels),
        "labels_expected": start["label"].get("lap_total"),
        "parse_errors": parse_errors,
        "sensor_counts": {name: len(values) for name, values in sorted(sensors.items())},
        "steps_since_start": labels[-1].get("steps_since_start") if labels else 0,
        "whole_session": whole,
        "pressure_altitude_change_m": round_or_none(pressure_altitude_change),
        "pdr": pdr,
        "trajectory_file": trajectory_file,
        "profile_file": profile_file,
        "segments": segments,
    }
    return result


def write_segments(results):
    rows = [segment for result in results for segment in result["segments"]]
    if not rows:
        return
    with (OUTPUT_DIR / "segments.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pearson(values_a, values_b):
    pairs = [(a, b) for a, b in zip(values_a, values_b) if a is not None and b is not None]
    if len(pairs) < 3:
        return None
    a_values = [pair[0] for pair in pairs]
    b_values = [pair[1] for pair in pairs]
    a_mean = mean(a_values)
    b_mean = mean(b_values)
    numerator = sum((a - a_mean) * (b - b_mean) for a, b in pairs)
    denominator = math.sqrt(sum((a - a_mean) ** 2 for a in a_values) * sum((b - b_mean) ** 2 for b in b_values))
    return numerator / denominator if denominator else None


def read_profile_values(filename, field):
    with (OUTPUT_DIR / filename).open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return [float(row[field]) if row[field] else None for row in rows]


def repeatability_metrics(results):
    grouped = defaultdict(list)
    for result in results:
        grouped[result["route_id"]].append(result)
    comparisons = []
    for route_id, sessions in grouped.items():
        for first_index in range(len(sessions)):
            for second_index in range(first_index + 1, len(sessions)):
                first = sessions[first_index]
                second = sessions[second_index]
                first_mag = read_profile_values(first["profile_file"], "magnetic_total_mean_ut")
                second_mag = read_profile_values(second["profile_file"], "magnetic_total_mean_ut")
                step_a = first["steps_since_start"] or 0
                step_b = second["steps_since_start"] or 0
                comparisons.append({
                    "route_id": route_id,
                    "file_a": first["file"],
                    "file_b": second["file"],
                    "steps_a": step_a,
                    "steps_b": step_b,
                    "step_difference": abs(step_a - step_b),
                    "duration_a_s": first["duration_s"],
                    "duration_b_s": second["duration_s"],
                    "magnetic_profile_pearson": round_or_none(pearson(first_mag, second_mag)),
                    "interpretation": "시간 정규화 자기장 패턴의 선형 유사도이며 위치 정합 정확도 자체는 아님",
                })
    return comparisons


def build_markdown(manifest, results, repeatability):
    zero_step_moving = []
    for result in results:
        for segment in result["segments"]:
            if segment["step_delta"] == 0 and segment["motion_evidence"] == "moving":
                zero_step_moving.append((result["route_id"], segment))
    lines = [
        "# 2026-09-01 실내 보행 로그 1차 오프라인 분석",
        "",
        f"- 데이터셋: `{manifest['dataset_id']}`",
        f"- 단말: `{manifest['device']}`",
        f"- 보존 원본: {len(manifest['sessions'])}개",
        f"- 주 분석 세션: {len(results)}개",
        "- 주의: 각 경로가 대부분 1회뿐이므로 자기장 지문의 반복 재현성과 위치 정확도를 확정할 수 없다.",
        "",
        "## 세션 요약",
        "",
        "| 경로 | 상태 | 시간(s) | 걸음 | 랩 | 자기장 평균/표준편차(µT) | 방향편차 p95(°) | 고정 보폭 끝점 오차(m) | 지도 스냅 라벨 평균오차(m) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        whole = result["whole_session"]
        pdr = result["pdr"]
        mag = f"{whole['mag_mean_ut']}/{whole['mag_std_ut']}" if whole["mag_mean_ut"] is not None else "-"
        laps = f"{result['labels_recorded']}/{result['labels_expected']}"
        lines.append(
            f"| {result['route_id']} | {result['status']} | {result['duration_s']} | {result['steps_since_start']} | {laps} | {mag} | {pdr.get('relative_heading_abs_p95_deg')} | {pdr.get('fixed_stride_endpoint_error_m')} | {pdr.get('label_error_mean_m')} |"
        )
    lines += [
        "",
        "## 걸음 수 0 구간의 가속도 판정",
        "",
        "Android 누적 걸음 센서가 0으로 유지돼도 가속도 동적 RMS와 활성 비율이 충분하면 실제 이동이 있었던 것으로 본다. 이 판정은 재측정 필요 여부를 가르는 품질 검사이며, 정확한 걸음 수 복원값은 아니다.",
        "",
    ]
    if zero_step_moving:
        for route_id, segment in zero_step_moving:
            lines.append(
                f"- `{route_id}`: {segment['from']} → {segment['to']}, {segment['duration_s']} s, 동적 RMS {segment['dynamic_rms']}, 활성 비율 {segment['active_ratio']} — 이동 증거 있음"
            )
    else:
        lines.append("- 걸음 수 0이면서 가속도상 이동으로 판정된 구간 없음")
    lines += ["", "## 반복 경로 비교", ""]
    if repeatability:
        for comparison in repeatability:
            lines.append(
                f"- `{comparison['route_id']}`: {comparison['steps_a']}걸음/{comparison['steps_b']}걸음, "
                f"{comparison['duration_a_s']}초/{comparison['duration_b_s']}초, "
                f"시간 정규화 자기장 패턴 Pearson r=`{comparison['magnetic_profile_pearson']}`"
            )
    else:
        lines.append("- 같은 경로 반복 로그 없음")
    lines += [
        "",
        "## 해석 한계",
        "",
        "- 복도 경로의 지도 보정 보폭은 실제 끝점 좌표를 사용해 계산했으므로 독립 성능 지표가 아니다.",
        "- 특수 경로는 지도에 상세 중심선·랜드마크 좌표가 없어 PDR 궤적만 만들고 지도 오차는 계산하지 않았다.",
        "- 자기장 반복 비교는 시간 진행률을 100구간으로 정규화한 1차 비교이며, 보행 거리 기준 동적 시간 왜곡(DTW)은 아직 적용하지 않았다.",
        "- 휴대폰 자세와 진행 방향이 완전히 고정되지 않아 축별 자기장보다 우선 `Btotal`을 사용했다.",
        "",
        "세부 수치는 `summary.json`, `segments.csv`, 경로별 `trajectory_*.csv`와 자기장·기압·방향 100구간 패턴 `profile_*.csv`에 있다.",
    ]
    return "\n".join(lines) + "\n"


def main():
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    raw_dir = DATA_DIR / manifest["raw_directory"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for pattern in ("trajectory_*.csv", "profile_*.csv"):
        for stale_path in OUTPUT_DIR.glob(pattern):
            stale_path.unlink()
    analysis_entries = [entry for entry in manifest["sessions"] if entry.get("include_in_analysis", True)]
    results = [analyze_session(entry, raw_dir) for entry in analysis_entries]
    repeatability = repeatability_metrics(results)
    checksums = {}
    for entry in manifest["sessions"]:
        path = raw_dir / entry["file"]
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        checksums[entry["file"]] = {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}
    write_segments(results)
    with (OUTPUT_DIR / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump({"dataset": manifest["dataset_id"], "sessions": results, "repeatability": repeatability}, handle, ensure_ascii=False, indent=2)
    with (OUTPUT_DIR / "source_checksums.json").open("w", encoding="utf-8") as handle:
        json.dump(checksums, handle, ensure_ascii=False, indent=2)
    with (OUTPUT_DIR / "REPORT.md").open("w", encoding="utf-8") as handle:
        handle.write(build_markdown(manifest, results, repeatability))
    print(f"Analyzed {len(results)} sessions -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
