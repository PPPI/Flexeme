import os
import sys

import jsonpickle
from tqdm import tqdm

from Util.general_util import get_pattern_paths

if __name__ == '__main__':
    times = int(sys.argv[1])
    mode = sys.argv[2].lower()  # Options are du and wl
    if mode == 'du':
        from du_chains.DU_chains_closure import validate as du_validate
        repository_names = sys.argv[3:]
        out_name = 'du_results_raw'
    else:
        from wl_kernel.wl_kernel_untangle import validate as wl_validate
        edges_kept = 'all'
        k_hop = int(sys.argv[3])
        repository_names = sys.argv[4:]
        out_name = 'wl_%s_%d_results_raw' % (edges_kept, k_hop)

    for repository_name in tqdm(repository_names):
        all_graphs = sorted(
            get_pattern_paths('*merged.dot', os.path.join('.', 'data', 'corpora_clean', repository_name)))
        os.makedirs('./out/%s' % repository_name, exist_ok=True)
        try:
            with open('./out/%s/%s.csv' % (repository_name, out_name)) as f:
                lines = f.read()
            lines = lines.split('\n')
            lines = lines[1:]
            datapoints_done = [l.split(',')[0] for l in lines]
        except FileNotFoundError:
            datapoints_done = list()
            with open('./out/%s/%s.csv' % (repository_name, out_name), 'w') as f:
                f.write('Datapoint,Concepts,Accuracy,Overlap,Cover,Time\n')
        try:
            with open('./out/%s/%s.json' % (repository_name, out_name)) as f:
                continue
        except FileNotFoundError:
            pass
        all_graphs = [d for d in all_graphs
                      if os.path.basename(os.path.dirname(os.path.dirname(d))) not in datapoints_done]
        if mode == 'du':
            du_validate(all_graphs, times, repository_name)
        else:
            wl_validate(all_graphs, times, k_hop, repository_name)
        with open('./out/%s/%s.json' % (repository_name, out_name), 'w') as f:
            f.write(jsonpickle.encode({'done'}))
