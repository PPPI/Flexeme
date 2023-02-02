import itertools
import os
import random
import sys

import jsonpickle
from tqdm import tqdm

from Util.general_util import get_pattern_paths
from wl_kernel.wl_kernel_untangle import validate

if __name__ == '__main__':
    times = int(sys.argv[1])
    edges_kept = sys.argv[2]
    k_hop = int(sys.argv[3])
    repository_name = sys.argv[4]
    l = [False, True]
    configs = list(itertools.product(l, repeat=3))[1:]
    for with_data, with_call, with_name in tqdm(configs):
        suffix = ""
        edges_kept = ""
        if with_data:
            suffix += "d"
            edges_kept += "data"
        if with_call:
            suffix += "c"
            edges_kept += "control"
        if with_name:
            suffix += "n"
            edges_kept += "name"

        all_graphs = sorted(
            get_pattern_paths('*merged.dot', os.path.join('.', 'data', 'corpora_clean', repository_name)))
        try:
            with open('./out/%s/wl_%s_%d_results_%s.csv' % (repository_name, edges_kept, k_hop, suffix)) as f:
                lines = f.read()
            lines = lines.split('\n')
            lines = lines[1:]
            datapoints_done = [l.split(',')[0] for l in lines]
        except FileNotFoundError:
            datapoints_done = list()
            with open('./out/%s/wl_%s_%d_results_%s.csv' % (repository_name, edges_kept, k_hop, suffix), 'w') as f:
                f.write('Datapoint,Concepts,Accuracy,Overlap,Time\n')
        try:
            with open('./out/%s/wl_%s_%d_results_%s.json' % (repository_name, edges_kept, k_hop, suffix)) as f:
                continue
        except FileNotFoundError:
            pass
        all_graphs = [d for d in all_graphs
                      if os.path.basename(os.path.dirname(os.path.dirname(d))) not in datapoints_done]
        random.shuffle(all_graphs)
        if len(all_graphs) > 0:
            validate(all_graphs, times, k_hop, repository_name, edges_kept=edges_kept, suffix=suffix)
            with open('./out/%s/wl_%s_%d_results_%s.json' % (repository_name, edges_kept, k_hop, suffix), 'w') as f:
                f.write(jsonpickle.encode({'done'}))
