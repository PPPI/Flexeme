import networkx as nx

from flexeme.deltaPDG.Util.pygraph_util import get_context_from_nxgraph


def slice_delta(graph):
    graph = graph.copy()
    context = get_context_from_nxgraph(graph)
    output = nx.MultiDiGraph()
    to_visit = [n[0] for n in graph.nodes(data=True) if 'color' in n[1].keys()]
    visited = list()
    to_add = list()
    while to_visit:
        node = to_visit[0]
        to_visit = to_visit[1:]
        if node not in visited:
            visited.append(node)
            to_add.append(node)
            try:
                if graph.nodes[node]['label'] != 'Entry %s' % context[node] \
                        and graph.nodes[node]['label'] != 'Exit %s' % context[node]:
                    for neighbour in list(graph.successors(node)) + list(graph.predecessors(node)):
                        if context[neighbour] == context[node]:
                            to_visit.append(neighbour)
            except KeyError:
                pass

    for node in sorted(sorted(to_add, key=lambda x: 'Entry' in graph.nodes[x]['label'], reverse=True),
                       key=lambda x: 'Exit' in graph.nodes[x]['label']):
        output.add_node(node, **graph.nodes[node])

    for edge in graph.edges(keys=True):
        source, target, key = edge
        try:
            if output.has_node(source) and output.has_node(target):
                output.add_edge(source, target, key=key, **graph[source][target][key])
        except KeyError:
            pass

    return output


if __name__ == '__main__':
    from deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx

    graph = obj_dict_to_networkx(read_graph_from_dot('./out/gui.cs/gui.cs.dot'))
    slice = slice_delta(graph)
    nx.drawing.nx_pydot.write_dot(slice, './out/gui.cs/sliced_gui.cs.dot')
