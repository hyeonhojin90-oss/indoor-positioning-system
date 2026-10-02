#!/usr/bin/env python3
"""Build platform-specific stationary node fingerprints from trusted labeled logs."""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "indoor" / "data"
MAPS = ROOT / "indoor" / "web" / "data" / "maps"
OUTPUT = ROOT / "app" / "expo-sensor-collector" / "referenceFingerprints.json"
WINDOW_MS = 900


def median(values):
    return statistics.median(values) if values else None


def stdev(values):
    return statistics.pstdev(values) if len(values) > 1 else (0.0 if values else None)


def norm(values):
    return math.sqrt(sum(float(value) ** 2 for value in values[:3]))


def yaw_degrees(values):
    if len(values) < 3:
        return None
    x, y, z = (float(value) for value in values[:3])
    w = float(values[3]) if len(values) >= 4 else math.sqrt(max(0.0, 1.0 - x * x - y * y - z * z))
    return (math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))) + 360.0) % 360.0


def circular_mean(values):
    if not values:
        return None
    sine = statistics.fmean(math.sin(math.radians(value)) for value in values)
    cosine = statistics.fmean(math.cos(math.radians(value)) for value in values)
    return (math.degrees(math.atan2(sine, cosine)) + 360.0) % 360.0


def parse(path):
    start = None
    labels = []
    sensors = defaultdict(list)
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("kind") == "session_start":
                start = row
            elif row.get("kind") == "label":
                labels.append(row)
            elif row.get("kind") == "sample":
                sensors[row.get("sensor")].append((int(row["wall_time_ms"]), row.get("values", [])))
    return start, labels, sensors


def map_nodes(floor):
    floor_map = json.loads((MAPS / f"floor-{floor:02d}.json").read_text(encoding="utf-8"))
    base = json.loads((MAPS / "floor-04.json").read_text(encoding="utf-8"))
    layout = floor_map.get("layout_dimensions", base["layout_dimensions"])
    core_x = floor_map.get("routing", {}).get("hub_junction", {}).get(
        "x", float(layout["left_corridor_length"]) + float(layout["hub_outer_width"]) / 2.0
    )
    nodes = {
        "CORE": {"label": "코어복도 출구 중앙점", "x": float(core_x)},
        "RIGHT_STAIRS": {"label": "오른쪽 계단 입구", "x": 0.0},
        "LEFT_STAIRS": {"label": "왼쪽 계단 입구", "x": 135.407},
    }
    for room in floor_map.get("rooms", []):
        if room.get("provisional") or "front_x" not in room:
            continue
        nodes[str(room["id"])] = {"label": room.get("label", str(room["id"])), "x": float(room["front_x"])}
    return nodes


def label_node(route_id, label, floor_nodes):
    location = str(label.get("label", {}).get("location", ""))
    match = re.search(r"\d{4}(?:-\d)?", location)
    if match and match.group(0) in floor_nodes:
        return match.group(0)
    lap_index = int(label.get("label", {}).get("lap_index", label.get("label_index", 0)) or 0)
    lap_total = int(label.get("label", {}).get("lap_total", 0) or 0)
    if lap_total and lap_index == lap_total:
        if "TO_RIGHT_STAIRS" in route_id:
            return "RIGHT_STAIRS"
        if "TO_LEFT_STAIRS" in route_id:
            return "LEFT_STAIRS"
    return None


def event_features(timestamp, sensors, platform):
    low, high = timestamp - WINDOW_MS, timestamp + WINDOW_MS
    magnetic = [norm(values) for time, values in sensors.get("magnetic_field_ut", []) if low <= time <= high and len(values) >= 3]
    pressure = [float(values[0]) for time, values in sensors.get("pressure_hpa", []) if low <= time <= high and values]
    heading = []
    if platform == "android":
        heading = [yaw_degrees(values) for time, values in sensors.get("rotation_vector", []) if low <= time <= high]
        heading = [value for value in heading if value is not None]
    if len(magnetic) < 5:
        return None
    return {
        "magnetic_median_ut": median(magnetic),
        "magnetic_std_ut": stdev(magnetic),
        "pressure_median_hpa": median(pressure),
        "heading_mean_deg": circular_mean(heading),
        "magnetic_samples": len(magnetic),
        "pressure_samples": len(pressure),
    }


def trusted_android_paths():
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    raw = DATA / manifest["raw_directory"]
    for session in manifest["sessions"]:
        if session.get("include_in_analysis", True) and session.get("status", "").startswith("accepted"):
            yield raw / session["file"]


