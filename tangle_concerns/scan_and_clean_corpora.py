import os
import sys
from threading import Thread

import networkx as nx

from Util.general_util import get_pattern_paths
from deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx


def worker(all_graph_locations, corpus_name):
    for graph_location in all_graph_locations:
        data_point_name = os.path.basename(os.path.dirname(os.path.dirname(graph_location)))
        if os.path.exists(os.path.join('.', 'data', 'corpora_clean', corpus_name, data_point_name)):
            print('[Scan and clean] Skipping %s as it exists'
                  '' % data_point_name)
            return
        print('[Scan and clean] Cleaning data-point %s' % data_point_name)

        try:
            graph = obj_dict_to_networkx(read_graph_from_dot(graph_location))
        except (TypeError, ValueError):
            continue

        # Get actual number of communities
        communities = set()
        for node, data in list(graph.nodes(data=True)):
            if 'community' in data.keys():
                communities.add(data['community'])
            if 'color' in data.keys() and 'community' not in data.keys():
                communities.add('0')
                graph.node[node]['community'] = '0'
        communities = sorted(list(communities))

        nr_concepts = str(len(communities))

        if len(communities) > 0:
            # Normalise labels
            for node, data in list(graph.nodes(data=True)):
                if 'community' in data.keys():
                    graph.node[node]['community'] = communities.index(data['community'])

            output_path = os.path.join('.', 'data', 'corpora_clean',
                                       corpus_name, data_point_name, nr_concepts, 'merged.dot')
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            nx.drawing.nx_pydot.write_dot(graph, output_path)


if __name__ == '__main__':
    corpus_name = sys.argv[1]
    all_graph_locations = get_pattern_paths('*merged.dot', os.path.join('.', 'data', 'corpora', corpus_name))
    os.makedirs(os.path.join('.', 'data', 'corpora_clean', corpus_name), exist_ok=True)
    n_workers = 32
    chunck_size = int(len(all_graph_locations) / n_workers)
    chuncked = [all_graph_locations[i:i + chunck_size] for i in range(0, len(all_graph_locations), chunck_size)]

    threads = []
    for work in chuncked:
        t = Thread(target=worker, args=(work, corpus_name))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
