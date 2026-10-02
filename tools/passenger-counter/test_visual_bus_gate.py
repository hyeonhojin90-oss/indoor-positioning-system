import unittest
import numpy as np
import cv2
from visual_bus_gate import BusVisualFallback


class VisualTests(unittest.TestCase):
    def setUp(self):
        self.frame=np.random.default_rng(42).integers(0,256,(180,240,3),dtype=np.uint8)
    def test_stationary_vehicle_is_bounded_and_cannot_acquire_without_detector(self):
        gate=BusVisualFallback(max_gap=.2)
        self.assertIsNone(gate.update(self.frame,[],0))
        self.assertIsNone(gate.update(self.frame,[(20,20,220,160)],0))
        self.assertIsNotNone(gate.update(self.frame,[],.1))
        self.assertIsNone(gate.update(self.frame,[],.3))
    def test_black_loss_rejected(self):
        gate=BusVisualFallback();gate.update(self.frame,[(20,20,220,160)],0)
        self.assertIsNone(gate.update(np.zeros_like(self.frame),[],.1))
    def test_coherent_translation_updates_vehicle_coordinates(self):
        gate=BusVisualFallback();gate.update(self.frame,[(20,20,220,160)],0)
        shifted=cv2.warpAffine(self.frame,np.float32([[1,0,3],[0,1,2]]),(240,180))
        box=gate.update(shifted,[],.1)
        self.assertIsNotNone(box)
        self.assertAlmostEqual(box[0],23,delta=.5);self.assertAlmostEqual(box[1],22,delta=.5)
