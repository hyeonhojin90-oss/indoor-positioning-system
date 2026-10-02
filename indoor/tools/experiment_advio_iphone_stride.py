"""Replay ADVIO iPhone IMU with the Expo step detector; analysis only.

The script never imports into the mobile app or writes a production motion model.
It keeps the same acceleration-magnitude threshold and 280 ms separation used by
app/expo-sensor-collector/positionTracking.js, after resampling ADVIO's 100 Hz
CoreMotion acceleration to the 20 Hz median rate observed in local Expo logs.
"""
from __future__ import annotations

import bisect
import csv
import hashlib
import io
import json
import math
import statistics
import sys
import zipfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
ADVIO_DIR = ROOT / "indoor/data/external/advio"
OUTPUT = ROOT / "indoor/data/analysis/detailed-20260914/advio-iphone-stride-v1.json"
SURVEY = json.loads((ROOT / "indoor/web/data/maps/floor-04-survey.json").read_text(encoding="utf-8"))
DISTANCE_M = SURVEY["core_center_to_right_end"]["reference_length_m"]


def downsample(rows, interval_s=0.05):
    out, next_time = [], -float("inf")
    for row in rows:
        if row[0] >= next_time:
            out.append(row)
            next_time = row[0] + interval_s
    return out


def detector(samples):
    """Direct Python equivalent of updateStepDetector in positionTracking.js."""
    gravity = previous = peak_value = 0.0
    rising = initialized = False
    last_sample = last_step_peak = None
    events = []
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
            separated = last_step_peak is None or peak_time - last_step_peak >= 0.280
            if peak_value >= 1.0 and separated:
                # Runtime increments at this falling-slope callback. Use that
                # same time when sampling the reference trajectory.
                events.append((time_s, peak_value))
                last_step_peak = peak_time
            rising = False
            peak_value, peak_time = dynamic, time_s
        previous = dynamic
    return events


def csv_rows(archive, name):
    return list(csv.reader(io.StringIO(archive.read(name).decode("utf-8-sig", errors="replace"))))


def interpolate_pose(poses, time_s):
    times = [row[0] for row in poses]
    index = bisect.bisect_left(times, time_s)
    if index == 0 or index == len(poses):
        return None
    before, after = poses[index - 1], poses[index]
    ratio = (time_s - before[0]) / (after[0] - before[0])
    return tuple(a + ratio * (b - a) for a, b in zip(before[1:], after[1:]))


def advio_rows(path):
    with zipfile.ZipFile(path) as archive:
        roots = {item.filename.split("/")[0] for item in archive.infolist() if item.filename.count("/") >= 2}
        if len(roots) != 1:
            raise ValueError(f"Unexpected ADVIO root in {path.name}: {roots}")
        root = roots.pop()
        acceleration = [tuple(map(float, row[:4])) for row in csv_rows(archive, f"{root}/iphone/accelerometer.csv")]
        poses = [tuple(map(float, row[:4])) for row in csv_rows(archive, f"{root}/ground-truth/pose.csv")]
    # ADVIO-13 values have a stationary magnitude about 9.8, so they are
    # already m/s². Do not multiply by g despite older README wording.
    samples = downsample([(time_s, (x, y, z)) for time_s, x, y, z in acceleration])
    events = detector(samples)
    rows = []
    for (previous_time, _), (current_time, peak) in zip(events, events[1:]):
        interval = current_time - previous_time
        before, after = interpolate_pose(poses, previous_time), interpolate_pose(poses, current_time)
        if before is None or after is None:
            continue
        # ADVIO office trajectories use y as vertical (the stair sequence has
        # 4.435 m y extent); match local horizontal corridor distance with x-z.
        stride = math.hypot(after[0] - before[0], after[2] - before[2])
        if 0.280 <= interval <= 2.5 and 0.15 <= stride <= 1.8:
            rows.append({"cadence": 1 / interval, "peak": peak, "stride": stride})
    magnitude = [math.sqrt(x * x + y * y + z * z) for _, x, y, z in acceleration]
    return {"file": path.name, "raw_samples": len(acceleration), "samples_20hz": len(samples),
            "detected_events": len(events), "rows": rows,
            "magnitude_median": statistics.median(magnitude)}


