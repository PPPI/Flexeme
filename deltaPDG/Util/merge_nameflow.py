from typing import Dict, List, Any


def find_node_in_graph(node: Any, apdg):
    if not node['Infile']: return None
    pdg_node = None
    for node_pdg, data in apdg.nodes(data=True):
        if '-' not in data['span']:
            continue
        start, end = data['span'].split('-')
        is_in_span = int(start) <= int(node['Location'][1]) <= int(end)
        if is_in_span:
            pdg_node = node_pdg
            break
    return pdg_node


def add_nameflow_edges(nameflow_data: Dict[str, List[Any]], apdg):
    apdg = apdg.copy()
    if nameflow_data is not None:
        for i in range(len(nameflow_data['nodes'])):
            node = nameflow_data['nodes'][i]
            relations = nameflow_data['relations'][i]
            pdg_node = find_node_in_graph(node, apdg)
            if pdg_node:
                for relation in relations:
                    if relation == -1:
                        continue
                    other_node = nameflow_data['nodes'][relation]
                    other_pdg_node = find_node_in_graph(other_node, apdg)
                    if other_pdg_node:
                        apdg.add_edge(pdg_node, other_pdg_node, key=3, color='darkorchid', style='bold',
                                      label='%s %s %s %s' %
                                            (node['symbolKind'], node['kind'], node['type'], node['name'])
                                      )

    return apdg
