"""Auto-discover patterns by clustering pre-move feature vectors."""

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


def discover_patterns(vectors: list, feature_keys: list, min_occurrences: int,
                      max_k: int = 6) -> list:
    if len(vectors) < 2 * min_occurrences:
        return []
    X = np.array([[v.get(k, 0.0) for k in feature_keys] for v in vectors], dtype=float)
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)

    best_k, best_score, best_labels = None, -1.0, None
    for k in range(2, min(max_k, len(vectors) // min_occurrences) + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(Xs)
        try:
            score = silhouette_score(Xs, km.labels_)
        except ValueError:
            continue
        if score > best_score:
            best_k, best_score, best_labels = k, score, km.labels_
    if best_labels is None:
        return []

    scaler_dict = {"mean": {feature_keys[i]: float(scaler.mean_[i])
                            for i in range(len(feature_keys))},
                   "std": {feature_keys[i]: float(scaler.scale_[i])
                           for i in range(len(feature_keys))}}

    patterns = []
    for cluster in range(best_k):
        idx = np.where(best_labels == cluster)[0]
        if len(idx) < min_occurrences:
            continue
        centroid = X[idx].mean(axis=0)
        # dominant features = top-2 by absolute standardized magnitude
        zc = Xs[idx].mean(axis=0)
        top = sorted(range(len(feature_keys)), key=lambda i: abs(zc[i]), reverse=True)[:2]
        tag = "_".join(feature_keys[i][:6] for i in top)
        patterns.append({
            "name": f"disc_{tag}_{cluster}",
            "n": int(len(idx)),
            "centroid": {feature_keys[i]: round(float(centroid[i]), 4)
                         for i in range(len(feature_keys))},
            "member_indices": idx.tolist(),
            "dominant_features": [feature_keys[i] for i in top],
            "scaler": scaler_dict,
        })
    return patterns


def assign_to_centroids(vectors: list, centroids: list, feature_keys: list,
                        scaler: dict, max_dist: float) -> list:
    """Assign each vector to the nearest centroid in standardized space, or None if
    beyond max_dist. scaler = {'mean': {feat: m}, 'std': {feat: s}} from training."""
    mean = scaler["mean"]
    std = scaler["std"]

    def standardize(d):
        return np.array([(d.get(k, 0.0) - mean[k]) / (std[k] or 1.0)
                         for k in feature_keys])

    cs = [standardize(c) for c in centroids]
    out = []
    for v in vectors:
        sv = standardize(v)
        dists = [float(np.linalg.norm(sv - c)) for c in cs]
        j = int(np.argmin(dists))
        out.append(j if dists[j] <= max_dist else None)
    return out
