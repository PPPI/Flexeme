import os
import sys
import logging

import jsonpickle
from tqdm import tqdm

from flexeme.Util.general_util import get_pattern_paths
from flexeme.wl_kernel.wl_kernel_untangle import validate as wl_validate
from flexeme.du_chains.DU_chains_closure import validate as du_validate

logging.basicConfig(level=logging.DEBUG,
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[logging.StreamHandler()])

if __name__ == '__main__':
    times = int(sys.argv[1])
    mode = sys.argv[2].lower()  # Options are du and wl
    if mode == 'du':
        logging.info("du mode")
        repository_names = sys.argv[3:]
        out_name = 'du_results_raw'
    else:
        logging.info("wl mode")
        edges_kept = 'all'
        k_hop = int(sys.argv[3])
        repository_names = sys.argv[4:]
        out_name = 'wl_%s_%d_results_raw' % (edges_kept, k_hop)

    # tqdm is eating logging statements for some reason. Disabled for now.
    # for repository_name in tqdm(repository_names):
    for repository_name in repository_names:
        all_graphs = sorted(
            get_pattern_paths('*merged.dot', os.path.join('.', 'data', 'corpora_clean', repository_name)))
        logging.info(f"Found {len(all_graphs)} files for repository {repository_name}")
        os.makedirs('./out/%s' % repository_name, exist_ok=True)
        try:
            with open('./out/%s/%s.csv' % (repository_name, out_name)) as f:
                lines = f.read()
            lines = lines.split('\n')
            lines = lines[1:]
            datapoints_done = [l.split(',')[0] for l in lines]
        except FileNotFoundError:
            logging.error(f"File not found: {'./out/%s/%s.csv' % (repository_name, out_name)}")
            datapoints_done = list()
            with open('./out/%s/%s.csv' % (repository_name, out_name), 'w') as f:
                f.write('Datapoint,Concepts,Accuracy,Overlap,Cover,Time\n')
        try:
            with open('./out/%s/%s.json' % (repository_name, out_name)) as f:
                logging.warning(f"Found {f.name}. Skipping.")
                continue
        except FileNotFoundError:
            pass
        # Uncomment to skip evaluation for chains already evaluated
        # all_graphs = [d for d in all_graphs
        #               if os.path.basename(os.path.dirname(os.path.dirname(d))) not in datapoints_done]
        if mode == 'du':
            du_validate(all_graphs, times, repository_name)
        else:
            wl_validate(all_graphs, times, k_hop, repository_name)

        # Uncomment to enable completion of evaluation acknowledgement
        # with open('./out/%s/%s.json' % (repository_name, out_name), 'w') as f:
        #     f.write(jsonpickle.encode({'done'}))
