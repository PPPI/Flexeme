from typing import Tuple, Dict

import networkx as nx
import pydot


def read_graph_from_dot(file_: str) -> Tuple[Dict, Dict[str, str]]:
    try:
        apdg = pydot.graph_from_dot_file(file_)[0].obj_dict
    except (IndexError, AttributeError, RuntimeError, TypeError, ValueError):
        apdg = ""
    return apdg


def obj_dict_to_networkx(obj_dict):
    graph = nx.MultiDiGraph()

    if isinstance(obj_dict, str):
        return graph

    for node, data in list(obj_dict['nodes'].items()):
        if node != 'graph' and 'span' in data[0]['attributes'].keys():
            attr = {k: v[1:-1] if v[0] == v[-1] == '"' else v for k, v in data[0]['attributes'].items()}
            graph.add_node(node, **attr)

    for edge, data in list(obj_dict['edges'].items()):
        s, t = edge
        attr = {k: v[1:-1] if v[0] == v[-1] == '"' else v for k, v in data[0]['attributes'].items()}
        graph.add_edge(s, t, **attr)

    for subgraph in list(obj_dict['subgraphs'].keys()):
        for node, data in list(obj_dict['subgraphs'][subgraph][0]['nodes'].items()):
            if node != 'graph' and 'span' in data[0]['attributes'].keys():
                attr = {k: v[1:-1] if v[0] == v[-1] == '"' else v for k, v in data[0]['attributes'].items()}
                if 'label' in obj_dict['subgraphs'][subgraph][0]['attributes'].keys():
                    attr['cluster'] = obj_dict['subgraphs'][subgraph][0]['attributes']['label'][1:-1]
                elif 'graph' in obj_dict['subgraphs'][subgraph][0]['nodes'].keys():
                    attr['cluster'] = obj_dict['subgraphs'][subgraph][0]['nodes']['graph'][0]['attributes']['label'][1:-1]
                graph.add_node(node, **attr)

    return graph


def get_context_from_nxgraph(graph):
    contexts = dict()
    for node in graph.nodes():
        if 'cluster' in list(graph.nodes[node].keys()):
            contexts[str(node)] = graph.nodes[node]['cluster']
    return contexts
