from typing import List, Tuple

from .Util.mark_pdgs import mark_pdg_nodes
from .Util.merge_marked_pdgs import Marked_Merger
from .Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx


class deltaPDG(object):
    def __init__(self, base_pdg_location: str, m_fuzziness: int, n_fuzziness: int):
        self.before_pdg = obj_dict_to_networkx(read_graph_from_dot(base_pdg_location))
        self.merger = Marked_Merger(m_fuzziness=m_fuzziness, n_fuzziness=n_fuzziness)

    def __call__(self, target_pdg_location: str, diff: List[Tuple[str, str, int, int, str]]):
        after_pdg = obj_dict_to_networkx(read_graph_from_dot(target_pdg_location))
        marked_before = mark_pdg_nodes(self.before_pdg, '-', diff)
        marked_after = mark_pdg_nodes(after_pdg, '+', diff)
        self.deltaPDG = self.merger(before_apdg=marked_before, after_apdg=marked_after)
        return self.deltaPDG
