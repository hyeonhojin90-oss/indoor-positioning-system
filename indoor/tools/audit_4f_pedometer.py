"""Compare recorded iOS Pedometer counts with the current PDR peak detector.

Analysis only.  The Pedometer stream is already collected by App.js; this tool
does not modify PDR or alter source logs.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "indoor/tools"))
from experiment_advio_iphone_stride import detector  # noqa: E402


def paths(external: Path):
    yield from (ROOT / "indoor/data/raw/ios/2026-09-05").glob("*.jsonl")
    yield from (ROOT / "indoor/data/raw/ios/2026-09-08").glob("*.jsonl")
    yield from (ROOT / "indoor/data/raw/ios/2026-09-14").glob("*.jsonl")
    yield from (external / f"indoor_positioning_ios_20260914_{stamp}.jsonl"
                for stamp in ("133338", "133534", "133637", "133734"))


def read(path: Path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if rows[0].get("label", {}).get("route_id") not in {"4F_CORE_TO_RIGHT_STAIRS", "4F_CORE_TO_RIGHT_STAIRS_REVERSE"}:
        return None
    acceleration = [(row["wall_time_ms"] / 1000, tuple(row["values"])) for row in rows
                    if row.get("sensor") == "accelerometer_mps2"]
    pedometer = [row["values"][0] for row in rows if row.get("sensor") == "step_counter" and row.get("values")]
    events = detector(acceleration)
    return {"file": path.name, "peak_detector_events": len(events),
            "pedometer_first": pedometer[0] if pedometer else None,
            "pedometer_last": pedometer[-1] if pedometer else None,
            "pedometer_delta": pedometer[-1] - pedometer[0] if len(pedometer) >= 2 else None,
            "pedometer_max": max(pedometer) if pedometer else None,
            "pedometer_samples": len(pedometer)}


def summary(values):
    return {"count": len(values), "min": min(values), "max": max(values),
            "range": max(values) - min(values), "median": statistics.median(values),
            "stdev": statistics.pstdev(values)}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit_4f_pedometer.py <external 20260914 jsonl directory>")
    sessions = [row for path in paths(Path(sys.argv[1])) if path.exists() for row in [read(path)] if row]
    available = [row for row in sessions if row["pedometer_delta"] is not None]
    result = {
        "purpose": "Analysis only; compare existing native iOS Pedometer logs to PDR peak-detector events.",
        "sessions": sessions,
        "peak_detector_summary": summary([row["peak_detector_events"] for row in sessions]),
        "pedometer_delta_summary": summary([row["pedometer_delta"] for row in available]) if available else None,
        "pedometer_available_sessions": len(available),
        "limit": "Pedometer delta starts at its first recorded callback, so it is a stability diagnostic, not an endpoint distance truth.",
    }
    output = ROOT / "indoor/data/analysis/detailed-20260914/4f-pedometer-audit.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
