"""Inspect RIDI trajectory axes before using its walking distance as a stride target."""
from __future__ import annotations

import csv
import io
import sys
import zipfile

import numpy as np


def main(archive_path: str) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        names = [
            item.filename for item in archive.infolist()
            if item.filename.endswith("/processed/data.csv") and "handheld" in item.filename
        ]
        # One file from each of three people is enough to identify the stable
        # vertical axis. This tool does not transform or export source data.
        selected = []
        seen = set()
        for name in sorted(names):
            subject = name.split("/")[1].split("_")[0]
            if subject not in seen:
                selected.append(name)
                seen.add(subject)
            if len(selected) == 3:
                break
        for name in selected:
            rows = csv.DictReader(io.StringIO(archive.read(name).decode("utf-8", errors="replace")))
            positions = np.array(
                [[float(row["pos_x"]), float(row["pos_y"]), float(row["pos_z"])] for row in rows],
                dtype=float,
            )
            extent = positions.max(axis=0) - positions.min(axis=0)
            delta = np.abs(np.diff(positions, axis=0)).sum(axis=0)
            print(name.split("/")[1])
            print("  coordinate extent (x, y, z) m:", np.round(extent, 3).tolist())
            print("  accumulated frame change (x, y, z) m:", np.round(delta, 3).tolist())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: inspect_ridi_axes.py <ridi zip>")
    main(sys.argv[1])
