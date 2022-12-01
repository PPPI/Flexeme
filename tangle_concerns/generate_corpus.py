import json
import logging
import os
import sys
from threading import Thread

import jsonpickle
import networkx as nx

from deltaPDG.Util.generate_pdg import PDG_Generator
from deltaPDG.Util.git_util import Git_Util
from deltaPDG.deltaPDG import deltaPDG
from tangle_concerns.tangle_by_file import tangle_by_file

logging.basicConfig(level=logging.DEBUG,
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[logging.StreamHandler()])

def mark_originating_commit(dpdg, marked_diff, filename):
    dpdg = dpdg.copy()

    for node, data in dpdg.nodes(data=True):
        if 'color' in data.keys() and data['color'] != 'orange':
            start, end = [int(l) for l in data['span'].split('-')] if '-' in data['span'] else [-1, -1]

            if start == end == -1:
                continue

            change_type = '+' if data['color'] == 'green' else '-'
            masked_diff = [p for p in marked_diff if p[0] == change_type and p[1] == filename]

            label = data['label'].replace('\'\'', '"')
            if 'Entry' in label:
                label = label[len('Entry '):].split('(')[0].split('.')[-1]
            elif 'Exit' in label:
                label = label[len('Exit '):].split('(')[0].split('.')[-1]
            if 'lambda' in label:
                label = '=>'
            if '\\r' in label:
                label = label.split('\\r')[0]
            elif '\\n' in label:
                label = label.split('\\n')[0]

            community = max([cm
                             for _, _, after_coord, before_coord, line, cm in masked_diff
                             if label in line and (start <= after_coord <= end or start <= before_coord <= end)],
                            default=0)

            dpdg.node[node]['community'] = community

    return dpdg


def mark_origin(tangled_diff, atomic_diffs):
    output = list()
    for change_type, file, after_coord, before_coord, line in tangled_diff:
        if change_type != ' ':
            relevant = {i: [(ct, f, ac, bc, ln) for ct, f, ac, bc, ln in diff
                            if file == f and line.strip() == ln.strip()]
                        for i, diff in atomic_diffs.items()}
            relevant = [i for i, diff in relevant.items() if len(diff) > 0]
            label = max(relevant, default=0)
            output.append((change_type, file, after_coord, before_coord, line, label))
    return output


def worker(work, subject_location, id_, temp_loc, extractor_location):
    logging.info("Starting worker" + str(id_))
    repository_name = os.path.basename(subject_location)
    method_fuzziness = 100
    node_fuzziness = 100

    git_handler = Git_Util(temp_dir=temp_loc)

    with git_handler as gh:
        v1 = gh.move_git_repo_to_tmp(subject_location)
        v2 = gh.move_git_repo_to_tmp(subject_location)
        temp_dir_worker = temp_loc + '/%d' % id_
        os.makedirs(temp_dir_worker, exist_ok=True)
        v1_pdg_generator = PDG_Generator(extractor_location=extractor_location,
                                         repository_location=v1,
                                         target_filename='before_pdg.dot',
                                         target_location=temp_dir_worker)
        v2_pdg_generator = PDG_Generator(extractor_location=extractor_location,
                                         repository_location=v2,
                                         target_filename='after_pdg.dot',
                                         target_location=temp_dir_worker)
        for chain in work:
            logging.info('Working on chain: %s' % str(chain))
            from_ = chain[0]
            gh.set_git_to_rev(from_ + '^', v1)
            gh.set_git_to_rev(from_, v2)

            labeli_changes = dict()
            labeli_changes[0] = gh.process_diff_between_commits(from_ + '^', from_, v2)
            previous_sha = from_
            i = 1
            for to_ in chain[1:]:
                gh.cherry_pick_on_top(to_, v2)

                changes = gh.process_diff_between_commits(from_ + '^', to_, v2)
                labeli_changes[i] = gh.process_diff_between_commits(previous_sha, to_, v2)
                i += 1
                previous_sha = to_
                files_touched = {filename for _, filename, _, _, _ in changes if
                                 os.path.basename(filename).split('.')[-1] == 'java'} # and not filename.endswith("Tests.java")
                logging.info(f"{len(files_touched)} files affected")
                for filename in files_touched:
                    logging.info(f"Generating PDGs for {filename}")
                    try:
                        output_path = './out/corpora_raw/%s/%s_%s/%d/%s.dot' % (
                            repository_name, from_, to_, i, os.path.basename(filename))
                        # try:
                        #     with open(output_path) as f:
                        #         print('Skipping %s as it exits' % output_path)
                        #         f.read()
                        # except FileNotFoundError:
                        v1_pdg_generator(filename)
                        v2_pdg_generator(filename)
                        logging.info(f"PDGs generated for {from_} and {to_}")
                        delta_gen = deltaPDG(temp_dir_worker + '/before_pdg.dot', m_fuzziness=method_fuzziness,
                                             n_fuzziness=node_fuzziness)
                        delta_pdg = delta_gen(temp_dir_worker + '/after_pdg.dot',
                                              [ch for ch in changes if ch[1] == filename])
                        delta_pdg = mark_originating_commit(delta_pdg, mark_origin(changes, labeli_changes), filename)
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        nx.drawing.nx_pydot.write_dot(delta_pdg, output_path)
                    except Exception as e:
                        raise e


if __name__ == '__main__':
    if len(sys.argv) != 7:
        print('To use this script please run as `[python] generate_corpus.py '
              '<json file location> <git location> <temp location> '
              '<thread id start> <number of threads> <extractor location>')
        exit(1)
    json_location = sys.argv[1]
    subject_location = sys.argv[2]
    n_workers = int(sys.argv[5])
    temp_loc = sys.argv[3]
    extractor_location = sys.argv[6]

    os.makedirs(temp_loc, exist_ok=True)

    try:
        with open(json_location) as f:
            logging.info("Found chains")
            list_to_tangle = jsonpickle.decode(f.read())
    except FileNotFoundError:
        list_to_tangle = tangle_by_file(subject_location, temp_loc)
        with open(json_location, 'w') as f:
            f.write(json.dumps(list_to_tangle))

    chunck_size = int(len(list_to_tangle) / n_workers)
    list_to_tangle = [list_to_tangle[i:i + chunck_size] for i in range(0, len(list_to_tangle), chunck_size)]

    threads = []
    id_ = int(sys.argv[4])
    for work in list_to_tangle:
        t = Thread(target=worker, args=(work, subject_location, id_, temp_loc, extractor_location))
        id_ += 1
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