def source_paths():
    for path in trusted_android_paths():
        yield "android", path
    for path in sorted((DATA / "raw" / "ios" / "2026-09-05").glob("*.jsonl")):
        yield "ios", path


def leave_one_source_out(events):
    results = {}
    for platform in ("android", "ios"):
        evaluated = []
        platform_events = [event for event in events if event["platform"] == platform]
        for event in platform_events:
            candidates = []
            keys = {(item["floor"], item["node_id"]) for item in platform_events if item["source"] != event["source"]}
            if (event["floor"], event["node_id"]) not in keys:
                continue
            for floor, node_id in keys:
                if floor != event["floor"]:
                    continue
                references = [
                    item for item in platform_events
                    if item["floor"] == floor and item["node_id"] == node_id and item["source"] != event["source"]
                ]
                reference_median = median([item["magnetic_median_ut"] for item in references])
                reference_spread = max(1.5, stdev([item["magnetic_median_ut"] for item in references]))
                score = abs(event["magnetic_median_ut"] - reference_median) / reference_spread
                candidates.append((score, node_id))
            candidates.sort()
            ranking = [node_id for _, node_id in candidates]
            nodes = map_nodes(event["floor"])
            predicted = ranking[0]
            evaluated.append({
                "top1": predicted == event["node_id"],
                "top3": event["node_id"] in ranking[:3],
                "x_error": abs(nodes[predicted]["x"] - nodes[event["node_id"]]["x"]),
            })
        if evaluated:
            results[platform] = {
                "evaluated_observations": len(evaluated),
                "top1_accuracy": round(sum(item["top1"] for item in evaluated) / len(evaluated), 4),
                "top3_accuracy": round(sum(item["top3"] for item in evaluated) / len(evaluated), 4),
                "mean_map_x_error": round(statistics.fmean(item["x_error"] for item in evaluated), 4),
                "method": "leave-one-source-out, same-floor magnetic median only",
            }
    return results


def cross_platform_transfer(fingerprints):
    android = {
        (item["floor"], item["node_id"]): item["magnetic_median_ut"]
        for item in fingerprints if item["platform"] == "android"
    }
    ios = {
        (item["floor"], item["node_id"]): item["magnetic_median_ut"]
        for item in fingerprints if item["platform"] == "ios"
    }
    keys = sorted(set(android) & set(ios))
    if len(keys) < 3:
        return []
    source = [android[key] for key in keys]
    target = [ios[key] for key in keys]
    source_mean = statistics.fmean(source)
    target_mean = statistics.fmean(target)
    slope = sum((x - source_mean) * (y - target_mean) for x, y in zip(source, target)) / sum(
        (x - source_mean) ** 2 for x in source
    )
    intercept = target_mean - slope * source_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(source, target)]
    correlation = sum((x - source_mean) * (y - target_mean) for x, y in zip(source, target)) / math.sqrt(
        sum((x - source_mean) ** 2 for x in source) * sum((y - target_mean) ** 2 for y in target)
    )
    return [{
        "source_platform": "android",
        "target_platform": "ios",
        "slope": round(slope, 6),
        "intercept": round(intercept, 6),
        "rmse_ut": round(math.sqrt(statistics.fmean(value * value for value in residuals)), 4),
        "correlation": round(correlation, 4),
        "overlap_nodes": len(keys),
        "scope": "4F right corridor overlap; experimental transfer only",
    }]


