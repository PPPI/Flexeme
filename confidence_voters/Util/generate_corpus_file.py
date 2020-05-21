import os
import random
import sys
from collections import defaultdict
from functools import reduce
from threading import Thread
from typing import List, Dict

import jsonpickle
import scipy.sparse
import scipy.spatial
import scipy.special
from tqdm import tqdm

from deltaPDG.Util.git_util import Git_Util


def build_corpus(json_location_, subject_location_, temp_dir_):
    with open(json_location_) as f_:
        list_to_tangle = jsonpickle.decode(f_.read())

    n_workers = 2
    chunk_size = int(len(list_to_tangle) / n_workers)
    chunked = [list_to_tangle[i:i + chunk_size] for i in range(0, len(list_to_tangle), chunk_size)]

    marked_changes = dict()
    file_length_map = defaultdict(lambda: dict())

    def worker(work_):
        git_handler = Git_Util(temp_dir=temp_dir_)
        with git_handler as gh:
            v1 = gh.move_git_repo_to_tmp(subject_location_)
            v2 = gh.move_git_repo_to_tmp(subject_location_)
            for chain in work_:
                print('Working on chain: %s' % str(chain))
                from_ = chain[0]
                gh.set_git_to_rev(from_ + '^', v1)
                gh.set_git_to_rev(from_, v2)

                label_changes = dict()
                label_changes[0] = diffs_by_file(gh.process_diff_between_commits(from_ + '^', from_, v2))
                previous_sha = from_
                i = 1
                for to_ in chain[1:]:
                    gh.cherry_pick_on_top(to_, v2)

                    changes = gh.process_diff_between_commits(from_ + '^', to_, v2)
                    files = {filename for _, filename, _, _, _ in changes if
                             os.path.basename(filename).split('.')[-1] == 'cs'}
                    for file in files:
                        try:
                            with open(v2 + file, encoding='utf-8', errors='replace') as f__:
                                file_length_map[from_ + '_' + to_].update(**{file: len(f__.read().split('\n'))})
                        except FileNotFoundError:
                            file_length_map[from_ + '_' + to_].update(**{file: -1})
                    label_changes[i] = diffs_by_file(gh.process_diff_between_commits(previous_sha, to_, v2))
                    i += 1
                    previous_sha = to_
                    marked_changes[from_ + '_' + to_] = (i, mark_origin(changes, label_changes))

    threads = []
    for work in chunked:
        t = Thread(target=worker, args=(work,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return marked_changes, dict(file_length_map)


def mark_origin(tangled_diff, atomic_diffs):
    output = list()
    for change_type, file, after_coord, before_coord, line in tangled_diff:
        if change_type != ' ':
            relevant = {i: [ln for _, _, _, ln in diff[file]
                            if line.strip() == ln.strip()]
                        for i, diff in atomic_diffs.items() if file in diff.keys()}
            relevant = [i for i, diff in relevant.items() if len(diff) > 0]
            label = max(relevant, default=0)
            output.append((change_type, file, after_coord, before_coord, line, label))
    return output


def diffs_by_file(diff):
    output = defaultdict(list)
    for ct, f_, ac, bc, ln in diff:
        output[f_].append((ct, ac, bc, ln))
    return dict(output)


def build_occurrence_matrix(subject_location_, temp_dir_, filter_commits):
    git_handler = Git_Util(temp_dir=temp_dir_)
    with git_handler as gh:
        temp = gh.move_git_repo_to_tmp(subject_location_)
        candidates = gh.get_all_commit_hashes_authors_dates_messages(temp)
        all_commits = list()
        all_files = list()
        file_commit_map = defaultdict(list)
        for sha, author, date, msg, diff in candidates:
            if (filter_commits is not None and sha in filter_commits) or filter_commits is None:
                all_commits.append(sha)
                files = {fn for _, fn, _, _, _ in diff}
                for file in files:
                    file_commit_map[file].append(sha)
                    if 'file' not in all_files:
                        all_files.append(file)

        file_commit_map = dict(file_commit_map)

        occurrence_matrix_ = generate_occurrence_matrix(all_files, all_commits, file_commit_map)
        return occurrence_matrix_, {fn: i for i, fn in enumerate(all_files)}


def generate_occurrence_matrix(list_of_files: List[str],
                               list_of_commits: List[str],
                               file_commit_map: Dict[str, List[str]]) -> scipy.sparse.csc_matrix:
    indices = reduce(lambda p1, p2: (p1[0] + p2[0], p1[1] + p2[1]),
                     map(lambda p: ([list_of_files.index(p[0])] * len(p[1]),
                                    [list_of_commits.index(c) for c in p[1]]), file_commit_map.items()), ([], []))
    return scipy.sparse.csc_matrix(([1] * len(indices[0]), indices), shape=(len(list_of_files), len(list_of_commits)))


if __name__ == '__main__':
    temp_dir = sys.argv[1]
    projects = sys.argv[2:]
    random.shuffle(projects)
    for repository_name in tqdm(projects):
        json_location = './out/%s/%s_history.json' % (repository_name, repository_name)
        subject_location = './subjects/%s' % repository_name
        occurrence_matrix, file_index_map = build_occurrence_matrix(subject_location, temp_dir, None)
        with open('./out/%s/file_index.json' % repository_name, 'w') as f:
            f.write(jsonpickle.encode(file_index_map))
        scipy.sparse.save_npz('./out/%s/occurrence_matrix.npz' % repository_name, occurrence_matrix)
        corpus, file_len_map = build_corpus(json_location, subject_location, temp_dir)
        os.makedirs('./out/%s/' % repository_name, exist_ok=True)
        with open('./out/%s/bl_corpus.json' % repository_name, 'w') as f:
            f.write(jsonpickle.encode((corpus, file_len_map)))
