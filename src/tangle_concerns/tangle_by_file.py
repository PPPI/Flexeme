#
# Generates multiple lists of commits. Each list of commit represent a tangled commit.
#
import datetime
import json
import sys
import os
from collections import defaultdict
from typing import List, Tuple, Any

import numpy as np

from deltaPDG.Util.git_util import Git_Util

KEYWORDS = {'FIX', 'FIXES', 'FIXED', 'IMPLEMENTS', 'IMPLEMENTED', 'IMPLEMENT', 'BUG', 'FEATURE', }

def get_history_by_file(gh: Git_Util, repository_root: str, files_considered: List[str]):
    return {filename: gh.get_commits_for_file(filename, repository_root) for filename in files_considered}


def merge_commit_chains(list_of_pairs: List[Tuple[str, str]]) -> List[Tuple[Any]]:
    merged_chains = list()
    while list_of_pairs:
        after, before = list_of_pairs[0]
        list_of_pairs = list_of_pairs[1:]
        result = [before, after]
        target = after
        while target:
            new = list(filter(lambda p: p[-1] == target, list_of_pairs))
            if len(new) == 1:
                target, _ = new[0]
                result.append(target)
                list_of_pairs.remove(new[0])
            elif len(new) == 0:
                target = None
        merged_chains.append(tuple(result[::-1]))
    return merged_chains


def get_cooccurrence_row_up_to_commit(current_commit: str, file1_index: int, file2_index: int, candidates, occurrence):
    selected_idx = list()
    for i in range(candidates.index(current_commit)):
        if occurrence[(file1_index, i)] and occurrence[(file2_index, i)]:
            selected_idx.append(i)
    return np.squeeze(np.asarray(occurrence[:, selected_idx].sum(axis=1)))


def filter_pairs_by_predicates(list_of_pairs: List[Tuple[str, str]], predicates: Any) -> List[Tuple[str, str]]:
    result = list()
    for i in range(len(list_of_pairs)):
        if all(map(lambda pred: pred(*list_of_pairs[i]), predicates)):
            result.append(list_of_pairs[i])
    return result


def commits_within(gh, path, days):
    def inner_predicate(sha1, sha2):
        return gh.get_time_between_commits(sha1, sha2, path) <= datetime.timedelta(days=days)

    return inner_predicate


def same_author(gh, path):
    def inner_predicate(sha1, sha2):
        author_old = gh.get_author(sha1, path)
        author_new = gh.get_author(sha2, path)
        return author_old == author_new

    return inner_predicate


def diff_regions_size(gh, path, max_regions):
    def inner_predicate(sha1, sha2):
        return len(gh.merge_diff_into_diff_regions(gh.process_diff_between_commits(sha1, sha2, path))) <= max_regions

    return inner_predicate


def both_are_atomic(gh, path):
    def inner_predicate(sha1, sha2):
        commit_msg1 = gh.get_commit_msg(sha1, path)
        commit_msg2 = gh.get_commit_msg(sha2, path)
        return len(set(commit_msg1.upper().split()).intersection(KEYWORDS)) <= 1 \
               and len(set(commit_msg2.upper().split()).intersection(KEYWORDS)) <= 1

    return inner_predicate


def tangle_by_file(subject, temp_loc):
    days = 14
    up_to_concerns = 4

    os.makedirs(temp_loc, exist_ok=True)
    git_handler = Git_Util(temp_dir=temp_loc)

    with git_handler as gh:
        temp = gh.move_git_repo_to_tmp(subject)
        candidates = gh.get_all_commit_hashes_authors_dates_messages(temp)

        candidates_by_author = defaultdict(list)
        for sha, author, date, msg, diff in candidates:
            candidates_by_author[author].append((sha, date, msg))
        candidates_by_author = dict(candidates_by_author)

        history_flat = list()
        for candidates in candidates_by_author.values():
            candidates = sorted(candidates, key=lambda p: p[1])
            index = 0
            while index < len(candidates):
                sha, date, msg = candidates[index]
                index += 1
                if len(set(msg.upper().split()).intersection(KEYWORDS)) <= 1:
                    chain = [sha]
                    for offset in range(1, up_to_concerns):
                        try:
                            new_sha, new_date, new_msg = candidates[index + offset]
                            if new_date - date <= datetime.timedelta(days=days) \
                                    and len(set(new_msg.upper().split()).intersection(KEYWORDS)) <= 1:
                                chain.append(new_sha)
                                index += 1
                            else:
                                break
                        except IndexError:
                            break
                    if len(chain) > 1:
                        history_flat.append(chain)

    return history_flat


if __name__ == '__main__':
    repository_name = sys.argv[1]

    os.makedirs("out/%s" % repository_name, exist_ok=True)
    outfile = 'out/%s/%s_history_filtered_flat.json' % (repository_name, repository_name)
    history_flat = tangle_by_file('./subjects/%s' % repository_name, ".tmp")
    with open(outfile, 'w') as f:
        f.write(json.dumps(history_flat))
