from rapidfuzz import fuzz


class Eq_Utils(object):
    def __init__(self, m_fuzziness, n_fuzziness):
        self.m_fuzziness = m_fuzziness
        self.n_fuzziness = n_fuzziness

    def context_eq(self, context_a: str, context_b: str) -> bool:
        return fuzz.ratio(context_a, context_b, score_cutoff=self.m_fuzziness) > 0

    def node_label_eq(self, node_label_a: str, node_label_b: str) -> bool:
        return fuzz.ratio(node_label_a, node_label_b, score_cutoff=self.n_fuzziness) > 0

    def node_eq(self, graph_a, node_a, graph_b, node_b):
        if not (self.node_label_eq(graph_a.nodes[node_a]['label'], graph_b.nodes[node_b]['label'])):
            return False

        n_a = [n for n in list(graph_a.successors(node_a)) + list(graph_a.predecessors(node_a)) if
               'color' not in graph_a.nodes[n].keys() or graph_a.nodes[n]['color'] == 'orange']

        n_b = [n for n in list(graph_b.successors(node_b)) + list(graph_b.predecessors(node_b)) if
               'color' not in graph_b.nodes[n].keys() or graph_b.nodes[n]['color'] == 'orange']

        # We check for set inclusion, make sure we have the smaller set in the outer loop!
        if len(n_a) > len(n_b):
            temp = n_b
            n_b = n_a
            n_a = temp

        for node in n_a:
            found = False
            for other_node in n_b:
                try:
                    if self.node_label_eq(graph_a.nodes[node]['label'], graph_b.nodes[other_node]['label']):
                        found = True
                        break
                except KeyError:
                    pass
            if not found:
                return False

        return True

    def attr_eq(self, attr_a, attr_b):
        for key in attr_a.keys():
            if key not in attr_b.keys():
                return False
            elif key == 'label' and not (self.node_label_eq(attr_a[key], attr_b[key])):
                return False
            elif attr_a[key] != attr_b[key]:
                return False
        return True
