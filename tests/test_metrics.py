import unittest

import numpy as np

from metashift.metrics import (
    classification_metrics,
    cluster_bootstrap_difference,
    select_macro_f1_threshold,
)


class MetricTests(unittest.TestCase):
    def test_metrics_recognize_separable_labels(self) -> None:
        labels = np.array([0, 0, 1, 1])
        scores = np.array([0.1, 0.2, 0.8, 0.9])
        threshold = select_macro_f1_threshold(labels, scores)
        metrics = classification_metrics(labels, scores, threshold)
        self.assertEqual(metrics.average_precision, 1.0)
        self.assertEqual(metrics.macro_f1, 1.0)
        self.assertEqual(metrics.false_positive_rate, 0.0)

    def test_cluster_bootstrap_preserves_paired_difference(self) -> None:
        point, lower, upper = cluster_bootstrap_difference(
            np.array(["a", "a", "b", "b"]),
            np.array([3.0, 3.0, 4.0, 4.0]),
            np.array([1.0, 1.0, 2.0, 2.0]),
            repetitions=100,
            seed=1,
        )
        self.assertEqual(point, 2.0)
        self.assertLessEqual(lower, point)
        self.assertGreaterEqual(upper, point)
