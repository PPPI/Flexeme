import itertools

import networkx as nx
import numpy as np
import scipy
from sklearn.cluster import AgglomerativeClustering


def integer_distance_between_intervals(r1, r2):
    # Taken from: https://stackoverflow.com/questions/16843409/finding-integer-distance-between-two-intervals
    # sort the two ranges such that the range with smaller first element
    # is assigned to x and the bigger one is assigned to y
    x, y = sorted((r1, r2))

    # now if x[1] lies between x[0] and y[0](x[1] != y[0] but can be equal to x[0])
    # then the ranges are not overlapping and return the differnce of y[0] and x[1]
    # otherwise return 0
    if x[0] <= x[1] < y[0] and all(y[0] <= y[1] for y in (r1, r2)):
        return y[0] - x[1]
    return 0


def prefix_distance(namespace, other_namespace):
    namespace = namespace.split('.')
    other_namespace = other_namespace.split('.')
    disagreement = max(len(namespace), len(other_namespace)) - min(len(namespace), len(other_namespace))
    for i in range(min(len(namespace), len(other_namespace))):
        if namespace[i] == other_namespace[i]:
            continue
        disagreement = max(len(namespace[i:]), len(other_namespace[i:]))
        break
    return disagreement / max(len(namespace), len(other_namespace))


def call_graph_distance(graph, context):
    graph = graph.copy()
    # Remove all non-call edged from graph
    # For method1 containing diff_region1 and method2 containing diff_region2
    # Compute the shortest path in the hypergraph
    # Compute the sum of the path weights, where thw weight of an edge is #from_to(m1,m2)/#into(m2)
    call_graph = nx.DiGraph()
    all_contexts = list(set(context.values()))
    node_id_lookup = {all_contexts[i]: i for i in range(len(all_contexts))}
    for hypernode in all_contexts:
        start = list()
        end = list()
        out_bound = list()
        for node, data in [(n, d) for n, d in graph.nodes(data=True)
                           if 'cluster' in d.keys() and d['cluster'] == hypernode]:
            start_, end_ = [int(n) for n in data['span'].split('-')] \
                if 'span' in data.keys() and '-' in data['span'] else [-1, -1]
            start.append(start_)
            end.append(end_)
            try:
                for out_neighbour in graph.successors(node):
                    other_context = context[str(out_neighbour)]
                    if other_context != hypernode:
                        out_bound.append(node_id_lookup[other_context])
            except KeyError:
                pass

        start = min(filter(lambda s: s != -1, start), default=-1)
        end = max(filter(lambda s: s != -1, end), default=-1)
        try:
            call_graph.add_node(node_id_lookup[hypernode], span={'start': start, 'end': end},
                                label=hypernode)
            for edge_target in set(out_bound):
                call_graph.add_edge(node_id_lookup[hypernode], edge_target, weight=out_bound.count(edge_target))
        except KeyError:
            pass

    call_graph_ = call_graph.copy()
    for u, v in call_graph_.edges():
        this_data = call_graph.get_edge_data(u, v)
        if call_graph.has_edge(v, u):
            other_data = call_graph.get_edge_data(v, u)
            call_graph.add_edge(u, v, weight=1 / (this_data['weight'] + other_data['weight']))
        else:
            call_graph.add_edge(u, v, weight=1 / this_data['weight'])

    working_graph = nx.MultiGraph(call_graph)

    def voter(node, other):
        region1_nodes = {context[k] for k in [node] if k in context.keys()}
        region2_nodes = {context[k] for k in [other] if k in context.keys()}

        region1_hypernodes = list()
        region2_hypernodes = list()

        for node, node_data in working_graph.nodes(data=True):
            call_graph_label = node_data['label']
            if call_graph_label in region1_nodes:
                region1_hypernodes.append(node_id_lookup[call_graph_label])
            if call_graph_label in region2_nodes:
                region2_hypernodes.append(node_id_lookup[call_graph_label])

        distances = list()
        if len(region1_hypernodes) > 0:
            for target in region2_hypernodes:
                try:
                    distances_, _ = nx.multi_source_dijkstra(working_graph, region1_hypernodes, target)
                    distances.append(distances_)
                except nx.NetworkXNoPath:
                    pass

        return min(distances, default=0)

    return voter


def cluster_from_voter_affinity(affinity, concepts):
    if concepts > 1:
        cluster = AgglomerativeClustering(n_clusters=concepts, affinity='precomputed', linkage='complete')
    else:
        # The distance choice is by if same file or same namespace but not data, not enough.
        cluster = AgglomerativeClustering(n_clusters=None, distance_threshold=2.5, affinity='precomputed',
                                          linkage='complete')
    if len(affinity) < 2:
        if len(affinity) == 1:
            labels = np.asarray([0, 0]) if affinity[0] <= 2.5 else np.asarray([0, 1])
        else:
            labels = np.asarray([0])
    else:
        labels = cluster.fit_predict(scipy.spatial.distance.squareform(affinity))

    return labels


def generate_empty_affinity(n, voters):
    affinity = np.zeros(shape=(scipy.special.comb(n, 2, exact=True),))
    args = list(enumerate(itertools.combinations(range(n), 2)))
    args = [(v, k, p) for v in voters for k, p in args]
    return affinity, args
