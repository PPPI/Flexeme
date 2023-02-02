import os
import time
from threading import Thread
from typing import List

import networkx as nx
import numpy as np
from tqdm import tqdm

from Util.evaluation import evaluate
from deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx


def extract_DU_chains_from_delta(graph):
    # Remove non-data-flow edges from graph
    # That is we keep only edges with key=1 for out graph format
    graph = graph.copy()
    for edge in list(graph.edges(keys=True)):
        source, target, key = edge
        if key != '1':
            try:
                graph.remove_edge(source, target, key=key)
            except KeyError:
                pass

    # Find Assignments, at each assign, delete all incoming edges.
    for node, data in list(graph.nodes(data=True)):
        if 'label' in data.keys():
            label = data['label']
            label = label.split()
            if any([op in label for op in ['=', '+=', '-=', '*=', '/=', '%=', '<<=', '>>=', '&=', '^=', '|=']]):
                for in_edge in list(graph.in_edges(nbunch=[node])):
                    try:
                        graph.remove_edge(*in_edge)
                    except KeyError:
                        pass

    return graph


def defUsesInDiffs(diff_node1, diff_node2, graph):
    return graph.has_edge(diff_node1, diff_node2) or graph.has_edge(diff_node2, diff_node1)


def useUsesInDiffs(diff_node1, diff_node2, graph):
    return len(set(map(lambda p: p[0], graph.in_edges(nbunch=[diff_node1]))).intersection(
        set(map(lambda p: p[0], graph.in_edges(nbunch=[diff_node2])))))


def closure_of_DU_on_diff(graph):
    graph = graph.copy()
    community_id = 0
    for node, data in graph.nodes(data=True):
        try:
            if data['color'] == 'green' or data['color'] == 'red':
                graph.nodes[node]['prediction'] = community_id
                community_id += 1
        except KeyError:
            pass

    changed = True
    nodes = [n for n in graph.nodes() if 'color' in graph.nodes[n].keys()]

    while changed:
        changed = False
        for i in range(len(nodes)):
            node = nodes[i]
            for other in nodes[:i] + nodes[i + 1:]:
                if (defUsesInDiffs(node, other, graph) or useUsesInDiffs(node, other, graph)) \
                        and int(graph.nodes[node]['prediction']) != int(graph.nodes[other]['prediction']):
                    community_id = min(int(graph.nodes[node]['prediction']), int(graph.nodes[other]['prediction']))
                    graph.nodes[node]['prediction'] = community_id
                    graph.nodes[other]['prediction'] = community_id
                    changed = True

    return graph


def validate(files: List[str], times, repository_name):
    n_workers = 4
    chunck_size = int(len(files) / n_workers)
    while chunck_size == 0:
        n_workers -= 1
        chunck_size = int(len(files) / n_workers)
    chuncked = [files[i:i + chunck_size] for i in range(0, len(files), chunck_size)]

    def worker(work):
        for graph_location in tqdm(work, leave=False):
            chain = os.path.basename(os.path.dirname(os.path.dirname(graph_location)))
            q = int(os.path.basename(os.path.dirname(graph_location)))
            graph = obj_dict_to_networkx(read_graph_from_dot(graph_location))

            t0 = time.process_time()
            for i in range(times):
                DU_chains = extract_DU_chains_from_delta(graph)
                closure = closure_of_DU_on_diff(DU_chains)
            t1 = time.process_time()
            time_ = (t1 - t0) / times

            truth = list()
            label = list()
            for node, data in graph.nodes(data=True):
                if 'color' in data.keys():
                    if 'community' in data.keys():
                        truth.append(int(data['community']))
                    else:
                        truth.append(0)

                    try:
                        label.append(int(closure.nodes[node]['prediction']))
                    except KeyError:
                        label.append(-1)
            nx.drawing.nx_pydot.write_dot(closure, graph_location[:-4] + '_closure.dot')
            truth = np.asarray(truth)
            label = np.asarray(label)
            acc, overlap = evaluate(truth[label > -1], label[label > -1],
                                    q=max(q, np.max(label) + 1) if len(label) > 0 else q)
            cover = len(label[label > -1]) / len(label) if len(label) > 0 else .0
            with open('./out/%s/du_results_raw.csv' % repository_name, 'a') as f:
                f.write(chain + ',' + str(q) + ',' + str(acc) + ',' + str(overlap) + ',' + str(cover) + ',' + str(
                    time_) + '\n')

    threads = []
    for work in chuncked:
        t = Thread(target=worker, args=(work,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()


def untangle(deltaPDG):
    DU_chains = extract_DU_chains_from_delta(deltaPDG)
    closure = closure_of_DU_on_diff(DU_chains)
    return closure
