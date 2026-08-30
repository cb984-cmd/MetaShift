"""Deterministic event-level metrics and cluster bootstrap utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class ClassificationMetrics:
    """Binary local-versus-regional classification metrics."""

    average_precision: float
    macro_f1: float
    precision: float
    recall: float
    false_positive_rate: float
    coverage: float
    threshold: float


def average_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    """Compute average precision for binary labels without external ML packages."""

    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(scores, dtype=float)
    valid = np.isfinite(scores)
    labels = labels[valid]
    scores = scores[valid]
    if len(labels) == 0 or not np.isin(labels, [0, 1]).all():
        raise ValueError("Labels must contain finite binary-scored observations.")
    positives = int(labels.sum())
    if positives == 0:
        raise ValueError("Average precision requires at least one positive label.")
    order = np.argsort(-scores, kind="stable")
    ranked = labels[order]
    precision = np.cumsum(ranked) / np.arange(1, len(ranked) + 1)
    return float((precision * ranked).sum() / positives)


def classification_metrics(
    labels: np.ndarray, scores: np.ndarray, threshold: float
) -> ClassificationMetrics:
    """Calculate metrics after treating scores below threshold as regional."""

    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(scores, dtype=float)
    valid = np.isfinite(scores)
    if not valid.any():
        raise ValueError("No finite scores are available.")
    actual = labels[valid]
    predicted = (scores[valid] >= threshold).astype(int)
    if not np.isin(actual, [0, 1]).all():
        raise ValueError("Labels must be binary.")

    true_positive = int(((predicted == 1) & (actual == 1)).sum())
    false_positive = int(((predicted == 1) & (actual == 0)).sum())
    true_negative = int(((predicted == 0) & (actual == 0)).sum())
    false_negative = int(((predicted == 0) & (actual == 1)).sum())
    positive_precision = true_positive / max(true_positive + false_positive, 1)
    positive_recall = true_positive / max(true_positive + false_negative, 1)
    positive_f1 = (
        2 * positive_precision * positive_recall
        / max(positive_precision + positive_recall, 1e-12)
    )
    negative_precision = true_negative / max(true_negative + false_negative, 1)
    negative_recall = true_negative / max(true_negative + false_positive, 1)
    negative_f1 = (
        2 * negative_precision * negative_recall
        / max(negative_precision + negative_recall, 1e-12)
    )
    return ClassificationMetrics(
        average_precision=average_precision(actual, scores[valid]),
        macro_f1=(positive_f1 + negative_f1) / 2,
        precision=positive_precision,
        recall=positive_recall,
        false_positive_rate=false_positive / max(false_positive + true_negative, 1),
        coverage=float(valid.mean()),
        threshold=float(threshold),
    )


def select_macro_f1_threshold(labels: np.ndarray, scores: np.ndarray) -> float:
    """Pick a deterministic threshold only on a calibration partition."""

    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(scores, dtype=float)
    valid_scores = np.unique(scores[np.isfinite(scores)])
    if len(valid_scores) == 0:
        raise ValueError("Cannot select a threshold from no finite scores.")
    candidates = np.r_[
        np.nextafter(valid_scores[0], -np.inf),
        valid_scores,
        np.nextafter(valid_scores[-1], np.inf),
    ]
    ranked = [
        (classification_metrics(labels, scores, float(threshold)).macro_f1, threshold)
        for threshold in candidates
    ]
    # Prefer the higher threshold in exact ties to control regional false positives.
    return float(max(ranked, key=lambda item: (item[0], item[1]))[1])


def cluster_bootstrap_difference(
    cluster_ids: np.ndarray,
    values_a: np.ndarray,
    values_b: np.ndarray,
    statistic: Callable[[np.ndarray], float] = np.mean,
    *,
    repetitions: int = 1_000,
    seed: int = 20260830,
) -> tuple[float, float, float]:
    """Bootstrap a paired A-minus-B statistic by resampling whole event clusters."""

    cluster_ids = np.asarray(cluster_ids)
    values_a = np.asarray(values_a, dtype=float)
    values_b = np.asarray(values_b, dtype=float)
    valid = np.isfinite(values_a) & np.isfinite(values_b)
    cluster_ids = cluster_ids[valid]
    differences = values_a[valid] - values_b[valid]
    unique_clusters = np.unique(cluster_ids)
    if len(unique_clusters) < 2:
        raise ValueError("At least two clusters are required for bootstrap.")
    rng = np.random.default_rng(seed)
    cluster_values = {
        cluster: differences[cluster_ids == cluster] for cluster in unique_clusters
    }
    samples = []
    for _ in range(repetitions):
        sampled_clusters = rng.choice(unique_clusters, size=len(unique_clusters), replace=True)
        sampled = np.concatenate([cluster_values[cluster] for cluster in sampled_clusters])
        samples.append(float(statistic(sampled)))
    point = float(statistic(differences))
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return point, float(lower), float(upper)


def metrics_as_dict(metrics: ClassificationMetrics) -> dict[str, float]:
    """Serialize metrics explicitly for CSV and JSON outputs."""

    return {key: float(value) for key, value in asdict(metrics).items()}
