import os
import random
import sys
from threading import Thread

import jsonpickle
import numpy as np
import scipy.sparse
from tqdm import tqdm

from Util.evaluation import evaluate
from Util.general_util import get_pattern_paths
from confidence_voters.Util.generate_corpus_file import build_occurrence_matrix, build_corpus
from confidence_voters.confidence_voters import cluster_diffs, convert_diff_to_diff_regions
from confidence_voters.confidence_voters_graph_only import cluster_diffs as graph_cluster_diffs
from deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx, get_context_from_nxgraph


def driver(times_, out_name_, projects_, worker_wrapper_, temp_dir_):
    for repository_name in tqdm(projects_):
        json_location = './out/%s/%s_history.json' % (repository_name, repository_name)
        subject_location = './subjects/%s' % repository_name

        try:
            with open('./out/%s/bl_corpus_clean.json' % repository_name) as f:
                corpus, file_len_map = jsonpickle.decode(f.read())
        except FileNotFoundError:
            corpus, file_len_map = build_corpus(json_location, subject_location, temp_dir_)
            with open('./out/%s/bl_corpus.json' % repository_name, 'w') as f:
                f.write(jsonpickle.encode((corpus, file_len_map)))

        try:
            with open('./out/%s/file_index.json' % repository_name) as f:
                file_index_map = jsonpickle.decode(f.read())
            occurrence_matrix = scipy.sparse.load_npz('./out/%s/occurrence_matrix.npz' % repository_name)
        except FileNotFoundError:
            occurrence_matrix, file_index_map = build_occurrence_matrix(subject_location, temp_dir_, None)
            with open('./out/%s/file_index.json' % repository_name, 'w') as f:
                f.write(jsonpickle.encode(file_index_map))
            scipy.sparse.save_npz('./out/%s/occurrence_matrix.npz' % repository_name, occurrence_matrix)

        all_graphs = sorted(
            get_pattern_paths('*merged.dot', os.path.join('.', 'data', 'corpora_clean', repository_name)))
        os.makedirs('./out/%s' % repository_name, exist_ok=True)

        try:
            with open(os.path.join('out', repository_name, out_name_ + '.csv')) as f:
                lines = f.read()
            lines = lines.split('\n')
            lines = lines[1:]
            datapoints_done = [l.split(',')[0] for l in lines]
        except FileNotFoundError:
            datapoints_done = list()
            with open(os.path.join('out', repository_name, out_name_ + '.csv'), 'w') as f:
                f.write('Datapoint,Concepts,Accuracy,Overlap,Time\n')
        try:
            with open(os.path.join('out', repository_name, out_name_ + '.json')) as _:
                continue
        except FileNotFoundError:
            pass

        all_graphs = [d for d in all_graphs
                      if os.path.basename(os.path.dirname(os.path.dirname(d))) not in datapoints_done]
        random.shuffle(all_graphs)

        corpus = {k: (i, convert_diff_to_diff_regions(v)) for k, (i, v) in corpus.items()}
        work_list = all_graphs
        n_workers = 1
        chunck_size = int(len(work_list) / n_workers)
        while chunck_size == 0:
            n_workers -= 1
            chunck_size = int(len(work_list) / n_workers)
        chuncked = [work_list[i:i + chunck_size] for i in range(0, len(work_list), chunck_size)]

        worker = worker_wrapper_(corpus, file_len_map, repository_name, occurrence_matrix, file_index_map, times_)

        threads = []
        for work in chuncked:
            t = Thread(target=worker, args=(work,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        with open(os.path.join('out', repository_name, out_name_ + '.json'), 'w') as f:
            f.write(jsonpickle.encode({'done'}))


if __name__ == '__main__':
    times = int(sys.argv[1])
    out_name = sys.argv[2]
    graph_version = True if sys.argv[3].lower() == 'true' else False
    if graph_version:
        projects = sys.argv[4:]


        def worker_wrapper(_, file_len_map, repository_name, occurrence_matrix, file_index_map, times_):
            def worker(work):
                for data_point_name in tqdm(work, leave=False):
                    concepts = int(os.path.basename(os.path.dirname(data_point_name)))
                    data_point_name = os.path.basename(os.path.dirname(os.path.dirname(data_point_name)))
                    try:
                        file_lens = file_len_map[data_point_name]
                        graph_location = os.path.join('.', 'data', 'corpora_clean',
                                                      repository_name, data_point_name,
                                                      str(concepts), 'merged.dot')
                        deltaPDG = obj_dict_to_networkx(read_graph_from_dot(graph_location))
                        context = get_context_from_nxgraph(deltaPDG)

                        try:
                            _, truth = list(zip(*[(n, d['community']) for n, d in deltaPDG.nodes(data=True)
                                                  if 'color' in d.keys() and d['color'] != 'orange'
                                                  and 'community' in d.keys()]))
                        except ValueError:
                            return

                        labels, time_ = graph_cluster_diffs(deltaPDG,
                                                            context,
                                                            concepts,
                                                            file_lens,
                                                            occurrence_matrix,
                                                            file_index_map,
                                                            times_)
                        truth = np.asarray(truth).astype(int)
                        labels = np.asarray(labels).astype(int)
                        acc, overlap = evaluate(labels, truth,
                                                q=max(concepts, np.max(labels) + 1))
                        with open(os.path.join('out', repository_name, out_name + '.csv'), 'a') as f:
                            f.write(
                                data_point_name + ',' + str(concepts) + ',' + str(acc) + ',' + str(overlap) + ',' + str(
                                    time_) + '\n')
                    except FileNotFoundError:
                        pass
                    except KeyError:
                        with open(os.path.join('out', repository_name, out_name + '.csv'), 'a') as f:
                            f.write(
                                data_point_name + ',' + str(concepts) + ',' + str(float('nan')) + ','
                                + str(float('nan')) + ',' + str(0.0) + '\n')

            return worker
    else:
        edges_to_keep = sys.argv[4]
        if edges_to_keep == 'None':
            edges_to_keep = None
        use_file_dist = sys.argv[5].lower() == 'true'
        use_call_distance = sys.argv[6].lower() == 'true'
        use_data = sys.argv[7].lower() == 'true'
        use_namespace = sys.argv[8].lower() == 'true'
        use_change_coupling = sys.argv[9].lower() == 'true'

        suffix = '_'
        if use_file_dist:
            suffix += 'fd_'
        if use_call_distance:
            suffix += 'cd_'
        if use_data:
            suffix += 'd_'
        if use_namespace:
            suffix += 'ns_'
        if use_change_coupling:
            suffix += 'cc_'

        projects = sys.argv[10:]


        def worker_wrapper(corpus, file_len_map, repository_name, occurrence_matrix, file_index_map, times_):
            def worker(work):
                for data_point_name in tqdm(work, leave=False):
                    data_point_name = os.path.basename(os.path.dirname(os.path.dirname(data_point_name)))
                    try:
                        concepts, data = corpus[data_point_name]
                    except KeyError:
                        concepts, data = 0, []
                    if len(data) > 1:
                        try:
                            try:
                                file_lens = file_len_map[data_point_name]
                            except KeyError:
                                continue
                            labels, time_ = cluster_diffs(concepts,
                                                          data,
                                                          os.path.join('.', 'data', 'corpora_clean',
                                                                       repository_name, data_point_name,
                                                                       str(concepts), 'merged.dot'),
                                                          file_lens,
                                                          occurrence_matrix,
                                                          file_index_map,
                                                          times_,
                                                          use_file_dist=use_file_dist,
                                                          use_call_distance=use_call_distance,
                                                          use_change_coupling=use_change_coupling,
                                                          use_data=use_data,
                                                          use_namespace=use_namespace)
                            truth = [p['label'] for p in data]
                            acc, overlap = evaluate(labels, np.asarray(truth), q=concepts)
                            with open('./out/%s/bl_results%s.csv' % (repository_name, suffix), 'a') as f:
                                f.write(data_point_name + ',' + str(concepts) + ','
                                        + str(acc) + ',' + str(overlap) + ',' + str(time_) + '\n')
                        except FileNotFoundError:
                            pass
                        except KeyError:
                            pass

            return worker

    driver(times, out_name, projects, worker_wrapper, temp_dir_='D:\Temp')
