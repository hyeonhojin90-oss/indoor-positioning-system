import unittest
import numpy as np
from lost_reid_guard import veto_lost, install


class LostAppearanceGuardTest(unittest.TestCase):
    def test_only_lost_and_known_mismatch_is_vetoed(self):
        costs = np.full((2, 3), .4)
        appearance = np.array([[.4, .1, np.nan], [.4, .1, np.nan]])
        result = veto_lost(costs, appearance, [True, False], .2)
        np.testing.assert_allclose(result, [[1, .4, .4], [.4, .4, .4]])
        np.testing.assert_allclose(costs, np.full((2, 3), .4))

    def test_invalid_feature_backend_rejected(self):
        with self.assertRaises(ValueError):
            install({'lost_reid_guard': True, 'person_model': 'model.onnx'})

if __name__ == '__main__':
    unittest.main()
