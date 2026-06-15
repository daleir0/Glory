import numpy as np
from glory_hype.patterns.discover import assign_to_centroids

FEATS = ["a", "b"]


def test_assigns_near_and_rejects_far():
    centroids = [{"a": 0.0, "b": 0.0}, {"a": 10.0, "b": 10.0}]
    scaler = {"mean": {"a": 5.0, "b": 5.0}, "std": {"a": 5.0, "b": 5.0}}
    vectors = [{"a": 0.2, "b": -0.1},     # near centroid 0
               {"a": 9.8, "b": 10.2},     # near centroid 1
               {"a": 100.0, "b": 100.0}]  # far from both -> unassigned
    labels = assign_to_centroids(vectors, centroids, FEATS, scaler, max_dist=2.5)
    assert labels[0] == 0
    assert labels[1] == 1
    assert labels[2] is None
