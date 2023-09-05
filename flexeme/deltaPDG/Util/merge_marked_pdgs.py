from flexeme.deltaPDG.Util.equivalence_util import Eq_Utils


class Marked_Merger(object):
    def __init__(self, m_fuzziness: int, n_fuzziness: int):
        self.m_fuzziness = m_fuzziness
        self.n_fuzziness = n_fuzziness
        self.eq_utils = Eq_Utils(m_fuzziness, n_fuzziness)

    def __call__(self, before_apdg, after_apdg):
        before_apdg = before_apdg.copy()
        after_apdg = after_apdg.copy()
        label_map_ab = dict()
        label_map_ba = dict()

        for node, data in before_apdg.nodes(data=True):
            if 'color' in data.keys() and data['color'] != 'orange':
                continue
            for other_node, other_data in after_apdg.nodes(data=True):
                if other_node in label_map_ba.keys():
                    continue
                if 'color' in other_data.keys() and other_data['color'] != 'orange':
                    continue
                equivalent = self.eq_utils.node_eq(before_apdg, node, after_apdg, other_node)
                try:
                    equivalent = equivalent \
                                 and self.eq_utils.context_eq(data['cluster'], other_data['cluster'])
                except KeyError:
                    equivalent = equivalent \
                                 and 'cluster' not in data.keys() \
                                 and 'cluster' not in other_data.keys()
                if equivalent:
                    label_map_ab[str(node)] = str(other_node)
                    label_map_ba[str(other_node)] = str(node)
                    break
        # Visit anchors, explore neighbourhood and copy over nodes
        # Each node copied: add to a list to be explored
        # As each node is explored add copied nodes
        # Stop when list is empty
        # Boot strap list with all marked nodes in v2
        to_visit = [str(node) for node in after_apdg.nodes() if
                    'color' in after_apdg.nodes[node].keys() and after_apdg.nodes[node]['color'] != 'orange']
        visited = list()

        work_to_be_done = len(to_visit) > 0
        # counter = 1
        # We fixed-point compute this due to the fact that we leave potentially dangling edges, 
        # so we iterate until all edges point to real nodes
        while work_to_be_done:
            # print(to_visit)
            # print(visited)
            node_id = to_visit[0]
            node_id = node_id.replace('n', 'd') if node_id not in label_map_ba.keys() else label_map_ba[node_id]
            to_visit = to_visit[1:]
            if not (before_apdg.has_node(node_id) and 'label' in before_apdg.nodes[node_id].keys()):
                # Find node in after graph and visit if not visited (sanity check)
                other_node = 'n' + node_id[1:]
                if other_node not in visited:
                    before_apdg.add_node(node_id, **after_apdg.nodes[other_node])

                    # Add in-edges from after graph to before graph, we leave references to un-imported nodes dangling
                    # However, we also add the un-imported nodes to the to-visit list
                    in_edges = after_apdg.in_edges(nbunch=[other_node], keys=True)
                    for in_edge in list(in_edges):
                        in_, _, key = in_edge
                        if in_ not in label_map_ba.keys():
                            in_id = str(in_).replace('n', 'd')
                            if in_ not in to_visit and in_ not in visited: to_visit.append(in_)
                        else:
                            in_id = label_map_ba[str(in_)]
                        if before_apdg.has_edge(in_id, node_id, key):
                            if not (self.eq_utils.attr_eq(before_apdg[in_id][node_id][key],
                                                          after_apdg[in_][other_node][key])):
                                before_apdg.add_edge(in_id, node_id, key,
                                                     **after_apdg[in_][other_node][key])
                                after_apdg.remove_edge(in_, other_node, key)
                        else:
                            before_apdg.add_edge(in_id, node_id, key, **after_apdg[in_][other_node][key])
                            after_apdg.remove_edge(in_, other_node, key)

                    # Add out-edges from after graph to before graph, we leave references to un-imported nodes dangling
                    # However, we also add the un-imported nodes to the to-visit list
                    out_edges = after_apdg.out_edges(nbunch=[other_node], keys=True)
                    for out_edge in list(out_edges):
                        _, out_, key = out_edge
                        if out_ not in label_map_ba.keys():
                            out_id = str(out_).replace('n', 'd')
                            if out_ not in to_visit and out_ not in visited: to_visit.append(out_)
                        else:
                            out_id = label_map_ba[str(out_)]
                        if before_apdg.has_edge(node_id, out_id, key):
                            if not (self.eq_utils.attr_eq(before_apdg[node_id][out_id][key],
                                                          after_apdg[other_node][out_][key])):
                                before_apdg.add_edge(node_id, out_id, key,
                                                     **after_apdg[other_node][out_][key])
                                after_apdg.remove_edge(other_node, out_, key)
                        else:
                            before_apdg.add_edge(node_id, out_id, key,
                                                 **after_apdg[other_node][out_][key])
                            after_apdg.remove_edge(other_node, out_, key)
                    visited.append(other_node)
            work_to_be_done = len(to_visit) > 0

        for node in before_apdg.nodes():
            if 'color' in before_apdg.nodes[node].keys():
                for edge in list(before_apdg.in_edges(nbunch=[node], keys=True)) \
                            + list(before_apdg.out_edges(nbunch=[node], keys=True)):
                    s, t, k = edge
                    before_apdg[s][t][k]['color'] = before_apdg.nodes[node]['color']

        for node, other_node in label_map_ab.items():
            for edge in list(after_apdg.in_edges(nbunch=[other_node], keys=True)):
                source, sink, key = edge
                assert sink == other_node
                if source in label_map_ba.keys():
                    before_node = label_map_ba[source]
                    if before_apdg.has_edge(before_node, node):
                        if not (self.eq_utils.attr_eq(before_apdg[before_node][node][key],
                                                      after_apdg[source][sink][key])):
                            after_apdg[source][sink][key]['color'] = 'green'
                            before_apdg.add_edge(before_node, node, key, **after_apdg[source][sink][key])
                            after_apdg.remove_edge(source, sink, key)
                    else:
                        after_apdg[source][sink][key]['color'] = 'green'
                        before_apdg.add_edge(before_node, node, key, **after_apdg[source][sink][key])
                        after_apdg.remove_edge(source, sink, key)

            for edge in list(after_apdg.out_edges(nbunch=[other_node], keys=True)):
                source, sink, key = edge
                assert source == other_node
                if sink in label_map_ba.keys():
                    before_node = label_map_ba[sink]
                    if before_apdg.has_edge(node, before_node, key):
                        if not (self.eq_utils.attr_eq(before_apdg[node][before_node][key],
                                                      after_apdg[source][sink][key])):
                            after_apdg[source][sink][key]['color'] = 'green'
                            before_apdg.add_edge(node, before_node, key, **after_apdg[source][sink][key])
                            after_apdg.remove_edge(source, sink, key)
                    else:
                        after_apdg[source][sink][key]['color'] = 'green'
                        before_apdg.add_edge(node, before_node, key, **after_apdg[source][sink][key])
                        after_apdg.remove_edge(source, sink, key)

        for edge in list(after_apdg.edges(keys=True)):
            source, target, key = edge
            if after_apdg[source][target][key]['style'] != 'solid':
                after_apdg.remove_edge(source, target, key=key)

        for node, other_node in label_map_ab.items():
            for edge in before_apdg.out_edges(nbunch=[node], data=True, keys=True):
                source, sink, key, data = edge
                if data['style'] != 'solid':
                    continue
                assert source == node
                if 'color' not in data.keys():
                    if sink in label_map_ab.keys():
                        after_node = label_map_ab[sink]
                        if not (after_apdg.has_edge(other_node, after_node)):
                            before_apdg[source][sink][key]['color'] = 'red'

        return before_apdg
