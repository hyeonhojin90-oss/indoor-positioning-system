import unittest
import numpy as np
from osnet_preprocessing import observed_crops


class ObservedFeaturePreprocessingTests(unittest.TestCase):
    def test_bgr_to_rgb_and_author_normalization(self):
        frame = np.zeros((20, 10, 3), np.uint8)
        frame[:, :, 2] = 255
        inputs = observed_crops(frame, [[0, 0, 10, 20]])
        self.assertEqual(tuple(inputs.shape), (1, 3, 256, 128))
        np.testing.assert_allclose(inputs[0, :, 50, 50].numpy(),
                                   [(1 - .485) / .229, -.456 / .224, -.406 / .225], atol=1e-6)

    def test_multiple_actual_crops_keep_order(self):
        frame = np.zeros((10, 20, 3), np.uint8)
        frame[:, 10:] = 255
        inputs = observed_crops(frame, [[0, 0, 10, 10], [10, 0, 20, 10]])
        self.assertTrue(bool((inputs[0] < inputs[1]).all()))

    def test_empty_input_and_boundary_clamp(self):
        frame = np.zeros((10, 10, 3), np.uint8)
        self.assertEqual(tuple(observed_crops(frame, []).shape), (0, 3, 256, 128))
        self.assertEqual(tuple(observed_crops(frame, [[-5, -5, 15, 15]]).shape), (1, 3, 256, 128))

    def test_invalid_crops_and_non_bgr_images_are_rejected(self):
        frame = np.zeros((10, 10, 3), np.uint8)
        for boxes in [[[0, 0, 3, 10]], [[20, 20, 30, 30]], [[0, 0, np.nan, 10]], [[4, 0, 1, 10]]]:
            with self.assertRaises(ValueError):
                observed_crops(frame, boxes)
        for invalid in [frame.astype(float), frame[:, :, 0]]:
            with self.assertRaises(ValueError):
                observed_crops(invalid, [])


if __name__ == '__main__':
    unittest.main()
