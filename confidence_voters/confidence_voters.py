import itertools
import os
import time
from multiprocessing.pool import ThreadPool

import networkx as nx
import numpy as np

from confidence_voters.Util.voter_util import integer_distance_between_intervals, prefix_distance, call_graph_distance, \
    cluster_from_voter_affinity, generate_empty_affinity
from deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx, get_context_from_nxgraph


def file_distance(file_length_map):
    def voter(diff_region1, diff_region2):
        # Given two diff_regions, the number of lines between them by the number of total lines in file if same file
        # otherwise 1.
        if diff_region1['file'] != diff_region2['file']:
            return 1

        if diff_region1['span_before']['start'] == -1:
            span1 = 'span_after'
        else:
            span1 = 'span_before'
        if diff_region2['span_before']['start'] == -1:
            span2 = 'span_after'
        else:
            span2 = 'span_before'

        if span1 != span2:
            return 1

        distance = integer_distance_between_intervals([diff_region1[span1]['start'], diff_region1[span1]['end']],
                                                      [diff_region2[span2]['start'], diff_region2[span2]['end']])

        try:
            return distance / file_length_map[diff_region1['file']] if file_length_map[diff_region1['file']] != -1 \
                else 1
        except KeyError:
            return 1

    return voter


def namespace_distance(graph, context):
    graph = graph.copy()

    def voter(diff_region1, diff_region2):
        # Get the nodes representing each diff-region
        region1_nodes = list()
        region2_nodes = list()
        for node, data in graph.nodes(data=True):
            if 'color' in data.keys() and data['color'] == 'green':
                span = 'span_after'
            else:
                span = 'span_before'
            start, end = [int(n) for n in data['span'].split('-')] \
                if 'span' in data.keys() and '-' in data['span'] else [-1, -1]
            if start <= diff_region1[span]['start'] - 1 <= end or start <= diff_region1[span]['end'] - 1 <= end:
                region1_nodes.append(node)
            if start <= diff_region2[span]['start'] - 1 <= end or start <= diff_region2[span]['end'] - 1 <= end:
                region2_nodes.append(node)

        region1_nodes = {context[k] for k in region1_nodes if k in context.keys()}
        region2_nodes = {context[k] for k in region2_nodes if k in context.keys()}

        return min([prefix_distance(n, n_o) for n, n_o in itertools.product(region1_nodes, region2_nodes)], default=0)

    return voter


def change_coupling(occurrence_matrix, file_index):
    # Zimmerman et al 2004
    # Given the matrix mapping commits to contains file (We assume this is from the training corpus in our case)
    # Filter to only columns that contain both
    # Sum along rows
    # the coupling is the min / max
    def voter(diff_region1, diff_region2):
        file1 = diff_region1['file']
        file2 = diff_region2['file']
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

    def voter(diff_region1, diff_region2):
        # Get the nodes representing each diff-region
        region1_nodes = list()
        region2_nodes = list()
        for node, data in graph.nodes(data=True):
            if 'color' in data.keys() and data['color'] == 'green':
                span = 'span_after'
            else:
                span = 'span_before'
            start, end = [int(n) for n in data['span'].split('-')] \
                if 'span' in data.keys() and '-' in data['span'] else [-1, -1]
            if start <= diff_region1[span]['start'] <= end or start <= diff_region1[span]['end'] <= end:
                region1_nodes.append(node)
            if start <= diff_region2[span]['start'] <= end or start <= diff_region2[span]['end'] <= end:
                region2_nodes.append(node)

        # Are the regions reachable? (ignoring edge direction)
        # 1 if reachable, 0 otherwise
        for node in region1_nodes:
            for reachable_node in nx.dfs_postorder_nodes(graph, source=node):
                if reachable_node in region2_nodes:
                    return 1
        return 0

    return voter


def confidence_aggregator(voters, data):
    def aggregator(indexs):
        result = np.zeros(shape=(len(data), len(data)))
        for diff_region_idx1, diff_region_idx2 in itertools.product(indexs, indexs):
            if diff_region_idx1[0] >= diff_region_idx2[0]:
                diff_region1 = data[diff_region_idx1[0]]
                diff_region2 = data[diff_region_idx2[0]]
                distance = sum(map(lambda v: v(diff_region1, diff_region2), voters))
                result[diff_region_idx1[0]][diff_region_idx2[0]] = distance
                if diff_region_idx1[0] != diff_region_idx2[0]:
                    result[diff_region_idx2[0]][diff_region_idx1[0]] = distance
        return result

    return aggregator


