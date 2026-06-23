"""Unit tests for split conformal interval utilities."""

from __future__ import annotations

import unittest

import numpy as np

from ml.price_modeling.conformal import build_prediction_interval, compute_conformal_quantile


class ConformalTests(unittest.TestCase):
    def test_quantile_and_clamped_interval(self) -> None:
        quantile = compute_conformal_quantile(
            np.array([100.0, 200.0, 300.0]), np.array([90.0, 220.0, 270.0])
        )
        lower, upper = build_prediction_interval(np.array([5.0, 200.0]), quantile)
        self.assertGreaterEqual(quantile, 0.0)
        self.assertEqual(lower[0], 0.0)
        self.assertTrue(np.all(lower <= np.array([5.0, 200.0])))
        self.assertTrue(np.all(upper >= np.array([5.0, 200.0])))

    def test_rejects_invalid_coverage_and_non_finite_calibration(self) -> None:
        with self.assertRaises(ValueError):
            compute_conformal_quantile(np.array([1.0]), np.array([1.0]), 1.0)
        with self.assertRaises(ValueError):
            compute_conformal_quantile(np.array([np.nan]), np.array([np.nan]))


if __name__ == "__main__":
    unittest.main()
