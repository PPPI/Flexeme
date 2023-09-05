from typing import List, Tuple

import networkx as nx

from flexeme.deltaPDG.Util.mark_pdgs import mark_pdg_nodes
from flexeme.deltaPDG.Util.merge_marked_pdgs import Marked_Merger
from flexeme.deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx


class deltaPDG(object):
    def __init__(self, base_pdg_location: str, m_fuzziness: int, n_fuzziness: int):
        self.before_pdg = self.reset_nodes_labels(obj_dict_to_networkx(read_graph_from_dot(base_pdg_location)))
        self.merger = Marked_Merger(m_fuzziness=m_fuzziness, n_fuzziness=n_fuzziness)

    def __call__(self, target_pdg_location: str, diff: List[Tuple[str, str, int, int, str]], lang):
        after_pdg = self.reset_nodes_labels(obj_dict_to_networkx(read_graph_from_dot(target_pdg_location)))
        marked_before = mark_pdg_nodes(self.before_pdg, '-', diff, lang)
        marked_after = mark_pdg_nodes(after_pdg, '+', diff, lang)
        self.deltaPDG = self.merger(before_apdg=marked_before, after_apdg=marked_after)
        return self.deltaPDG

    def reset_nodes_labels(self, pdg):
        pdg_integers = nx.convert_node_labels_to_integers(pdg)
        pdg_reset = nx.relabel_nodes(pdg_integers, lambda n: 'n' + str(n))
        return pdg_reset


def quote_label(pdg: nx.Graph):
    """
    Quotes the label of the nodes in the pdg to avoid issue https://github.com/pydot/pydot/issues/258.
    """
    pdg = pdg.copy()
    for node in pdg.nodes:
        label_value = pdg.nodes[node]['label']
        pdg.nodes[node]['label'] = f'"{label_value}"'
    return pdg
