"""
Optimal Number of Clusters (ONC Algorithm)
"""

from typing import Union

import numpy as np
import pandas as pd

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_samples


def get_clusters_quality_scores(clusters:dict, scores:np.array) -> dict:
    """
    Calculates clusters quality scores

    :param clusters: (dict) clusters elements
    :param scores: (np.array) scores for each element of cluster
    :return: (dict) Cluster quality scores
    """
    return {i: np.mean(scores[clusters[i]]) / np.std(scores[clusters[i]]) for i in clusters.keys()}


def _improve_clusters(corr_mat, clusters, top_clusters):
    clusters_new, new_idx = {}, []
    for i in clusters.keys():
        clusters_new[len(clusters_new.keys())] = list(clusters[i])

    for i in top_clusters.keys():
        clusters_new[len(clusters_new.keys())] = list(top_clusters[i])

    map(new_idx.extend, clusters_new.values())
    corr_new = corr_mat.loc[new_idx, new_idx]

    dist = ((1 - corr_mat.fillna(0)) / 2.0) ** 0.5

    kmeans_labels = np.zeros(len(dist.columns))
    for i in clusters_new.keys():
        idxs = [dist.index.get_loc(k) for k in clusters_new[i]]
        kmeans_labels[idxs] = i

    silh_scores_new = pd.Series(silhouette_samples(dist, kmeans_labels), index=dist.index)
    return corr_new, clusters_new, silh_scores_new


def _cluster_kmeans_base(corr_mat:pd.DataFrame, max_num_clusters:int=10, repeat:int=10) -> Union[pd.DataFrame, dict, pd.Series]:
    """
    Initial clustering step using KMeans.

    :param corr_mat: (pd.DataFrame) correlation matrix
    :param max_num_clusters: maximum number of cluster to search for.
    :param repeat: number of clustering algorithm repetitions.
    :return: 3 tuple (ordered correlation matrix, clusters, silh scores)
    """

    # Distance matrix
    distance = ((1 - corr_mat.fillna(0)) / 2.0) ** 0.5

    silh = pd.Series()

    # Get optimal num clusters
    for init in range(repeat):
        for num_clusters in range(2, max_num_clusters + 1):
            kmeans_ = KMeans(n_clusters=num_clusters, n_jobs=1, n_init=1)
            kmeans_ = kmeans_.fit(distance)
            silh_ = silhouette_samples(distance, kmeans_.labels_)
            stat = (silh_.mean() / silh_.std(), silh.mean() / silh.std())

            if np.isnan(stat[1]) or stat[0] > stat[1]:
                silh = silh_
                kmeans = kmeans_

    # Number of clusters equals to length(kmeans labels)
    new_idx = np.argsort(kmeans.labels_)

    # Reorder rows
    corr1 = corr_mat.iloc[new_idx]
    # Reorder columns
    corr1 = corr1.iloc[:, new_idx]

    # Cluster members
    clusters = {i: corr_mat.columns[np.where(kmeans.labels_ == i)[0]].tolist() for i in
                np.unique(kmeans.labels_)}
    silh = pd.Series(silh, index=distance.index)

    return corr1, clusters, silh


def cluster_kmeans_top(corr_mat:pd.DataFrame, repeat:int=10) -> Union[pd.DataFrame, dict, pd.Series]:
    """
    Improve the initial clustering by leaving clusters with high scores unchanged and modifying clusters with
    below average scores.

    :param corr_mat: (pd.DataFrame) correlation matrix
    :param repeat: number of clustering algorithm repetitions.
    :return: 3 tuple (correlation matrix, optimized clusters, silh scores)
    """
    max_num_clusters = corr_mat.shape[1] - 1
    corr1, clusters, silh = _cluster_kmeans_base(corr_mat, max_num_clusters=max_num_clusters, repeat=repeat)

    # Get cluster quality scores
    cluster_quality = {i: np.mean(silh[clusters[i]]) / np.std(silh[clusters[i]]) for i in clusters.keys()}
    avg_quality = np.mean(list(cluster_quality.values()))
    redo_clusters = [i for i in cluster_quality.keys() if cluster_quality[i] < avg_quality]

    if len(redo_clusters) <= 2:
        # If 2 or less clusters have a quality rating less than the average then stop.
        return corr1, clusters, silh
    else:

        keys_redo = []
        for i in redo_clusters:
            keys_redo.extend(clusters[i])

        corr_tmp = corr_mat.loc[keys_redo, keys_redo]
        mean_redo_tstat = np.mean([cluster_quality[i] for i in redo_clusters])
        corr2, top_clusters, silh_score_2 = cluster_kmeans_top(corr_tmp, repeat=repeat)

        # Make new clusters (improved)
        corr_new, clusters_new, silh_new = _improve_clusters(corr_mat,
                                                             {i: clusters[i] for i in clusters.keys() if
                                                              i not in redo_clusters},
                                                             top_clusters)
        new_tstat_mean = np.mean(
            [np.mean(silh_new[clusters_new[i]]) / np.std(silh_new[clusters_new[i]]) for i in clusters_new.keys()])

        if new_tstat_mean <= mean_redo_tstat:
            return corr1, clusters, silh, cluster_quality
        else:
            return corr_new, clusters_new, silh_new


def onc_cluster(corr_mat:pd.DataFrame, repeat:int=10) -> Union[pd.DataFrame, dict, pd.Series]:
    """
    ONC algorithm (Optimal Number of Clusters) using correlation matrix of features.

    :param corr_mat: (pd.DataFrame) correlation matrix of features
    :param repeat (int): number of clustering algorithm repetitions.
    :return: 3 tuple (correlation matrix, optimized clusters, silh scores)
    """

    return cluster_kmeans_top(corr_mat, repeat)