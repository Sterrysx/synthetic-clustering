import os
os.environ["OMP_NUM_THREADS"]        = "1"
os.environ["OPENBLAS_NUM_THREADS"]   = "1"
os.environ["MKL_NUM_THREADS"]        = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

import numpy as np
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from scipy.spatial.distance import cdist

def fit_kmeans(data, k, n_init=10):
    model  = KMeans(n_clusters=k, n_init=n_init, random_state=42)
    labels = model.fit_predict(data)
    return labels, model.cluster_centers_

def fit_hierarchical(data, k):
    model  = AgglomerativeClustering(n_clusters=k)
    labels = model.fit_predict(data)
    centers = np.array([data[labels == i].mean(axis=0) for i in range(k)])
    return labels, centers

def detect_optimal_k(data, method='kmeans', k_min=2, k_max=8):
    """Find optimal k via silhouette score in range [k_min, k_max]."""
    scaler = StandardScaler()
    data_scaled = scaler.fit_transform(data)

    best_k, best_score = k_min, -1.0
    for k in range(k_min, k_max + 1):
        try:
            if method == 'kmeans':
                labels, _ = fit_kmeans(data_scaled, k)
            else:
                labels, _ = fit_hierarchical(data_scaled, k)
            score = silhouette_score(data_scaled, labels)
            if score > best_score:
                best_score = score
                best_k     = k
        except Exception:
            continue
    return best_k

def calculate_quality_metrics(data, k, method='kmeans'):
    """Return (silhouette_score, mean_intra_cluster_distance)."""
    scaler      = StandardScaler()
    data_scaled = scaler.fit_transform(data)

    try:
        if method == 'kmeans':
            labels, centers = fit_kmeans(data_scaled, k)
        else:
            labels, centers = fit_hierarchical(data_scaled, k)

        sil  = silhouette_score(data_scaled, labels)
        dists = np.mean([
            np.mean(cdist(data_scaled[labels == i],
                          centers[i].reshape(1, -1)))
            for i in range(k)
            if np.any(labels == i)
        ])
        return float(sil), float(dists)
    except Exception:
        return 0.0, 0.0