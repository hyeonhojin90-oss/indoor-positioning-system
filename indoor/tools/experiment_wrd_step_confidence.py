"""Validate detector-confidence features against foot-labelled smartphone data.

The public Walking Recognition Dataset has foot-sensor step timestamps.  This
script replays its handheld-phone accelerometer using the same 20 Hz,
gravity-EMA, 1.0 m/s² and 280 ms detector used by Expo.  It is analysis only:
it never imports a model into the app or changes detected events in local logs.

The useful question is whether a probability for an *already detected* event
can identify false positives.  Missed steps are reported separately; an event
probability cannot restore an event that was never emitted.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE = ROOT / "indoor/data/external/walking-recognition/walking-recognition-master.zip"
OUTPUT = ROOT / "indoor/data/analysis/detailed-20260914/wrd-step-confidence-v1.json"
LOCAL_DISTANCE_M = json.loads((ROOT / "indoor/web/data/maps/floor-04-survey.json").read_text(encoding="utf-8"))["core_center_to_right_end"]["reference_length_m"]


def time_s(value: str) -> float:
    hours, minutes, seconds = value.strip().split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def expo_detector(samples: list[tuple[float, tuple[float, float, float]]]) -> list[dict]:
    """Python-equivalent of app/expo-sensor-collector/positionTracking.js."""
    gravity = previous = peak_value = 0.0
    rising = initialized = False
    last_sample = last_step_peak = peak_time = None
    events = []
    for timestamp, xyz in samples:
        magnitude = math.sqrt(sum(value * value for value in xyz))
        if not initialized:
            gravity, last_sample, initialized = magnitude, timestamp, True
            continue
        dt = max(0.001, min(0.1, timestamp - last_sample))
        last_sample = timestamp
        gravity += min(1.0, dt / 0.8) * (magnitude - gravity)
        dynamic = magnitude - gravity
        if dynamic > previous:
            if not rising:
                peak_value, peak_time = dynamic, timestamp
            rising = True
            if dynamic > peak_value:
                peak_value, peak_time = dynamic, timestamp
        elif rising:
            if peak_value >= 1.0 and (last_step_peak is None or peak_time - last_step_peak >= 0.280):
                events.append({"time": peak_time, "peak": peak_value})
                last_step_peak = peak_time
            rising = False
            peak_value, peak_time = dynamic, timestamp
        previous = dynamic
    return events


def downsample(samples: list[tuple[float, tuple[float, float, float]]], interval_s: float = 0.05):
    out, next_time = [], -float("inf")
    for row in sorted(samples):
        if row[0] >= next_time:
            out.append(row)
            next_time = row[0] + interval_s
    return out


def read_csv(archive: zipfile.ZipFile, name: str):
    with archive.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""), skipinitialspace=True)


def match_events(events: list[dict], truth_times: list[float], tolerance_s: float = 0.250):
    """Ordered one-to-one matching; returns labels and count metrics."""
    index = matched = false_positive = missed = 0
    labels = []
    for event in events:
        while index < len(truth_times) and truth_times[index] < event["time"] - tolerance_s:
            missed += 1
            index += 1
        if index < len(truth_times) and abs(truth_times[index] - event["time"]) <= tolerance_s:
            labels.append(1)
            matched += 1
            index += 1
        else:
            labels.append(0)
            false_positive += 1
    missed += len(truth_times) - index
    return labels, {"true_positive": matched, "false_positive": false_positive, "false_negative": missed,
                    "truth_steps": len(truth_times), "detected_events": len(events)}


def nearest_norm(times: list[float], norms: list[float], target: float):
    if not times:
        return None
    index = bisect.bisect_left(times, target)
    candidates = [candidate for candidate in (index - 1, index) if 0 <= candidate < len(times)]
    nearest = min(candidates, key=lambda candidate: abs(times[candidate] - target))
    return norms[nearest] if abs(times[nearest] - target) <= 0.150 else None


def event_features(events: list[dict], gyro_times: list[float], gyro_norms: list[float]):
    prior_intervals: list[float] = []
    gyro_median = median(gyro_norms) or 1.0
    result = []
    for index, event in enumerate(events):
        interval = events[index]["time"] - events[index - 1]["time"] if index else None
        expected = median(prior_intervals) if len(prior_intervals) >= 3 else None
        interval_deviation = abs(math.log(max(interval / expected, 0.01))) if interval and expected else 0.0
        long_gap = max(0.0, (interval / expected - 1.55) / 0.70) if interval and expected else 0.0
        if interval:
            prior_intervals.append(interval)
        gyro = nearest_norm(gyro_times, gyro_norms, event["time"])
        result.append({"peak_margin": event["peak"] - 1.0, "interval_deviation": interval_deviation,
                       "long_gap": clamp(long_gap, 0, 1),
                       "gyro_relative_log": math.log(max((gyro or gyro_median) / gyro_median, 0.05)),
                       "gyro_norm": gyro})
    return result


def f1(metrics: dict) -> dict:
    tp, fp, fn = metrics["true_positive"], metrics["false_positive"], metrics["false_negative"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {**metrics, "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def sigmoid(values):
    return 1 / (1 + np.exp(-np.clip(values, -30, 30)))


def train_logistic(rows: list[dict], feature_names: tuple[str, ...]):
    features = np.asarray([[row[name] for name in feature_names] for row in rows], dtype=float)
    labels = np.asarray([row["matched"] for row in rows], dtype=float)
    mean = features.mean(axis=0)
    scale = features.std(axis=0)
    scale[scale < 1e-6] = 1
    x = np.column_stack((np.ones(len(features)), (features - mean) / scale))
    # Keep the observed class prevalence.  A class-balanced loss can be useful
    # for ranking false positives, but its output is not a calibrated event
    # probability and therefore cannot be used to set particle spread.
    weights = np.ones(len(labels))
    beta = np.zeros(x.shape[1])
    for _ in range(600):
        probabilities = sigmoid(x @ beta)
        gradient = (x.T @ (weights * (probabilities - labels))) / len(labels)
        gradient[1:] += 0.03 * beta[1:]
        beta -= 0.12 * gradient
    return {"mean": mean, "scale": scale, "beta": beta}


def predict(model, rows, feature_names: tuple[str, ...]):
    features = np.asarray([[row[name] for name in feature_names] for row in rows], dtype=float)
    x = np.column_stack((np.ones(len(features)), (features - model["mean"]) / model["scale"]))
    return sigmoid(x @ model["beta"])


def auc(labels, probabilities):
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    ranks = np.empty(len(probabilities), dtype=float)
    order = np.argsort(probabilities)
    ranks[order] = np.arange(1, len(probabilities) + 1)
    # Ties are rare with continuous features; use average rank if they occur.
    for value in np.unique(probabilities):
        tied = np.where(probabilities == value)[0]
        if len(tied) > 1:
            ranks[tied] = ranks[tied].mean()
    return float((ranks[np.asarray(labels, dtype=bool)].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def aggregate_metrics(records):
    keys = ("true_positive", "false_positive", "false_negative", "truth_steps", "detected_events")
    return f1({key: sum(record["metrics"][key] for record in records) for key in keys})


def weighted_stride_base(rows, count_key: str) -> float:
    values = sorted(((LOCAL_DISTANCE_M / row[count_key], row[count_key]) for row in rows if row[count_key]), key=lambda row: row[0])
    total, passed = sum(row[1] for row in values), 0
    for stride, weight in values:
        passed += weight
        if passed >= total / 2:
            return stride
    return values[-1][0]


def read_records(archive_path: Path):
    records = []
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        gt_names = sorted(name for name in names if name.endswith("@GT.csv"))
        for gt_name in gt_names:
            prefix = gt_name[:-len("@GT.csv")]
            acc_name, gyro_name = f"{prefix}@main_ACC.csv", f"{prefix}@main_GYRO.csv"
            if acc_name not in names or gyro_name not in names:
                continue
            parts = gt_name.split("/")
            data_index = parts.index("DATA")
            building, user, location, record_id = parts[data_index + 1:data_index + 5]
            truth = [time_s(row["global_time_peak"]) for row in read_csv(archive, gt_name) if row.get("global_time_peak")]
            acceleration = [(time_s(row["global_time"]), (float(row["acc_x"]), float(row["acc_y"]), float(row["acc_z"])))
                            for row in read_csv(archive, acc_name) if row.get("global_time")]
            gyro_rows = [(time_s(row["global_time"]), float(row["gyro_module"]))
                         for row in read_csv(archive, gyro_name) if row.get("global_time")]
            gyro_rows.sort()
            events = expo_detector(downsample(acceleration))
            labels, metrics = match_events(events, truth)
            features = event_features(events, [row[0] for row in gyro_rows], [row[1] for row in gyro_rows])
            for row, label in zip(features, labels):
                row["matched"] = label
            records.append({"building": building, "user": user, "location": location, "record_id": record_id,
                            "events": events, "features": features, "metrics": metrics})
    return records


def local_events():
    sources = [
        *sorted((ROOT / "indoor/data/raw/ios/2026-09-05").glob("*.jsonl")),
        *sorted((ROOT / "indoor/data/raw/ios/2026-09-08").glob("*.jsonl")),
        *[Path(r"C:\Users\20222967\Documents\카카오톡 받은 파일") / f"indoor_positioning_ios_20260914_{stamp}.jsonl"
          for stamp in ("133338", "133534", "133637", "133734")],
        *sorted((ROOT / "indoor/data/raw/ios/2026-09-14").glob("*.jsonl"))
    ]
    sessions = []
    for path in sources:
        if not path.exists():
            continue
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if rows[0].get("label", {}).get("route_id") not in {"4F_CORE_TO_RIGHT_STAIRS", "4F_CORE_TO_RIGHT_STAIRS_REVERSE"}:
            continue
        acceleration = [(row["wall_time_ms"] / 1000, tuple(row["values"])) for row in rows if row.get("sensor") == "accelerometer_mps2"]
        gyro = [(row["wall_time_ms"] / 1000, math.hypot(*row["values"])) for row in rows if row.get("sensor") == "gyroscope_rads"]
        gyro.sort()
        events = expo_detector(acceleration)
        sessions.append({"file": path.name, "events": events,
                         "features": event_features(events, [row[0] for row in gyro], [row[1] for row in gyro])})
    return sessions


def spearman(values_a, values_b):
    if len(values_a) < 3:
        return None
    def ranks(values):
        return [1 + sum(other < value for other in values) + (sum(other == value for other in values) - 1) / 2 for value in values]
    a, b = ranks(values_a), ranks(values_b)
    a_mean, b_mean = statistics.mean(a), statistics.mean(b)
    denominator = math.sqrt(sum((value - a_mean) ** 2 for value in a) * sum((value - b_mean) ** 2 for value in b))
    return sum((x - a_mean) * (y - b_mean) for x, y in zip(a, b)) / denominator if denominator else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    args = parser.parse_args()
    if not args.archive.is_file():
        raise SystemExit(f"Archive not found: {args.archive}")
    records = read_records(args.archive)
    hand = [record for record in records if record["location"] == "mobile_in_hand" and record["metrics"]["truth_steps"] > 0]
    by_location = {location: aggregate_metrics([record for record in records if record["location"] == location and record["metrics"]["truth_steps"] > 0])
                   for location in sorted({record["location"] for record in records})}

    # Five user-held-out folds prevent a user's repeated records from becoming
    # both training and test data.  This evaluates only already-detected events.
    users = sorted({record["user"] for record in hand})
    original_detector_missed = sum(record["metrics"]["false_negative"] for record in hand)
    handheld_truth_steps = sum(record["metrics"]["truth_steps"] for record in hand)
    feature_sets = {
        "peak_only": ("peak_margin",),
        "peak_interval": ("peak_margin", "interval_deviation"),
        "peak_interval_gyro": ("peak_margin", "interval_deviation", "gyro_relative_log"),
    }
    validation = {}
    for model_name, feature_names in feature_sets.items():
        fold_rows = []
        all_test_labels, all_test_probabilities = [], []
        for fold in range(5):
            test_users = [user for index, user in enumerate(users) if index % 5 == fold]
            train_records = [record for record in hand if record["user"] not in test_users]
            test_records = [record for record in hand if record["user"] in test_users]
            train_features = [feature for record in train_records for feature in record["features"]]
            test_features = [feature for record in test_records for feature in record["features"]]
            if not train_features or not test_features:
                continue
            model = train_logistic(train_features, feature_names)
            probabilities = predict(model, test_features, feature_names)
            labels = [feature["matched"] for feature in test_features]
            all_test_labels.extend(labels)
            all_test_probabilities.extend(probabilities.tolist())
            fold_rows.append({"fold": fold, "test_users": test_users, "events": len(labels), "precision": float(np.mean(labels)),
                              "auc": auc(labels, probabilities), "brier": float(np.mean((probabilities - np.asarray(labels)) ** 2))})
        threshold_metrics = {}
        labels_array, probabilities_array = np.asarray(all_test_labels), np.asarray(all_test_probabilities)
        for threshold in (0.5, 0.6, 0.7, 0.8, 0.9):
            accepted = probabilities_array >= threshold
            tp = int(np.sum((labels_array == 1) & accepted))
            fp = int(np.sum((labels_array == 0) & accepted))
            # Include true steps the original peak detector never emitted; a
            # confidence threshold cannot recover them.
            fn = original_detector_missed + int(np.sum((labels_array == 1) & ~accepted))
            threshold_metrics[str(threshold)] = f1({"true_positive": tp, "false_positive": fp, "false_negative": fn,
                                                    "truth_steps": handheld_truth_steps, "detected_events": int(np.sum(accepted))})
        validation[model_name] = {"features": feature_names, "folds": fold_rows, "events": len(all_test_labels),
                                  "eventMatchRate": float(np.mean(all_test_labels)), "auc": auc(all_test_labels, np.asarray(all_test_probabilities)),
                                  "brier": float(np.mean((np.asarray(all_test_probabilities) - np.asarray(all_test_labels)) ** 2)),
                                  "thresholdMetricsOutOfFold": threshold_metrics,
                                  "limit": "AUC evaluates false-positive discrimination among emitted events only. Missed ground-truth steps need a separate gap model."}

    full_model = train_logistic([feature for record in hand for feature in record["features"]], feature_sets["peak_interval_gyro"])
    local = local_events()
    local_rows = []
    for session in local:
        probabilities = predict(full_model, session["features"], feature_sets["peak_interval_gyro"])
        local_rows.append({"file": session["file"], "events": len(session["events"]),
                           "meanExternalHandProbability": float(np.mean(probabilities)),
                           "lowProbabilityFraction": float(np.mean(probabilities < 0.75)),
                           "medianProbability": float(np.median(probabilities)),
                           "externalModelSigmaEvents": float(math.sqrt(np.sum(probabilities * (1 - probabilities))),),
                           "retainedEventsByThreshold": {str(threshold): int(np.sum(probabilities >= threshold))
                                                             for threshold in (0.5, 0.6, 0.7, 0.8, 0.9)}})
    # The local endpoint distance is not used to train this model.  It is shown
    # only to test whether imported probability varies with known endpoint error.
    base = statistics.median([LOCAL_DISTANCE_M / row["events"] for row in local_rows])
    for row in local_rows:
        row["endpointErrorMetersDescriptive"] = abs(row["events"] * base - LOCAL_DISTANCE_M)
    correlation = spearman([row["lowProbabilityFraction"] for row in local_rows],
                           [row["endpointErrorMetersDescriptive"] for row in local_rows])
    # Personal calibration may use only previously completed routes.  This is
    # the same chronological split used for all local stride experiments.
    fresh_ids = ("170738", "170901", "171021", "171142")
    earlier = [row for row in local_rows if not any(token in row["file"] for token in fresh_ids)]
    newer = [row for row in local_rows if any(token in row["file"] for token in fresh_ids)]
    chronological_base = weighted_stride_base(earlier, "events")
    for row in earlier:
        row["chronologicalErrorMeters"] = abs(row["events"] * chronological_base - LOCAL_DISTANCE_M)
    multiplier = float(np.quantile([row["chronologicalErrorMeters"] / max(0.05, chronological_base * row["externalModelSigmaEvents"])
                                    for row in earlier], 0.8))
    transfer_trials = []
    for row in newer:
        error = abs(row["events"] * chronological_base - LOCAL_DISTANCE_M)
        radius = multiplier * chronological_base * row["externalModelSigmaEvents"]
        transfer_trials.append({"file": row["file"], "events": row["events"], "absoluteErrorMeters": error,
                                "radiusMeters": radius, "covered": error <= radius,
                                "meanExternalHandProbability": row["meanExternalHandProbability"],
                                "lowProbabilityFraction": row["lowProbabilityFraction"]})
    local_threshold_trials = {}
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9):
        count_key = f"threshold_{threshold}"
        threshold_rows = [{**row, count_key: row["retainedEventsByThreshold"][str(threshold)]} for row in local_rows]
        threshold_earlier = [row for row in threshold_rows if not any(token in row["file"] for token in fresh_ids)]
        threshold_newer = [row for row in threshold_rows if any(token in row["file"] for token in fresh_ids)]
        if any(row[count_key] == 0 for row in threshold_earlier + threshold_newer):
            continue
        threshold_base = weighted_stride_base(threshold_earlier, count_key)
        errors = [abs(row[count_key] * threshold_base - LOCAL_DISTANCE_M) for row in threshold_newer]
        local_threshold_trials[str(threshold)] = {"personalBaseMetersPerRetainedEvent": threshold_base,
                                                   "meanEndpointErrorMeters": float(np.mean(errors)),
                                                   "trials": [{"file": row["file"], "retainedEvents": row[count_key], "errorMeters": error}
                                                              for row, error in zip(threshold_newer, errors)]}
    result = {
        "purpose": "Analysis only: validate peak/interval/gyro event confidence against public foot-labelled steps, then inspect untrained transfer distribution on local 4F logs.",
        "archive": {"path": str(args.archive.relative_to(ROOT)), "sha256": sha256_file(args.archive),
                    "source": "https://gitlab.citius.gal/fernando.estevez/walking-recognition-dataset"},
        "detector": "Expo-equivalent: 20Hz downsample, magnitude gravity EMA tau=0.8s, peak >=1.0m/s², 280ms separation.",
        "truth": "Foot-sensor GT peak timestamps; ordered one-to-one event match within 250ms.",
        "records": {"all": len(records), "handheld": len(hand), "usersHandheld": len(users), "byLocation": by_location},
        "handheldUserHeldOut": validation,
        "local4FExternalModelTransfer": {"sessions": local_rows, "lowProbabilityVsEndpointErrorSpearmanDescriptive": correlation,
                                           "chronological11ToNew4Uncertainty": {
                                               "personalBaseMetersPerEvent": chronological_base, "targetCoverage": 0.8,
                                               "coverage": float(np.mean([row["covered"] for row in transfer_trials])),
                                               "meanRadiusMeters": float(np.mean([row["radiusMeters"] for row in transfer_trials])),
                                               "trials": transfer_trials},
                                           "externalThresholdExploration11ToNew4": local_threshold_trials,
                                           "limit": "No local event labels exist. This is a distribution/association check, not validation or a runtime model."},
        "decisionRule": "Do not apply unless handheld user-held-out discrimination is useful and the external score also predicts local held-out endpoint risk with a practical radius."
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": result["records"], "handheldUserHeldOut": result["handheldUserHeldOut"],
                      "local4FExternalModelTransfer": {"lowProbabilityVsEndpointErrorSpearmanDescriptive": correlation,
                                                          "chronological11ToNew4Uncertainty": result["local4FExternalModelTransfer"]["chronological11ToNew4Uncertainty"]}}, indent=2))


if __name__ == "__main__":
    main()
