import itertools
import os
import logging
import re
import time
from collections import defaultdict
from multiprocessing.pool import ThreadPool
from threading import Thread
from typing import List, Tuple

import networkx as nx
import numpy as np
import scipy
from grakel import GraphKernel
from nltk import casual_tokenize
from nltk.stem import PorterStemmer
from sklearn.cluster import AgglomerativeClustering
from tqdm import tqdm

from flexeme.deltaPDG.deltaPDG import quote_label
from flexeme.Util.evaluation import evaluate
from flexeme.confidence_voters.confidence_voters import remove_all_except
from flexeme.deltaPDG.Util.pygraph_util import obj_dict_to_networkx, read_graph_from_dot


def split_camel_case(input: str) -> List[str]:
    return re.sub(r'([A-Z][a-z]+)', r' \1', re.sub(r'([A-Z]+)', r' \1', input)).split()


ps = PorterStemmer()


def process_line_of_code(line: str) -> str:
    words = casual_tokenize(line.strip())
    new_words = list()
    for word in words:
        candidate = ''.join(map(lambda w: ps.stem(w), split_camel_case(word)))
        for new_word in candidate.split("."):
            new_words.append(new_word)
    processed = ' '.join(new_words)
    return processed


def graph_to_grakel(g: nx.MultiDiGraph, with_data: bool = True, with_call: bool = True, with_name: bool = True):
    nodelst = [n for n in g.nodes]
    adj = nx.adjacency_matrix(g)
    node_labels = {nodelst.index(n):
                   # ('1' if "color" in g.nodes[n].keys() else '0')
                       ('1' if any([k == 1 for u, v, k in g.edges(nbunch=[n], keys=True)]) else '0')
                       if with_data else ""  # data-flow
                                         + ('1' if any([k == 2 for u, v, k in g.edges(nbunch=[n], keys=True)]) else '0')
                       if with_call else ""  # call-graph
                                         + ('1' if any([k == 3 for u, v, k in g.edges(nbunch=[n], keys=True)]) else '0')
                       if with_name else ""  # name-flow
                   for n in g.nodes}
    edge_labels = {(nodelst.index(fro), nodelst.index(to)): int(type_of_edge) for fro, to, type_of_edge in g.edges}
    return adj, node_labels, edge_labels


def deltaPDG_to_list_of_Graphs(delta: nx.MultiDiGraph, khop_k: int = 1) -> Tuple[List[str], List[nx.MultiDiGraph]]:
    seeds = [n for n, d in delta.nodes(data=True)
             if 'color' in d.keys() and d['color'] != 'orange' and 'community' in d.keys()]
    result = list()
    with ThreadPool(processes=min(os.cpu_count() - 1, 12)) as wp:
        for subgraph in wp.imap_unordered(lambda s:
                                          delta.subgraph(
                                              nx.single_source_shortest_path_length(delta, s, cutoff=khop_k).keys()),
                                          seeds):
            result.append(subgraph)
    return seeds, result


