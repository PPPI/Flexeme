import itertools
import os
import time
from multiprocessing.pool import ThreadPool

import networkx as nx
import numpy as np

from confidence_voters.Util.voter_util import integer_distance_between_intervals, prefix_distance, call_graph_distance, \
    cluster_from_voter_affinity, generate_empty_affinity


def file_distance(graph, file_length_map):
    def voter(node, other):
        # Given two diff_regions, the number of lines between them by the number of total lines in file if same file
        # otherwise 1.
        if graph.nodes[node]['file'] != graph.nodes[other]['file']:
            return 1

        node_start, node_end = graph.nodes[node]["span"].split('-') \
            if '-' in graph.nodes[node]["span"] else [-1, -1]
        other_start, other_end = graph.nodes[other]["span"].split('-') \
            if '-' in graph.nodes[other]["span"] else [-1, -1]

        if node_start == -1 or other_start == -1:
            return 1

        distance = integer_distance_between_intervals([int(node_start), int(node_end)],
                                                      [int(other_start), int(other_end)])

        try:
            return distance / file_length_map[graph.nodes[node]['file']] \
                if file_length_map[graph.nodes[node]['file']] != -1 else 1
        except KeyError:
            return 1

    return voter


def namespace_distance(context):
    def voter(node, other):
        region1_nodes = {context[k] for k in [node] if k in context.keys()}
        region2_nodes = {context[k] for k in [other] if k in context.keys()}

        return min([prefix_distance(n, n_o) for n, n_o in itertools.product(region1_nodes, region2_nodes)], default=0)

    return voter


def change_coupling(graph, occurrence_matrix, file_index):
    # Zimmerman et al 2004
    # Given the matrix mapping commits to contains file (We assume this is from the training corpus in our case)
    # Filter to only columns that contain both
    # Sum along rows
    # the coupling is the min / max
    def voter(node, other):
        file1 = graph.nodes[node]['file']
        file2 = graph.nodes[other]['file']
        selected_idx = list()
        for i in range(occurrence_matrix.shape[1]):
            try:
                if occurrence_matrix[(file_index[file1], i)] and occurrence_matrix[(file_index[file2], i)]:
                    selected_idx.append(i)
            except KeyError:
                pass
        occurrence_profile = np.squeeze(np.asarray(occurrence_matrix[:, selected_idx].sum(axis=1)))
        try:
            file1_count = occurrence_profile[file_index[file1]]
            file2_count = occurrence_profile[file_index[file2]]
            return min(file1_count, file2_count) / max(file1_count, file2_count) \
                if max(file1_count, file2_count) > 0 else .0
        except KeyError:
            return .0

    return voter


def data_dependency(graph):
    graph = graph.copy()
    # Remove non-data-flow edges from graph
    # That is we keep only edges with key=1 for out graph format
    for edge in list(graph.edges(keys=True)):
        source, target, key = edge
        if key != 1:
            try:
                graph.remove_edge(source, target, key=key)
            except KeyError:
                pass

    def voter(node, other):
        # Are the regions reachable? (ignoring edge direction)
        # 1 if reachable, 0 otherwise
        for reachable_node in nx.dfs_postorder_nodes(graph, source=node):
            if reachable_node == other:
                return 1
        return 0

    return voter


def cluster_diffs(deltaPDG, context, concepts, file_length_map, occurrence_matrix, file_index_map, times):
    """
    :param deltaPDG: The deltaPDG we wish to untangle
    :param context: A mapping from node to method within which it exits
    :param concepts: The number of concepts we wish to segment
    :param file_length_map: A map between filename and file line count
    :param occurrence_matrix: The matrix mapping commits to files and vice versa
    :param file_index_map: The map between filenames and occurrence_matrix indices
    :return: The proposed clustering of diff_regions
    """
    try:
        data, _ = list(zip(*[(n, d['community']) for n, d in deltaPDG.nodes(data=True)
                             if 'color' in d.keys() and d['color'] != 'orange'
                             and 'community' in d.keys()]))
    except ValueError:
        return
    n = len(data)

    t0 = time.process_time()
    for i in range(times):
        voters = [
            file_distance(deltaPDG, file_length_map),
            call_graph_distance(deltaPDG, context),
            data_dependency(deltaPDG),
            namespace_distance(context),
            change_coupling(deltaPDG, occurrence_matrix, file_index_map),
        ]
        affinity, args = generate_empty_affinity(n, voters)
        with ThreadPool(processes=min(os.cpu_count() - 1, 12)) as wp:
            for k, value in wp.imap_unordered(lambda i: (i[1], i[0](data[i[-1][0]], data[i[-1][1]])), args):
                affinity[k] += value

        labels = cluster_from_voter_affinity(affinity, concepts)
    t1 = time.process_time()
    time_ = (t1 - t0) / times

    return labels, time_
