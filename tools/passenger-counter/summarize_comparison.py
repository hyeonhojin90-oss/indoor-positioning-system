"""Summarize observed runs, without treating derived clips as held-out accuracy."""
import json
from pathlib import Path


def main():
    cases = [
        ('bus-multiscale-001', 'original, calibrated', 1, 0),
        ('bus-shift-multiscale', 'translated derivative', 1, 0),
        ('bus-reverse', 'reversed derivative', 0, 1),
        ('bus-stationary', 'stationary derivative', 0, 0),
        ('bus-grounding-003', 'original, calibrated', 1, 0),
        ('bus-shift-grounding', 'translated derivative', 1, 0),
        ('bus-stationary-grounding', 'stationary derivative, first 20 frames', 0, 0),
        ('cascade-original-001', 'original, calibrated', 1, 0),
        ('cascade-shift-001', 'translated derivative', 1, 0),
        ('cascade-original-aspect-001', 'original, calibrated, vertical-door filter', 1, 0),
        ('cascade-shift-aspect-001', 'translated derivative, vertical-door filter', 1, 0),
        ('cascade-wiki-001', 'separate moving-bus scene, original gates, qualitative one boarding', 1, 0),
    ]
    rows = []
    for name, kind, entering, leaving in cases:
        path = Path('runs') / name / 'summary.json'
        if not path.exists():
            rows.append({'run': name, 'status': 'not completed'})
            continue
        result = json.loads(path.read_text(encoding='utf-8'))
        expected = {'in': entering, 'out': leaving}
        active = result['active_door_frames']
        rows.append({'run': name, 'kind': kind, 'frames': result['frames'],
                     'active_door_frames': active, 'counts': result['counts'],
                     'expected': expected,
                     'count_check_with_active_door': active > 0 and result['counts'] == expected,
                     'cpu_fps_observed': result['processed_fps_including_render'],
                     'detector_calls': result.get('door_detector_calls'),
                     'cascade_stats': result.get('cascade_stats')})
    report = {'independent_accuracy_validated': False, 'jetson_validated': False,
              'notes': ['Gates calibrated on original clip; derivatives share its scene.',
                        'Stationary count is inconclusive when door never becomes active.',
                        'Separate Wikimedia scene shows a visible boarding but count fails; moving bus and camera geometry differ.',
                        'Some CPU runs overlapped; throughput is not a controlled hardware benchmark.'],
              'runs': rows}
    text = json.dumps(report, indent=2)
    Path('runs/model-comparison-summary.json').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