def fit_ridge(rows, ridge=5.0):
    x = np.array([[row["cadence"], row["peak"]] for row in rows], dtype=float)
    y = np.array([row["stride"] for row in rows], dtype=float)
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-6] = 1.0
    z = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    weights = np.linalg.solve(z.T @ z + np.diag([0.0, ridge, ridge]), z.T @ y)
    return {"intercept": float(weights[0]), "weights": [float(v) for v in weights[1:]],
            "mean": [float(v) for v in mean], "scale": [float(v) for v in scale],
            "median_stride": float(np.median(y))}


def predict(model, cadence, peak):
    values = [(cadence - model["mean"][0]) / model["scale"][0],
              (peak - model["mean"][1]) / model["scale"][1]]
    return model["intercept"] + sum(a * b for a, b in zip(model["weights"], values))


def within_sequence_holdout(rows):
    split = max(1, round(len(rows) * 0.6))
    train, held = rows[:split], rows[split:]
    model = fit_ridge(train)
    actual = np.array([row["stride"] for row in held])
    prediction = np.array([predict(model, row["cadence"], row["peak"]) for row in held])
    return {"training_rows": len(train), "held_rows": len(held),
            "model_mae_m": float(np.mean(np.abs(prediction - actual))),
            "median_baseline_mae_m": float(np.mean(np.abs(model["median_stride"] - actual)))}


def leave_one_sequence_out(sequences):
    """Keep an entire office/stair route out of source training."""
    reports = []
    if len(sequences) < 2:
        return reports
    for held in sequences:
        train = [row for sequence in sequences if sequence is not held for row in sequence["rows"]]
        test = held["rows"]
        if len(train) < 3 or not test:
            continue
        model = fit_ridge(train)
        truth = np.array([row["stride"] for row in test])
        prediction = np.array([predict(model, row["cadence"], row["peak"]) for row in test])
        reports.append({"held_file": held["file"], "training_rows": len(train), "held_rows": len(test),
                        "model_mae_m": float(np.mean(np.abs(prediction - truth))),
                        "median_baseline_mae_m": float(np.mean(np.abs(model["median_stride"] - truth)))})
    return reports


def local_sessions():
    paths = [
        *(ROOT / "indoor/data/raw/ios/2026-09-05").glob("*.jsonl"),
        *(ROOT / "indoor/data/raw/ios/2026-09-08").glob("*.jsonl"),
        *(ROOT / "indoor/data/raw/ios/2026-09-14").glob("*.jsonl"),
        *(Path(sys.argv[1]) / f"indoor_positioning_ios_20260914_{stamp}.jsonl"
          for stamp in ("133338", "133534", "133637", "133734")),
    ]
    fresh_ids = {"170738", "170901", "171021", "171142"}
    output = []
    for path in paths:
        if not path.exists():
            continue
        data = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        route = data[0].get("label", {}).get("route_id")
        if route not in {"4F_CORE_TO_RIGHT_STAIRS", "4F_CORE_TO_RIGHT_STAIRS_REVERSE"}:
            continue
        samples = [(row["wall_time_ms"] / 1000, tuple(row["values"])) for row in data
                   if row.get("sensor") == "accelerometer_mps2"]
        events = detector(samples)
        if events:
            output.append({"file": path.name, "events": events,
                           "fresh": any(marker in path.name for marker in fresh_ids)})
    return output


def local_domain(sessions):
    features = []
    for session in sessions:
        for (previous_time, _), (current_time, peak) in zip(session["events"], session["events"][1:]):
            interval = current_time - previous_time
            if 0.280 <= interval <= 2.5:
                features.append((1 / interval, peak))
    values = np.array(features, dtype=float)
    mean, scale = values.mean(axis=0), values.std(axis=0)
    scale[scale < 1e-6] = 1.0
    return {"rows": len(values), "mean": [float(v) for v in mean], "scale": [float(v) for v in scale]}


def weighted_base(sessions):
    values = sorted((DISTANCE_M / len(session["events"]), len(session["events"])) for session in sessions)
    target, passed = sum(weight for _, weight in values) / 2, 0
    for value, weight in values:
        passed += weight
        if passed >= target:
            return value
    return values[-1][0]


