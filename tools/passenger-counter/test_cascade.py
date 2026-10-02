import unittest
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(__file__).resolve().parent/'runs'/'settings'))
import numpy as np
import torch
from ultralytics.engine.results import Results
from cascade_detector import CascadeDoorDetector


FRAME = np.zeros((100, 100, 3), dtype=np.uint8)


class Detector:
    provenance = {'test': True}

    def __init__(self, box):
        self.box = box
        self.calls = 0
        self.confidence = .9

    def predict(self, frame, **kwargs):
        self.calls += 1
        boxes = self.box if self.box and isinstance(self.box[0], list) else ([self.box] if self.box else [])
        rows = [box + [self.confidence, 0] for box in boxes]
        return [Results(frame, path='', names={0: 'door'},
                        boxes=torch.tensor(rows).reshape(-1, 6))]


class CascadeTests(unittest.TestCase):
    def test_runtime_filter_is_applied_before_reference_choice(self):
        reference=Detector([[0,0,20,80],[60,0,80,80]])
        detector=CascadeDoorDetector(Detector(None),reference)
        r=detector.predict(FRAME,candidate_filter=lambda b:b[0]>50)[0]
        self.assertEqual(r.boxes.xyxy.tolist(),[[60,0,80,80]])

    def test_runtime_selector_can_choose_second_reference_door(self):
        reference=Detector([[0,0,20,80],[60,0,80,80]])
        detector=CascadeDoorDetector(Detector(None),reference)
        r=detector.predict(FRAME,candidate_selector=lambda boxes:1)[0]
        self.assertEqual(r.boxes.xyxy.tolist(),[[60,0,80,80]])
    def test_weak_reference_can_only_confirm_same_locked_door(self):
        reference=Detector([10,10,40,90])
        reference.confidence=.28
        detector=CascadeDoorDetector(Detector(None),reference,associated_conf=.25)
        self.assertEqual(len(detector.predict(FRAME)[0].boxes),0)
        self.assertEqual(len(detector.predict(FRAME,locked_box=[10,10,40,90])[0].boxes),1)
        reference.box=[60,10,90,90]
        self.assertEqual(len(detector.predict(FRAME,locked_box=[10,10,40,90])[0].boxes),0)

    def test_weak_reference_below_floor_cannot_refresh(self):
        reference=Detector([10,10,40,90]); reference.confidence=.2
        detector=CascadeDoorDetector(Detector(None),reference,associated_conf=.25)
        self.assertEqual(len(detector.predict(FRAME,locked_box=[10,10,40,90])[0].boxes),0)

    def test_strong_displaced_reference_still_invalidates_lock(self):
        reference=Detector([60,10,90,90])
        detector=CascadeDoorDetector(Detector(None),reference,associated_conf=.25)
        result=detector.predict(FRAME,locked_box=[10,10,40,90])[0]
        self.assertEqual(result.boxes.xyxy.tolist(),[[60,10,90,90]])

    def test_wide_bus_candidate_does_not_acquire_door(self):
        reference = Detector([[0,20,95,55], [10,10,40,90]])
        detector = CascadeDoorDetector(Detector(None), reference, min_aspect=1)
        result = detector.predict(FRAME)[0]
        self.assertEqual(result.boxes.xyxy.tolist(), [[10,10,40,90]])

    def test_reference_acquisition_and_bounded_refresh(self):
        primary, reference = Detector([10,10,40,90]), Detector([10,10,40,90])
        detector = CascadeDoorDetector(primary, reference, refresh_calls=2)
        for _ in range(4):
            detector.predict(FRAME)
        self.assertEqual((primary.calls, reference.calls), (2, 2))

    def test_displaced_primary_cannot_keep_old_door(self):
        primary, reference = Detector([60,10,90,90]), Detector([10,10,40,90])
        detector = CascadeDoorDetector(primary, reference)
        detector.predict(FRAME)
        reference.box = [60,10,90,90]
        result = detector.predict(FRAME)[0]
        self.assertEqual(reference.calls, 2)
        self.assertEqual(result.boxes.xyxy.tolist(), [[60,10,90,90]])

    def test_missing_reference_clears_geometry(self):
        primary, reference = Detector(None), Detector([10,10,40,90])
        detector = CascadeDoorDetector(primary, reference)
        detector.predict(FRAME)
        reference.box = None
        self.assertEqual(len(detector.predict(FRAME)[0].boxes), 0)
        self.assertIsNone(detector.box)


if __name__ == '__main__':
    unittest.main()
