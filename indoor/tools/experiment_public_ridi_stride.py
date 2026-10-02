"""Train a public-data stride prior from RIDI, then test it on local 4F walks.

This is an analysis-only experiment.  The public model never writes
motion-models.json and no app or Fusion runtime imports its output.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RIDIZIP = ROOT / "indoor/data/external/ridi/ridi_data_publish_v2.zip"
SURVEY = json.loads((ROOT / "indoor/web/data/maps/floor-04-survey.json").read_text(encoding="utf-8"))
DISTANCE = SURVEY["core_center_to_right_end"]["reference_length_m"]
LOCAL_EXTERNAL = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def detector(samples):
    """Mirror app/expo-sensor-collector/positionTracking.js at 20 Hz."""
    gravity = previous = peak_value = 0.0
    rising = False
    initialized = False
    last_sample = last_step_peak = None
    steps = []
    for time_s, xyz, position in samples:
        magnitude = math.sqrt(sum(v * v for v in xyz))
        if not initialized:
            gravity = magnitude
            last_sample = time_s
            initialized = True
            continue
        dt = max(0.001, min(0.1, time_s - last_sample))
        last_sample = time_s
        gravity += min(1.0, dt / 0.8) * (magnitude - gravity)
        dynamic = magnitude - gravity
        if dynamic > previous:
            if not rising:
                peak_value = dynamic
                peak_time = time_s
            rising = True
            if dynamic > peak_value:
                peak_value = dynamic
                peak_time = time_s
        elif rising:
            separated = last_step_peak is None or peak_time - last_step_peak >= 0.280
            if peak_value >= 1.0 and separated:
                steps.append((time_s, peak_value, position))
                last_step_peak = peak_time
            rising = False
            peak_value = dynamic
            peak_time = time_s
        previous = dynamic
    return steps


def downsample(rows, interval_s=0.05):
    out, next_time = [], -float("inf")
    for row in rows:
        if row[0] >= next_time:
            out.append(row)
            next_time = row[0] + interval_s
    return out


def read_ridi_sequence(archive: zipfile.ZipFile, name: str):
    raw = archive.read(name).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    rows = []
    for r in reader:
        try:
            rows.append((
                float(r["time"]) / 1e9,
                (float(r["acce_x"]), float(r["acce_y"]), float(r["acce_z"])),
                (float(r["pos_x"]), float(r["pos_y"]), float(r["pos_z"])),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return downsample(rows)


def public_rows(archive: zipfile.ZipFile):
    """Use handheld, bag, and body placements; reserve two people by subject."""
    names = [i.filename for i in archive.infolist()
             if re.fullmatch(r"data_publish_v2/[^/]+/processed/data\.csv", i.filename)]
    data = []
    for name in sorted(names):
        session = name.split("/")[1]
        if not any(x in session for x in ("handheld", "bag", "body")):
            continue
        subject = session.split("_")[0]
        steps = detector(read_ridi_sequence(archive, name))
        for previous, current in zip(steps, steps[1:]):
            interval = current[0] - previous[0]
            # RIDI trajectories are on the x-y walking plane; z is vertical
            # (verified by inspect_ridi_axes.py).  Match the 4F horizontal
            # corridor reference rather than treating device-height noise as
            # walking distance.
            stride = math.hypot(previous[2][0] - current[2][0], previous[2][1] - current[2][1])
            if 0.28 <= interval <= 2.5 and 0.15 <= stride <= 1.8:
                data.append({"session": session, "subject": subject,
                             "cadence": 1 / interval, "peak": current[1], "stride": stride})
    return data


def fit_ridge(rows, ridge=5.0):
    """Fit target step length from exactly the two features Expo has at a step."""
    x = np.array([[r["cadence"], r["peak"]] for r in rows], dtype=float)
    y = np.array([r["stride"] for r in rows], dtype=float)
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-6] = 1.0
    z = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    reg = np.diag([0.0, ridge, ridge])
    weights = np.linalg.solve(z.T @ z + reg, z.T @ y)
    return {"intercept": float(weights[0]), "weights": [float(v) for v in weights[1:]],
            "mean": [float(v) for v in mean], "scale": [float(v) for v in scale],
            "median_stride": float(np.median(y))}


def predict(model, cadence, peak):
    z = [(cadence - model["mean"][0]) / model["scale"][0],
         (peak - model["mean"][1]) / model["scale"][1]]
    return model["intercept"] + sum(a * b for a, b in zip(model["weights"], z))


def evaluate_public(model, rows):
    values = [predict(model, r["cadence"], r["peak"]) for r in rows]
    return {"rows": len(rows), "mae_m": float(np.mean(np.abs(np.array(values) - np.array([r["stride"] for r in rows])))),
            "baseline_median_mae_m": float(np.mean(np.abs(model["median_stride"] - np.array([r["stride"] for r in rows]))))}


def read_local(file: Path):
    rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = rows[0]
    route = start.get("label", {}).get("route_id")
    if route not in ("4F_CORE_TO_RIGHT_STAIRS", "4F_CORE_TO_RIGHT_STAIRS_REVERSE"):
        return None
    samples = []
    for row in rows:
        if row.get("sensor") == "accelerometer_mps2":
            samples.append((row["wall_time_ms"] / 1000, tuple(row["values"]), (0.0, 0.0, 0.0)))
    return {"file": file.name, "steps": detector(samples)}


def local_files():
    if LOCAL_EXTERNAL is None:
        raise RuntimeError("Pass the external 20260914 JSONL directory as argv[1].")
    return [
        *(ROOT / "indoor/data/raw/ios/2026-09-05").glob("*.jsonl"),
        *(ROOT / "indoor/data/raw/ios/2026-09-08").glob("*.jsonl"),
        *(LOCAL_EXTERNAL / f"indoor_positioning_ios_20260914_{i}.jsonl" for i in ("133338", "133534", "133637", "133734")),
        *(ROOT / "indoor/data/raw/ios/2026-09-14").glob("*.jsonl"),
    ]


def local_feature_stats(sessions):
    rows = []
    for session in sessions:
        for previous, current in zip(session["steps"], session["steps"][1:]):
            interval = current[0] - previous[0]
            if 0.28 <= interval <= 2.5:
                rows.append((1 / interval, current[1]))
    values = np.array(rows, dtype=float)
    mean = values.mean(axis=0)
    scale = values.std(axis=0)
    scale[scale < 1e-6] = 1.0
    return {"mean": [float(v) for v in mean], "scale": [float(v) for v in scale], "rows": len(rows)}


def replay_local(session, base, model, smoothing, domain=None):
    applied, previous_time, dynamic = [], None, base
    for time_s, peak, _ in session["steps"]:
        if previous_time is None:
            predicted = base
        else:
            cadence = 1 / (time_s - previous_time)
            if domain is None:
                public = predict(model, cadence, peak)
                multiplier = public / model["median_stride"]
            else:
                # Re-express this iPhone feature vector by the earlier local
                # feature distribution, then use only the public model's
                # learned relative response. No held-out endpoint is used.
                z = [(cadence - domain["mean"][0]) / domain["scale"][0],
                     (peak - domain["mean"][1]) / domain["scale"][1]]
                public = model["intercept"] + sum(a * b for a, b in zip(model["weights"], z))
                multiplier = public / model["intercept"]
            # Public data supplies only a relative gait multiplier.  The local
            # surveyed 4F base remains the absolute scale for this app/device.
            predicted = base * max(0.90, min(1.10, multiplier))
        previous_time = time_s
        dynamic = smoothing * dynamic + (1 - smoothing) * predicted
        applied.append(dynamic)
    estimate = sum(applied)
    return {"estimate_m": estimate, "error_m": abs(estimate - DISTANCE),
            "min_stride_m": min(applied), "max_stride_m": max(applied)}


def public_multipliers(session, model, domain):
    values, previous_time = [], None
    for time_s, peak, _ in session["steps"]:
        if previous_time is not None:
            cadence = 1 / (time_s - previous_time)
            z = [(cadence - domain["mean"][0]) / domain["scale"][0],
                 (peak - domain["mean"][1]) / domain["scale"][1]]
            value = model["intercept"] + sum(a * b for a, b in zip(model["weights"], z))
            values.append(max(0.90, min(1.10, value / model["intercept"])))
        previous_time = time_s
    return values


def fit_transfer(earlier, base, public_model, domain, ridge=2.0):
    # Local endpoints supervise only the gain and offset of the public gait
    # response. This is deliberately a two-parameter fine tune, not a new
    # local neural model trained on 11 walks.
    feature = np.array([statistics.mean(public_multipliers(s, public_model, domain)) for s in earlier])
    target = np.array([DISTANCE / len(s["steps"]) for s in earlier])
    x = np.column_stack([np.ones(len(feature)), feature - 1.0])
    prior = np.array([base, 0.0])
    # Ridge toward local base/no public gain.  It prevents the small local set
    # from turning public feature noise into a large per-step change.
    matrix = x.T @ x + np.diag([ridge, ridge])
    vector = x.T @ target + ridge * prior
    coefficient = np.linalg.solve(matrix, vector)
    return {"intercept": float(coefficient[0]), "gain": float(coefficient[1]),
            "ridge": ridge, "training_session_feature_mean": float(feature.mean()),
            "training_session_feature_std": float(feature.std())}


def replay_transfer(session, base, public_model, domain, transfer, smoothing=0.8):
    dynamic, applied = base, []
    values = public_multipliers(session, public_model, domain)
    running = []
    for i in range(len(session["steps"])):
        if i:
            running.append(values[i - 1])
            feature = statistics.mean(running)
            predicted = transfer["intercept"] + transfer["gain"] * (feature - 1.0)
        else:
            predicted = base
        predicted = max(base * 0.90, min(base * 1.10, predicted))
        dynamic = smoothing * dynamic + (1 - smoothing) * predicted
        applied.append(dynamic)
    estimate = sum(applied)
    return {"estimate_m": estimate, "error_m": abs(estimate - DISTANCE),
            "min_stride_m": min(applied), "max_stride_m": max(applied)}


def weighted_median_stride(sessions):
    ordered = sorted((DISTANCE / len(s["steps"]), len(s["steps"])) for s in sessions)
    total, passed = sum(weight for _, weight in ordered), 0
    for value, weight in ordered:
        passed += weight
        if passed >= total / 2:
            return value
    return ordered[-1][0]


def main():
    if not RIDIZIP.exists():
        raise RuntimeError(f"Missing RIDI archive: {RIDIZIP}")
    with zipfile.ZipFile(RIDIZIP) as archive:
        public = public_rows(archive)
    if not public:
        raise RuntimeError("No usable RIDI step rows")
    held_subjects = {"hang", "huayi"}
    train = [r for r in public if r["subject"] not in held_subjects]
    held = [r for r in public if r["subject"] in held_subjects]
    model = fit_ridge(train)

    local = [read_local(p) for p in local_files()]
    local = [s for s in local if s]
    fresh_ids = {"170738", "170901", "171021", "171142"}
    fresh = [s for s in local if any(i in s["file"] for i in fresh_ids)]
    earlier = [s for s in local if s not in fresh]
    base = weighted_median_stride(earlier)
    local_domain = local_feature_stats(earlier)
    transfer = fit_transfer(earlier, base, model, local_domain)
    variants = {}
    for name, settings in {
        "public_relative_direct": {"smoothing": 0.0, "domain": None},
        "public_relative_ema_0_8": {"smoothing": 0.8, "domain": None},
        "public_domain_normalized_direct": {"smoothing": 0.0, "domain": local_domain},
        "public_domain_normalized_ema_0_8": {"smoothing": 0.8, "domain": local_domain},
    }.items():
        trials = [{"file": s["file"], **replay_local(s, base, model, **settings)} for s in fresh]
        variants[name] = {"endpoint_mae_m": statistics.mean(t["error_m"] for t in trials), "trials": trials}
    transfer_trials = [{"file": s["file"], **replay_transfer(s, base, model, local_domain, transfer)} for s in fresh]
    variants["public_prior_local_endpoint_finetune_ema_0_8"] = {
        "endpoint_mae_m": statistics.mean(t["error_m"] for t in transfer_trials),
        "trials": transfer_trials, "transfer": transfer,
    }
    fixed = [abs(len(s["steps"]) * base - DISTANCE) for s in fresh]
    out = {
        "purpose": "Analysis-only public RIDI prior experiment; no production model update.",
        "public_source": {"name": "RIDI Robust IMU Double Integration", "archive": str(RIDIZIP.relative_to(ROOT)),
                          "sha256": __import__("hashlib").sha256(RIDIZIP.read_bytes()).hexdigest(),
                          "features": ["accelerometer magnitude peak", "inter-step cadence"],
                          "target": "ground-truth horizontal x-y displacement between detected steps"},
        "public_split": {"train_subjects": sorted({r["subject"] for r in train}), "held_subjects": sorted(held_subjects),
                         "train": evaluate_public(model, train), "held": evaluate_public(model, held), "model": model},
        "local_application": {"distance_m": DISTANCE, "local_base_m_per_detected_step": base,
                              "feature_normalization_from_earlier_local_sessions": local_domain,
                              "test_sessions": [s["file"] for s in fresh], "fixed_endpoint_mae_m": statistics.mean(fixed),
                              "variants": variants},
        "limits": ["RIDI is Android/Tango data, while local data is iPhone Expo; only a bounded relative multiplier is transferred.",
                   "RIDI x-y ground-truth target and the 4F reference are both horizontal distances.",
                   "No local per-step physical ground truth exists, so local evaluation is endpoint-only."]
    }
    output = ROOT / "indoor/data/analysis/detailed-20260914/public-ridi-stride-v1.json"
    output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"public": out["public_split"], "local": out["local_application"]}, indent=2))


if __name__ == "__main__":
    main()
