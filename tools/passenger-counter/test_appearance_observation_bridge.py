import unittest
import numpy as np
from appearance_observation_bridge import AppearanceObservationBridge


class AppearanceContinuityTests(unittest.TestCase):
    full = (0, 0, 100, 400)
    partial = (10, 0, 90, 160)
    vector = [1., 0.]

    def test_short_gap_requires_three_observations_and_keeps_actual_partial(self):
        bridge = AppearanceObservationBridge()
        bridge.update([(1, self.full)], [self.vector], 0)
        for index in range(1, 3):
            self.assertEqual(bridge.update([(2, self.partial)], [self.vector], index * .03)[0][0], 2)
        self.assertEqual(bridge.update([(2, self.partial)], [self.vector], .09), [(1, self.partial)])
        self.assertEqual(len(bridge.audit), 1)

    def test_equal_appearance_candidates_are_ambiguous(self):
        bridge = AppearanceObservationBridge()
        bridge.update([(1, self.full), (3, self.full)], [self.vector, self.vector], 0)
        for index in range(1, 5):
            self.assertEqual(bridge.update([(2, self.partial)], [self.vector], index * .03)[0][0], 2)
        self.assertEqual(bridge.audit, [])

    def test_two_children_cannot_claim_one_parent(self):
        bridge = AppearanceObservationBridge()
        bridge.update([(1, self.full)], [self.vector], 0)
        for index in range(1, 5):
            output = bridge.update([(2, self.partial), (3, self.partial)], [self.vector, self.vector], index * .03)
            self.assertEqual({p for p, _ in output}, {2, 3})
        self.assertEqual(bridge.audit, [])

    def test_simultaneous_full_and_partial_do_not_alias_two_live_tracks(self):
        bridge = AppearanceObservationBridge()
        for index in range(5):
            output = bridge.update([(1, self.full), (2, self.partial)], [self.vector, self.vector], index * .03)
            self.assertEqual({p for p, _ in output}, {1, 2})

    def test_expired_parent_and_distant_geometry_are_not_reused(self):
        for box, start in [(self.partial, 1.), ((200, 0, 280, 160), .1)]:
            bridge = AppearanceObservationBridge()
            bridge.update([(1, self.full)], [self.vector], 0)
            for index in range(4):
                self.assertEqual(bridge.update([(2, box)], [self.vector], start + index * .03)[0][0], 2)
            self.assertEqual(bridge.audit, [])

    def test_invalid_features_are_rejected(self):
        for features in [[], [[2., 0.]], [[np.nan, 0.]], [1.]]:
            with self.assertRaises(ValueError):
                AppearanceObservationBridge().update([(1, self.full)], features, 0)

    def test_optional_simultaneous_merge_requires_strong_current_appearance(self):
        for cosine, should_merge in [(.84, False), (.9, True)]:
            bridge = AppearanceObservationBridge(simultaneous_partial=True)
            other = [cosine, np.sqrt(1 - cosine ** 2)]
            bridge.update([(1, self.full)], [self.vector], 0)
            for index in range(1, 4):
                output = bridge.update([(1, self.full), (2, self.partial)],
                                       [self.vector, other], index * .03)
            self.assertEqual(len(output), 1 if should_merge else 2)
            if should_merge:
                self.assertEqual(output, [(1, self.full)])

    def test_optional_policy_does_not_merge_non_nested_similar_neighbors(self):
        bridge = AppearanceObservationBridge(simultaneous_partial=True)
        distant = (90, 0, 170, 160)
        bridge.update([(1, self.full)], [self.vector], 0)
        for index in range(1, 5):
            output = bridge.update([(1, self.full), (2, distant)],
                                   [self.vector, self.vector], index * .03)
            self.assertEqual({p for p, _ in output}, {1, 2})


if __name__ == '__main__':
    unittest.main()
