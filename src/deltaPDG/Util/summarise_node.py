from collections import deque

import networkx as nx
import numpy as np

from deltaPDG.Util.pygraph_util import get_context_from_nxgraph


def compress_delta(graph, node_context_size=1, line_context_size=3):
    graph = graph.copy()
    output = nx.MultiDiGraph()

    # Get context for each node so we can generate list of touched methods later
    context = get_context_from_nxgraph(graph)
    # Get a method to node map later for summarisation
    reverse_context = dict()
    for node in context.keys():
        try:
            reverse_context[context[node]].append(node)
        except KeyError:
            reverse_context[context[node]] = [node]
    # Make sure nodes are line number sorted
    reverse_context = {
        c: sorted(ns,
                  key=lambda node: int(graph.nodes[node]["span"].split('-')[0])
                  if '-' in graph.nodes[node]["span"] else 0)
        for c, ns in reverse_context.items()
    }

    # Seed summarisation from changed nodes
    to_visit = deque([(n[0], 0) for n in graph.nodes(data=True) if 'color' in n[1].keys()])

    # Keep track of which methods we should not replace fully by single nodes
    all_methods = set(context.values())
    touched_methods = {context[n] for n, _ in to_visit if n in context.keys()}

    # Explore the graph starting from changed nodes, keep track of hopes from changed nodes, stop at method boundaries
    visited = list()
    to_add = set()
    while to_visit:
        node, dst = to_visit.popleft()
        if node not in visited:
            visited.append(node)
            if dst <= node_context_size:
                to_add.add(node)
            try:
                # As long as this node is not an Entry or Exit, append it to the visit queue
                if graph.nodes[node]['label'] != 'Entry %s' % context[node] \
                        and graph.nodes[node]['label'] != 'Exit %s' % context[node]:
                    for neighbour in list(graph.successors(node)) + list(graph.predecessors(node)):
                        try:
                            n_context = context[neighbour]
                        except KeyError:
                            n_context = ""
                        if n_context == context[node]:
                            to_visit.append((neighbour, dst + 1))
            except KeyError:
                pass

    name_alias_for_edges = dict()

    merged_nodes = list()
    for method_name in all_methods:
        if method_name in touched_methods:
            # Summary of touched methods keeps topology exact
            # up to "context" hops away; we also want to carefully merge
            # labels of nodes up to method boundary.
            current_node = None
            for node in [n for n in reverse_context[method_name] if n not in to_add]:
                # This handles the case where "file" info is missing 
                # (for example we are using the dNFG for a single file)
                node_dict = {
                    k: graph.nodes[node][k] for k in ['file', 'label', 'span', 'color'] if k in graph.nodes[node].keys()
                }
                node_dict['merged_nodes'] = [node]
                node_dict['cluster'] = method_name
                # XXX: Is this sufficient to handle the empty span case?
                if node_dict['span'] == "":
                    node_dict['span'] = "0-0"
                if current_node is None:
                    current_node = node_dict
                else:
                    # Check if at method boundary
                    if graph.nodes[node]['label'] != 'Entry %s' % method_name \
                            and graph.nodes[node]['label'] != 'Exit %s' % method_name \
                            and 'color' not in graph.nodes[node].keys():
                        # We are still in method, Merge in the node details if the spans are close enough.
                        # We never merge changed/touched nodes
                        current_span_end = int(current_node['span'].split('-')[-1])
                        new_span_start = int(node_dict['span'].split('-')[0])
                        if np.abs(current_span_end - new_span_start) <= line_context_size:
                            # The spans are within line distance, merge the nodes.
                            current_span_start = int(current_node['span'].split('-')[0])
                            new_span_end = int(node_dict['span'].split('-')[-1])
                            current_node['merged_nodes'].append(node)
                            current_node['label'] += '\\n' + node_dict['label']
                            current_node['span'] = '%d-%d' % (current_span_start, new_span_end)
                        else:
                            # The spans are not within admissible line distance, emit the current node,
                            # store node aliasing, and replace current.
                            merged_nodes.append(current_node)
                            for other in current_node['merged_nodes'][1:]:
                                name_alias_for_edges[other] = current_node['merged_nodes'][0]
                            current_node = node_dict
                    else:
                        # At method boundary. Emit any current node and set the current node as None (we don't merge
                        # into method entry/exit nodes).
                        merged_nodes.append(current_node)
                        for other in current_node['merged_nodes'][1:]:
                            name_alias_for_edges[other] = current_node['merged_nodes'][0]
                        current_node = current_node
            if current_node is not None:
                merged_nodes.append(current_node)
        else:
            # The full method is summarised, do a full summary in one go.
            line_nrs = [l_ for node in reverse_context[method_name]
                        for l_ in
                        [int(l) for l in (graph.nodes[node]["span"].split('-')
                                          if '-' in graph.nodes[node]["span"] else [0])]]
            span = (min(line_nrs), max(line_nrs))
            node = reverse_context[method_name][0]
            node_dict = {
                k: graph.nodes[node][k] for k in ['file'] if k in graph.nodes[node].keys()
            }
            node_dict['merged_nodes'] = reverse_context[method_name]
            node_dict['label'] = '\\n'.join([graph.nodes[node]['label'] for node in node_dict['merged_nodes']
                                             if 'label' in graph.nodes[node].keys()])
            node_dict['cluster'] = method_name
            node_dict['span'] = '%d-%d' % span
            merged_nodes.append(node_dict)
            for other in node_dict['merged_nodes'][1:]:
                name_alias_for_edges[other] = node_dict['merged_nodes'][0]

    # Convert kept nodes to node_dict
    to_add_dict = list()
    for node in to_add:
        node_dict = {
            k: graph.nodes[node][k] for k in ['file', 'label', 'span'] if k in graph.nodes[node].keys()
        }
        node_dict['merged_nodes'] = [node]
        node_dict['cluster'] = context[node] if node in context.keys() else ""
        # XXX: Is this sufficient to handle the empty span case?
        if node_dict['span'] == "":
            node_dict['span'] = "0-0"
        to_add_dict.append(node_dict)
    to_add = to_add_dict
    # We explicitly assign to None to have it GCed
    # noinspection PyUnusedLocal
    to_add_dict = None

    # We now want to rebuild the graph with the kept and summarised nodes.
    # Add nodes
    to_add = to_add + merged_nodes
    # Keep method data (kept as subgraphs)
    to_add_with_context = dict()
    for node in to_add:
        the_context = node['cluster']

        # Record context
        try:
            to_add_with_context[the_context].append(node)
        except KeyError:
            to_add_with_context[the_context] = [node]

    # Add the nodes by method (context)
    for cluster in to_add_with_context.keys():
        to_add = to_add_with_context[cluster]
        to_add_subgraph_node_list = list()

        for node in sorted(to_add, key=lambda x: int(x['span'].split('-')[0]), reverse=True):
            node_attr = {attr: node[attr] for attr in ['file', 'label', 'span', 'cluster']
                         if attr in node.keys()}
            output.add_node(node['merged_nodes'][0], **node_attr)
            to_add_subgraph_node_list.append(node['merged_nodes'][0])

        output.subgraph(nodes=to_add_subgraph_node_list)

    # Carry over edges
    for edge in graph.edges(keys=True):
        source, target, key = edge
        # Alias output name if needed (we use the id of the first node in a summarised chain)
        output_source = name_alias_for_edges[source] if source in name_alias_for_edges.keys() else source
        output_target = name_alias_for_edges[target] if target in name_alias_for_edges.keys() else target
        try:
            if output.has_node(output_source) and output.has_node(output_target):
                output.add_edge(output_source, output_target, key=key, **graph[source][target][key])
        except KeyError:
            # This should never happen!
            pass

    # Add change and community data back in
    for n in output.nodes:
        if 'color' in graph.nodes[n].keys():
            output.nodes[n]['color'] = graph.nodes[n]['color']
        if 'community' in graph.nodes[n].keys():
            output.nodes[n]['community'] = graph.nodes[n]['community']

    return output


if __name__ == '__main__':
    from deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx

    graph = obj_dict_to_networkx(read_graph_from_dot('./out/gui.cs/Core.cs.dot'))
    compressed = compress_delta(graph)
    nx.drawing.nx_pydot.write_dot(compressed, './out/gui.cs/compressed_Core.cs.dot')