def ios_hybrid_leave_one_source_out(events):
    android_events = [item for item in events if item["platform"] == "android"]
    ios_events = [item for item in events if item["platform"] == "ios"]
    evaluated = []
    for test in ios_events:
        training_ios = [item for item in ios_events if item["source"] != test["source"]]
        ios_groups = defaultdict(list)
        android_groups = defaultdict(list)
        for item in training_ios:
            ios_groups[(item["floor"], item["node_id"])].append(item["magnetic_median_ut"])
        for item in android_events:
            android_groups[(item["floor"], item["node_id"])].append(item["magnetic_median_ut"])
        overlap = sorted(set(ios_groups) & set(android_groups))
        if len(overlap) < 3:
            continue
        source = [median(android_groups[key]) for key in overlap]
        target = [median(ios_groups[key]) for key in overlap]
        source_mean = statistics.fmean(source)
        target_mean = statistics.fmean(target)
        slope = sum((x - source_mean) * (y - target_mean) for x, y in zip(source, target)) / sum((x - source_mean) ** 2 for x in source)
        intercept = target_mean - slope * source_mean
        residuals = [y - (intercept + slope * x) for x, y in zip(source, target)]
        transfer_rmse = math.sqrt(statistics.fmean(value * value for value in residuals))
        candidates = []
        for key, values in ios_groups.items():
            spread = max(2.0, stdev(values))
            candidates.append((abs(test["magnetic_median_ut"] - median(values)) / spread, key))
        for key, values in android_groups.items():
            if key in ios_groups:
                continue
            transformed = intercept + slope * median(values)
            spread = max(2.0, abs(slope) * stdev(values) + transfer_rmse)
            candidates.append((abs(test["magnetic_median_ut"] - transformed) / spread + 0.35, key))
        candidates.sort()
        ranking = [key for _, key in candidates]
        truth = (test["floor"], test["node_id"])
        predicted = ranking[0]
        truth_nodes = map_nodes(test["floor"])
        predicted_nodes = map_nodes(predicted[0])
        evaluated.append({
            "top1": predicted == truth,
            "top3": truth in ranking[:3],
            "floor": predicted[0] == test["floor"],
            "x_error": abs(predicted_nodes[predicted[1]]["x"] - truth_nodes[test["node_id"]]["x"]),
        })
    return {
        "evaluated_observations": len(evaluated),
        "top1_accuracy": round(sum(item["top1"] for item in evaluated) / len(evaluated), 4),
        "top3_accuracy": round(sum(item["top3"] for item in evaluated) / len(evaluated), 4),
        "floor_accuracy": round(sum(item["floor"] for item in evaluated) / len(evaluated), 4),
        "mean_map_x_error": round(statistics.fmean(item["x_error"] for item in evaluated), 4),
        "method": "iOS leave-one-source-out; direct iOS plus Android-to-iOS transfer; all covered floors",
    } if evaluated else None


def main():
    events = []
    coverage = defaultdict(set)
    for platform, path in source_paths():
        start, labels, sensors = parse(path)
        route_id = str(start.get("label", {}).get("route_id", ""))
        if "CORE_TO_" not in route_id:
            continue
        floor = int(start.get("label", {}).get("floor", 0))
        nodes = map_nodes(floor)
        start_features = event_features(int(start["wall_time_ms"]) + WINDOW_MS, sensors, platform)
        if start_features:
            events.append({"platform": platform, "floor": floor, "node_id": "CORE", "source": path.name, **start_features})
        for label in labels:
            node_id = label_node(route_id, label, nodes)
            if not node_id:
                continue
            features = event_features(int(label["wall_time_ms"]), sensors, platform)
            if features:
                events.append({"platform": platform, "floor": floor, "node_id": node_id, "source": path.name, **features})
                coverage[platform].add(floor)

    grouped = defaultdict(list)
    for event in events:
        grouped[(event["platform"], event["floor"], event["node_id"])].append(event)

    fingerprints = []
    for (platform, floor, node_id), items in sorted(grouped.items()):
        nodes = map_nodes(floor)
        node = nodes.get(node_id)
        if not node:
            continue
        magnetic_medians = [item["magnetic_median_ut"] for item in items]
        pressures = [item["pressure_median_hpa"] for item in items if item["pressure_median_hpa"] is not None]
        headings = [item["heading_mean_deg"] for item in items if item["heading_mean_deg"] is not None]
        fingerprints.append({
            "platform": platform,
            "floor": floor,
            "node_id": node_id,
            "label": node["label"],
            "map_x": node["x"],
            "observation_count": len(items),
            "magnetic_median_ut": round(median(magnetic_medians), 4),
            "magnetic_between_observation_std_ut": round(stdev(magnetic_medians), 4),
            "magnetic_within_window_std_ut": round(statistics.fmean(item["magnetic_std_ut"] for item in items), 4),
            "pressure_median_hpa": round(median(pressures), 4) if pressures else None,
            "heading_mean_deg": round(circular_mean(headings), 2) if headings else None,
            "sources": sorted({item["source"] for item in items}),
        })

    output = {
        "schema_version": 1,
        "window_ms": WINDOW_MS,
        "purpose": "experimental_stationary_initial_position_candidates",
        "limitations": [
            "Most Android nodes have one observation only.",
            "iOS coverage is currently limited to the 4F right corridor.",
            "Absolute pressure is retained for diagnostics and must not decide the floor alone.",
        ],
        "coverage": {platform: sorted(floors) for platform, floors in coverage.items()},
        "validation": {
            **leave_one_source_out(events),
            "ios_hybrid_all_floors": ios_hybrid_leave_one_source_out(events),
        },
        "transfer_models": cross_platform_transfer(fingerprints),
        "fingerprints": fingerprints,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(fingerprints)} fingerprints from {len(events)} labeled observations")


if __name__ == "__main__":
    main()