def replay_local(session, base, model, domain):
    dynamic, result, previous_time = base, [], None
    for time_s, peak in session["events"]:
        if previous_time is None:
            predicted = base
        else:
            cadence = 1 / (time_s - previous_time)
            local_z = [(cadence - domain["mean"][0]) / domain["scale"][0],
                       (peak - domain["mean"][1]) / domain["scale"][1]]
            public_response = model["intercept"] + sum(a * b for a, b in zip(model["weights"], local_z))
            predicted = base * max(0.90, min(1.10, public_response / model["intercept"]))
        dynamic = 0.8 * dynamic + 0.2 * predicted
        result.append(dynamic)
        previous_time = time_s
    estimate = sum(result)
    return {"estimate_m": estimate, "signed_error_m": estimate - DISTANCE_M,
            "error_m": abs(estimate - DISTANCE_M), "min_stride_m": min(result), "max_stride_m": max(result)}


def local_leave_one_walk_out(sessions, model):
    """Evaluate all local walks without using a held walk's endpoint or features."""
    trials = []
    for held in sessions:
        training = [session for session in sessions if session is not held]
        base, domain = weighted_base(training), local_domain(training)
        fixed_estimate = len(held["events"]) * base
        trials.append({
            "file": held["file"],
            "detected_events": len(held["events"]),
            "personal_fixed": {"base_m_per_event": base, "estimate_m": fixed_estimate,
                               "signed_error_m": fixed_estimate - DISTANCE_M,
                               "error_m": abs(fixed_estimate - DISTANCE_M)},
            "advio_domain_normalized_ema": replay_local(held, base, model, domain),
        })
    fixed_mae = statistics.mean(trial["personal_fixed"]["error_m"] for trial in trials)
    advio_mae = statistics.mean(trial["advio_domain_normalized_ema"]["error_m"] for trial in trials)
    return {"sessions": len(trials), "personal_fixed_endpoint_mae_m": fixed_mae,
            "advio_endpoint_mae_m": advio_mae, "delta_m": advio_mae - fixed_mae, "trials": trials}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: experiment_advio_iphone_stride.py <external 20260914 jsonl directory>")
    # Ignore an in-progress archive while background downloads continue.
    archives = [path for path in sorted(ADVIO_DIR.glob("advio-*.zip")) if zipfile.is_zipfile(path)]
    if not archives:
        raise RuntimeError("No ADVIO archive downloaded")
    sequences = [advio_rows(path) for path in archives]
    usable = [row for sequence in sequences for row in sequence["rows"]]
    model = fit_ridge(usable)
    local = local_sessions()
    earlier, fresh = [s for s in local if not s["fresh"]], [s for s in local if s["fresh"]]
    base, domain = weighted_base(earlier), local_domain(earlier)
    fixed = [abs(len(s["events"]) * base - DISTANCE_M) for s in fresh]
    transfer = [{"file": s["file"], **replay_local(s, base, model, domain)} for s in fresh]
    fixed = [{"file": s["file"], "estimate_m": len(s["events"]) * base,
              "signed_error_m": len(s["events"]) * base - DISTANCE_M,
              "error_m": abs(len(s["events"]) * base - DISTANCE_M)} for s in fresh]
    result = {
        "purpose": "Analysis-only ADVIO iPhone experiment; production engine and model unchanged.",
        "source": {"name": "ADVIO", "archives": [{"file": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in archives],
                   "detector": "Expo acceleration magnitude peak >=1.0m/s², 280ms separation, 20Hz resample",
                   "horizontal_reference": "ADVIO x-z; y is vertical in office stair data"},
        "advio_sequences": [{key: value for key, value in sequence.items() if key != "rows"} | {
            "usable_stride_rows": len(sequence["rows"]),
            "stride_median_m": float(np.median([row["stride"] for row in sequence["rows"]])) if sequence["rows"] else None,
            "holdout": within_sequence_holdout(sequence["rows"]) if len(sequence["rows"]) >= 20 else None,
        } for sequence in sequences],
        "advio_leave_one_route_out": leave_one_sequence_out(sequences),
        "local_transfer": {"base_m_per_event": base, "fixed_endpoint_mae_m": statistics.mean(row["error_m"] for row in fixed),
                           "advio_domain_normalized_ema_endpoint_mae_m": statistics.mean(row["error_m"] for row in transfer),
                           "test_sessions": [s["file"] for s in fresh], "local_feature_domain": domain},
        "local_transfer_trials": {"fixed": fixed, "advio_domain_normalized_ema": transfer},
        "local_leave_one_walk_out": local_leave_one_walk_out(local, model),
        "limits": ["ADVIO contains four office/stair routes, but not a participant-held-out iPhone population evaluation.",
                   "ADVIO ground-truth pose is a reference trajectory; this experiment does not claim an independent per-step foot-placement truth.",
                   "No production model changes are made from this result."],
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
