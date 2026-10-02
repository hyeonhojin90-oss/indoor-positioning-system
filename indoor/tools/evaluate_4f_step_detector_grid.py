"""Test step-detector parameters on all surveyed 4F right-corridor iPhone logs.

Analysis only: no app constants are changed. Each candidate is evaluated both
with leave-one-walk-out personal scale and an earlier-11 to newer-4 split.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISTANCE_M = json.loads((ROOT / "indoor/web/data/maps/floor-04-survey.json").read_text(encoding="utf-8"))["core_center_to_right_end"]["reference_length_m"]


def detector(samples, threshold, minimum_gap_s):
    gravity = previous = peak_value = 0.0
    rising = initialized = False
    last_sample = last_step_peak = None
    count = 0
    for time_s, xyz in samples:
        magnitude = math.sqrt(sum(v * v for v in xyz))
        if not initialized:
            gravity, last_sample, initialized = magnitude, time_s, True
            continue
        dt = max(0.001, min(0.1, time_s - last_sample))
        last_sample = time_s
        gravity += min(1.0, dt / 0.8) * (magnitude - gravity)
        dynamic = magnitude - gravity
        if dynamic > previous:
            if not rising:
                peak_value, peak_time = dynamic, time_s
            rising = True
            if dynamic > peak_value:
                peak_value, peak_time = dynamic, time_s
        elif rising:
            if peak_value >= threshold and (last_step_peak is None or peak_time - last_step_peak >= minimum_gap_s):
                count += 1
                last_step_peak = peak_time
            rising = False
            peak_value, peak_time = dynamic, time_s
        previous = dynamic
    return count


def source_paths(external):
    yield from (ROOT / "indoor/data/raw/ios/2026-09-05").glob("*.jsonl")
    yield from (ROOT / "indoor/data/raw/ios/2026-09-08").glob("*.jsonl")
    yield from (ROOT / "indoor/data/raw/ios/2026-09-14").glob("*.jsonl")
    yield from (external / f"indoor_positioning_ios_20260914_{stamp}.jsonl"
                for stamp in ("133338", "133534", "133637", "133734"))


def sessions(external):
    result = []
    fresh = {"170738", "170901", "171021", "171142"}
    for path in source_paths(external):
        if not path.exists():
            continue
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if rows[0].get("label", {}).get("route_id") not in {"4F_CORE_TO_RIGHT_STAIRS", "4F_CORE_TO_RIGHT_STAIRS_REVERSE"}:
            continue
        result.append({"file": path.name, "fresh": any(stamp in path.name for stamp in fresh),
                       "samples": [(row["wall_time_ms"] / 1000, tuple(row["values"])) for row in rows if row.get("sensor") == "accelerometer_mps2"]})
    return result


def weighted_median_base(counts):
    ordered = sorted((DISTANCE_M / count, count) for count in counts if count)
    total, passed = sum(weight for _, weight in ordered), 0
    for value, weight in ordered:
        passed += weight
        if passed >= total / 2:
            return value
    return ordered[-1][0]


def evaluate(rows, threshold, gap):
    counts = [detector(row["samples"], threshold, gap) for row in rows]
    loo_errors = []
    for index, count in enumerate(counts):
        base = weighted_median_base([other for j, other in enumerate(counts) if j != index])
        loo_errors.append(abs(count * base - DISTANCE_M))
    earlier = [count for row, count in zip(rows, counts) if not row["fresh"]]
    newer = [count for row, count in zip(rows, counts) if row["fresh"]]
    chronological_base = weighted_median_base(earlier)
    chronological_errors = [abs(count * chronological_base - DISTANCE_M) for count in newer]
    return {"threshold_mps2": threshold, "minimum_gap_ms": int(gap * 1000),
            "counts": counts, "count_min": min(counts), "count_max": max(counts),
            "count_range": max(counts) - min(counts), "count_stdev": statistics.pstdev(counts),
            "loo_personal_fixed_mae_m": statistics.mean(loo_errors),
            "earlier11_to_new4_mae_m": statistics.mean(chronological_errors),
            "earlier11_base_m_per_event": chronological_base}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: evaluate_4f_step_detector_grid.py <external 20260914 jsonl directory>")
    rows = sessions(Path(sys.argv[1]))
    candidates = [evaluate(rows, threshold, gap) for threshold in [round(value, 2) for value in [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]] for gap in [0.24, 0.26, 0.28, 0.30, 0.32, 0.34]]
    current = next(row for row in candidates if row["threshold_mps2"] == 1.0 and row["minimum_gap_ms"] == 280)
    result = {"purpose": "Analysis-only detector parameter grid; no PDR constant is changed.",
              "sessions": [row["file"] for row in rows], "current": current,
              "best_by_chronological_mae": min(candidates, key=lambda row: row["earlier11_to_new4_mae_m"]),
              "best_by_loo_mae": min(candidates, key=lambda row: row["loo_personal_fixed_mae_m"]),
              "candidates": candidates,
              "limit": "The same 15 walks are used to select candidates, so a parameter change needs a new independent walking test."}
    output = ROOT / "indoor/data/analysis/detailed-20260914/4f-step-detector-grid.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("current", "best_by_chronological_mae", "best_by_loo_mae")}, indent=2))


if __name__ == "__main__":
    main()