def validate(files: List[str], times, k_hop, repository_name, edges_kept="all",
             with_data: bool = True, with_call: bool = True, with_name: bool = True, suffix="raw", out_file=None):
    if not len(files):
        logging.error("No files to validate.")
        return
    n_workers = 1
    chunck_size = int(len(files) / n_workers)
    while (chunck_size == 0) and (n_workers > 1):
        n_workers -= 1
        chunck_size = int(len(files) / n_workers)
    chuncked = [files[i:i + chunck_size] for i in range(0, len(files), chunck_size)]

    def worker(work, out_file=None):
        for graph_location in tqdm(work, leave=False):
            chain = os.path.basename(os.path.dirname(os.path.dirname(graph_location)))
            q = int(os.path.basename(os.path.dirname(graph_location))) # q is for concepts
            graph = obj_dict_to_networkx(read_graph_from_dot(graph_location))
            graph = remove_all_except(graph, edges_kept)

            if len(graph.nodes) == 0:
                continue

            t0 = time.perf_counter()
            for i in range(times):
                seeds, list_of_graphs = deltaPDG_to_list_of_Graphs(graph, khop_k=k_hop)
                logging.info(f"List of graph length {len(list_of_graphs)}")
                wl_subtree = GraphKernel(kernel=[{"name": "weisfeiler_lehman", "n_iter": 10}, {"name": "subtree_wl"}],
                                         normalize=True)
                if len(list_of_graphs) > 0:
                    similarities = defaultdict(lambda: (0, 0.0))
                    for g1, g2 in itertools.combinations(list_of_graphs, 2):
                        # The graph has to be converted to {Graph, Node_Labels, Edge_Labels}
                        wl_subtree.fit([graph_to_grakel(g1, with_data, with_call, with_name)])
                        similarity = wl_subtree.transform([graph_to_grakel(g2, with_data, with_call, with_name)])[0][0]
                        similarities[(list_of_graphs.index(g1), list_of_graphs.index(g2))] = similarity
                        # logging.info(similarity)

                    n = len(list_of_graphs)
                    logging.info(f"n={n}")
                    affinity = np.zeros(shape=(scipy.special.comb(n, 2, exact=True),))
                    logging.info(f"affinity={affinity}")
                    args = list(enumerate(itertools.combinations(range(n), 2)))
                    with ThreadPool(processes=min(os.cpu_count() - 1, 1)) as wp:
                        for k, value in wp.imap_unordered(lambda i: (i[0], similarities[(i[-1][0], i[-1][1])]),
                                                          args):
                            affinity[k] += (1 - value)  # affinity is distance! so (1 - sim)

                    cluster = AgglomerativeClustering(n_clusters=None, distance_threshold=0.5,
                                                      affinity='precomputed', linkage='complete')
                    logging.info(f"Affinity: {affinity}")
                    if len(affinity) < 2:
                        if len(affinity) == 1:
                            labels = np.asarray([0, 0]) if affinity[0] <= 0.5 else np.asarray([0, 1])
                        else:
                            labels = np.asarray([0])
                    else:
                        labels = cluster.fit_predict(scipy.spatial.distance.squareform(affinity))
                else:
                    labels = None
            t1 = time.perf_counter()
            time_ = (t1 - t0) / times

            truth = list()
            label = list()
            for node, data in graph.nodes(data=True):
                if 'color' in data.keys():
                    if 'community' in data.keys():
                        truth.append(int(data['community']))

                        # Get the index for the currently evaluated node
                        i = seeds.index(node) if node in seeds else -1

                        if labels is not None and i != -1:
                            data['label'] = '"%d: %s"' % (labels[i], data['label'])
                            label.append(labels[i])
                            graph.add_node(node, **data)
                        else:
                            data['label'] = '"-1: %s"' % data['label']
                            label.append(-1)
                            graph.add_node(node, **data)

            if out_file is None:
                out_file = graph_location[:-4] + '_output_wl_%d.dot' % k_hop
            nx.drawing.nx_pydot.write_dot(quote_label(graph), out_file)

            truth = np.asarray(truth)
            label = np.asarray(label)
            acc, overlap = evaluate(truth[label > -1], label[label > -1], q=1 if len(label) == 0 else np.max(label) + 1)
            os.makedirs('./out/%s' % repository_name, exist_ok=True)
            with open('./out/%s/wl_%s_%d_results_%s.csv' % (repository_name, edges_kept, k_hop, suffix), 'a') as f:
                f.write(chain + ',' + str(q) + ',' + str(acc) + ',' + str(overlap) + ',' + str(time_) + '\n')

    threads = []
    for work in chuncked:
        t = Thread(target=worker, args=(work,out_file))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()


def untangle(graph, k_hop, with_data: bool = True, with_call: bool = True, with_name: bool = True):
    seeds, list_of_graphs = deltaPDG_to_list_of_Graphs(graph, khop_k=k_hop)
    wl_subtree = GraphKernel(kernel=[{"name": "weisfeiler_lehman", "n_iter": 10}, {"name": "subtree_wl"}],
                             normalize=True)
    if len(list_of_graphs) > 0:
        similarities = defaultdict(lambda: (0, 0.0))
        for g1, g2 in itertools.combinations(list_of_graphs, 2):
            # The graph has to be converted to {Graph, Node_Labels, Edge_Labels}
            wl_subtree.fit([graph_to_grakel(g1, with_data, with_call, with_name)])
            similarity = wl_subtree.transform([graph_to_grakel(g2, with_data, with_call, with_name)])[0][0]
            similarities[(list_of_graphs.index(g1), list_of_graphs.index(g2))] = similarity

        n = len(list_of_graphs)
        affinity = np.zeros(shape=(scipy.special.comb(n, 2, exact=True),))
        args = list(enumerate(itertools.combinations(range(n), 2)))
        with ThreadPool(processes=min(os.cpu_count() - 1, 1)) as wp:
            for k, value in wp.imap_unordered(lambda i: (i[0], similarities[(i[-1][0], i[-1][1])]),
                                              args):
                affinity[k] += (1 - value)  # affinity is distance! so (1 - sim)

        cluster = AgglomerativeClustering(n_clusters=None, distance_threshold=0.5,
                                          affinity='precomputed',
                                          linkage='complete')
        if len(affinity) < 2:
            if len(affinity) == 1:
                labels = np.asarray([0, 0]) if affinity[0] <= 0.5 else np.asarray([0, 1])
            else:
                labels = np.asarray([0])
        else:
            labels = cluster.fit_predict(scipy.spatial.distance.squareform(affinity))
    else:
        labels = None

    label = list()
    for node, data in graph.nodes(data=True):
        if 'color' in data.keys():
            i = seeds.index(node) if node in seeds else -1

            if labels is not None and i != -1:
                data['label'] = '%d: ' % labels[i] + data['label']
                label.append(labels[i])
                graph.add_node(node, **data)
            else:
                data['label'] = '-1: ' + data['label']
                label.append(-1)
                graph.add_node(node, **data)

    return graph