def cluster_diffs(concepts, data, graph_location, file_length_map, occurrence_matrix, file_index_map, times,
                  edges_kept=None, use_file_dist=True, use_call_distance=True, use_data=True, use_namespace=True,
                  use_change_coupling=True):
    """
    :param concepts: The number of concepts we wish to segment
    :param data: The initial diff-regions segmentation, each it's own group
    :param graph_location: The location of the dot file representing the deltaPDG of the file
    :param file_length_map: A map between filename and file line count
    :param occurrence_matrix: The matrix mapping commits to files and vice versa
    :param file_index_map: The map between filenames and occurrence_matrix indices
    :return: The proposed clustering of diff_regions
    """
    deltaPDG = obj_dict_to_networkx(read_graph_from_dot(graph_location))
    if edges_kept is not None:
        deltaPDG = remove_all_except(deltaPDG, edges_kept)
    context = get_context_from_nxgraph(deltaPDG)
    voters = [
        file_distance(file_length_map) if use_file_dist else None,
        call_graph_distance(deltaPDG, context) if use_call_distance else None,
        data_dependency(deltaPDG) if use_data else None,
        namespace_distance(deltaPDG, context) if use_namespace else None,
        change_coupling(occurrence_matrix, file_index_map) if use_change_coupling else None,
    ]
    voters = [v for v in voters if v is not None]

    n = len(data)

    t0 = time.process_time()
    for i in range(times):
        affinity, args = generate_empty_affinity(n, voters)
        with ThreadPool(processes=min(os.cpu_count() - 1, 6)) as wp:
            for k, value in wp.imap_unordered(lambda i: (i[1], i[0](data[i[-1][0]], data[i[-1][1]])), args):
                affinity[k] += value

        labels = cluster_from_voter_affinity(affinity, concepts)
    t1 = time.process_time()
    time_ = (t1 - t0) / times

    return labels, time_


def remove_all_except(graph, edge_kind):
    if edge_kind == 'data':
        target_kind = ['1']
    elif edge_kind == 'name':
        target_kind = ['3']
    elif edge_kind == 'control':
        target_kind = ['0']
    elif edge_kind == 'dataname':
        target_kind = ['1', '3']
    elif edge_kind == 'datacontrol':
        target_kind = ['1', '0']
    elif edge_kind == 'controlname':
        target_kind = ['3', '0']
    else:
        target_kind = ['0', '1', '2', '3']

    graph = graph.copy()
    for edge in list(graph.edges(keys=True)):
        source, target, key = edge
        if key not in target_kind:
            try:
                graph.remove_edge(source, target, key=key)
            except KeyError:
                pass

    return graph


def convert_diff_to_diff_regions(diff, line_level=False):
    additions = [ch for ch in diff if ch[0] == '+']
    deletions = [ch for ch in diff if ch[0] == '-']
    result = list()

    if len(additions) > 0:
        type_, file, line_no, _, line, label = additions[0]
        previous = {'type': type_,
                    'file': file,
                    'span_after': {'start': line_no,
                                   'end': line_no, },
                    'span_before': {'start': -1,
                                    'end': -1, },
                    'line': line,
                    'label': label,
                    }
        for type_, file, line_no, _, line, label in additions[1:]:
            if not line_level \
                    and line_no - previous['span_after']['end'] == 1 \
                    and file == previous['file'] and label == previous['label']:
                previous['line'] += '\n' + line
                previous['span_after']['end'] = line_no
            else:
                result.append(previous)
                previous = {'type': type_,
                            'file': file,
                            'span_after': {'start': line_no,
                                           'end': line_no, },
                            'span_before': {'start': -1,
                                            'end': -1, },
                            'line': line,
                            'label': label,
                            }

    if len(deletions) > 0:
        type_, file, _, line_no, line, label = deletions[0]
        previous = {'type': type_,
                    'file': file,
                    'span_after': {'start': -1,
                                   'end': -1, },
                    'span_before': {'start': line_no,
                                    'end': line_no, },
                    'line': line,
                    'label': label,
                    }
        for type_, file, _, line_no, line, label in deletions[1:]:
            if not line_level \
                    and line_no - previous['span_before']['end'] == 1 \
                    and file == previous['file'] and label == previous['label']:
                previous['line'] += '\n' + line
                previous['span_before']['end'] = line_no
            else:
                result.append(previous)
                previous = {'type': type_,
                            'file': file,
                            'span_after': {'start': -1,
                                           'end': -1, },
                            'span_before': {'start': line_no,
                                            'end': line_no, },
                            'line': line,
                            'label': label,
                            }

    return result
