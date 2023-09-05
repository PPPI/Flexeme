# Given a collection of deltaPDGs, try to merge the method nodes among them such that we minimise the number of files.
import itertools
import os

import networkx as nx

from flexeme.deltaPDG.deltaPDG import quote_label
from flexeme.Util.general_util import get_pattern_paths
from flexeme.deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx, get_context_from_nxgraph


def merge_files_pdg(path_to_commit):
    """
    Given a directory containing dot file per java file, merges them into a single dot file.
    """
    paths = get_pattern_paths('*.java.dot', path_to_commit)
    if not len(paths):
        paths = get_pattern_paths('*.cs.dot', path_to_commit)

    merged = merge_deltas_for_a_commit(paths)
    merged_path = os.path.join(path_to_commit, 'merged.dot')
    try:
        nx.drawing.nx_pydot.write_dot(quote_label(merged), merged_path)
    except Exception as e:
        print('Could not write merged dot file')
        print(merged.nodes.data())
        raise e
    return merged_path


def find_entry_and_exit(context, graph):
    # This works under an assumption of entry and exit uniqueness
    # See the change in marking nodes to ensure this: Not marking Entry and Exit nodes
    entry = None
    exit = None
    for node, data in graph.nodes(data=True):
        if 'label' in data.keys() and 'cluster' in data.keys():
            if 'Entry' in data['label'] and data['cluster'] == context:
                entry = node
            elif 'Exit' in data['label'] and data['cluster'] == context:
                exit = node

    return entry, exit


def merge_deltas_for_a_commit(graph_locations):
    # We will use the file attribute to track original files so that diff intersection can be made to work
    original_file = os.path.basename(graph_locations[0])
    # We will take the first graph as a base and add the rest onto it
    graph = obj_dict_to_networkx(read_graph_from_dot(graph_locations[0]))
    contexts = get_context_from_nxgraph(graph)
    output = graph.copy()
    graph_locations = graph_locations[1:]
    for i, graph_location in enumerate(graph_locations):
        next_graph = obj_dict_to_networkx(read_graph_from_dot(graph_location))
        next_contexts = get_context_from_nxgraph(next_graph)
        # First find the contexts that exist in both
        mappable_contexts = list()
        for next_context, current_context in itertools.product(set(next_contexts.values()), set(contexts.values())):
            if next_context == current_context and next_context != 'lambda expression':
                mappable_contexts.append(current_context)
                break

        copied_nodes = list()
        mapped_nodes = list()
        # And copy over all of the nodes into the merged representation
        for context in mappable_contexts:
            current_entry, current_exit = find_entry_and_exit(context, graph)
            other_entry, other_exit = find_entry_and_exit(context, next_graph)

            if current_entry is not None and other_entry is not None:
                mapped_nodes.append((str(current_entry), str(other_entry)))
            if current_exit is not None and other_exit is not None:
                mapped_nodes.append((str(current_exit), str(other_exit)))

            other_nodes = [n for n in next_graph.nodes(data=True)
                           if n[0] not in [other_entry, other_exit] and 'cluster' in n[1].keys()
                           and n[1]['cluster'] == context]
            if current_entry is None and other_entry is not None:
                other_nodes.append((other_entry, next_graph.nodes[other_entry]))
            if current_exit is None and other_exit is not None:
                other_nodes.append((other_exit, next_graph.nodes[other_exit]))

            if len(other_nodes) > 0:
                if current_entry is not None and 'file' not in graph.nodes[current_entry].keys():
                    graph.nodes[current_entry]['file'] = os.path.basename(graph_location[:-len('.dot')])
                if current_exit is not None and 'file' not in graph.nodes[current_exit]:
                    graph.nodes[current_exit]['file'] = os.path.basename(graph_location[:-len('.dot')])

            for copy_node, data in other_nodes:
                data['file'] = os.path.basename(graph_location[:-len('.dot')])
                output.add_node('m%d_' % i + copy_node[1:], **data)
                copied_nodes.append(('m%d_' % i + copy_node[1:], copy_node))

        # Now we copy over all of the contexts that did not map/exist in the merged representation
        for other_context in [c for c in set(next_contexts.values()) if c not in mappable_contexts]:
            other_entry, other_exit = find_entry_and_exit(other_context, next_graph)
            other_nodes = [n for n in next_graph.nodes(data=True)
                           if n[0] not in [other_entry, other_exit] and 'cluster' in n[1].keys()
                           and n[1]['cluster'] == other_context]
            # For aesthetic reasons make sure to copy entry first and exit last
            if other_entry is not None:
                other_nodes = [(other_entry, next_graph.nodes[other_entry])] + other_nodes
            if other_exit is not None:
                other_nodes.append((other_exit, next_graph.nodes[other_exit]))
            for copy_node, data in other_nodes:
                data['file'] = os.path.basename(graph_location[:-len('.dot')])
                output.add_node('m%d_' % i + copy_node[1:], **data)
                copied_nodes.append(('m%d_' % i + copy_node[1:], copy_node))

        # Finally we copy over all of the nodes w/o a context
        for copy_node, data in [n for n in next_graph.nodes(data=True) if n[0] not in next_contexts.keys()]:
            data['file'] = os.path.basename(graph_location[:-len('.dot')])
            output.add_node('m%d_' % i + copy_node[1:], **data)
            copied_nodes.append(('m%d_' % i + copy_node[1:], copy_node))

        # We move over the edges making sure we properly map the ends
        reverse_map = {v: u for u, v in copied_nodes + mapped_nodes}
        for copied_node, original_node in copied_nodes:
            for s, t, k in next_graph.edges(nbunch=[original_node], keys=True):
                try:
                    if s in reverse_map.keys() and t in reverse_map.keys():
                        if output.has_node(reverse_map[s]) and output.has_node(reverse_map[t]):
                            output.add_edge(reverse_map[s], reverse_map[t], key=k, **next_graph[s][t][k])
                except KeyError:
                    pass

    # And finally we mark the original file nodes
    for node, _ in [n for n in output.nodes(data=True) if 'file' not in n[1].keys()]:
        graph.nodes[node]['file'] = original_file

    return output


if __name__ == '__main__':
    merged = merge_deltas_for_a_commit(get_pattern_paths('*.cs.dot', os.path.join(
        '.',
        'out',
        'gui.cs'
    )))
    nx.drawing.nx_pydot.write_dot(merged, './out/gui.cs/gui.cs.dot')
