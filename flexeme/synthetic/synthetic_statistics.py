#!/usr/bin/env python3

import logging
import os
import subprocess
import sys
import pprint
from dotenv import load_dotenv
from git import Repo

import jsonpickle
from flexeme.deltaPDG.Util.git_util import Git_Util

logging.basicConfig(level=logging.DEBUG,
                    format='[%(asctime)s][%(name)s] %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[logging.StreamHandler()])

logging.getLogger("git.cmd").setLevel(logging.INFO)


def main(synthetic_chains, subject_location):
    """
    Analyze the synthetic commit chains and generate statistics. Computes the following statistics:
    - Number of chains
    - Number of data points
    - Number of files per data point
    - Number of files edited in multiple commits in the chain.
    A data point is one instance of a synthetic commit produced by the commit chain.
    :param synthetic_chains: list of synthetic chains. Each chain is a list of real commit hashes.
    :param subject_location: path to the repository
    """
    repository_name = os.path.basename(subject_location)
    temp_loc = '/tmp/synth'
    git_handler = Git_Util(temp_dir="/tmp")

    logging.info(f'Chains %s', len(synthetic_chains))

    with git_handler as gh:
        v1 = gh.move_git_repo_to_tmp(subject_location)
        v2 = gh.move_git_repo_to_tmp(subject_location)
        os.makedirs(temp_loc, exist_ok=True)

        datapoint_counter = 0

        print('project', 'datapoint', 'n_commits', 'n_files', 'n_files_updated_i', 'shared_files', sep=',')
        project = repository_name

        for chain in synthetic_chains:
            logging.info('Working on chain: %s' % str(chain))
            from_ = chain[0]

            repo = Repo(v1)
            commit = repo.commit(from_)

            if len(commit.parents) == 0:
                logging.warning(f'Ignoring {from_} because the commit has no parents')
                continue

            gh.set_git_to_rev(from_ + '^', v1)
            gh.set_git_to_rev(from_, v2)
            labeli_changes = dict()
            labeli_changes[0] = gh.process_diff_between_commits(from_ + '^', from_, v2)

            edits = dict()
            for file in [filename for _, filename, _, _, _ in labeli_changes[0] if os.path.basename(filename).split('.')[-1] == 'java']:
                if edits.get(file) is None:
                    edits[file] = set()
                edits[file].add(from_)

            previous_sha = from_
            i = 1

            for to_ in chain[1:]:
                datapoint_counter += 1
                datapoint = f'{from_}_{to_}'
                n_commits = i + 1
                logging.info(f'Datapoint: {datapoint}')

                try:
                    # Make commits in the chain sequential in the repo.
                    gh.cherry_pick_on_top(to_, v2)

                    # Get the diff between the two commits using git diff commit1..commit2
                    # all the changes in from_ and to_
                    changes = gh.process_diff_between_commits(from_ + '^', to_, v2)
                    # only the changes added in to_
                    labeli_changes[i] = gh.process_diff_between_commits(previous_sha, to_, v2)

                    files_touched = {filename for _, filename, _, _, _ in changes if os.path.basename(filename).split('.')[-1] == 'java'}

                    files_updated_i = {filename for _, filename, _, _, _ in labeli_changes[i]  if os.path.basename(filename).split('.')[-1] == 'java'}
                    for file in files_updated_i:
                        if edits.get(file) is None:
                            edits[file] = set()
                        edits[file].add(to_)

                    shared_edits = {k: v for k, v in edits.items() if len(v) > 1}
                    print(project, datapoint, n_commits, len(files_touched), len(files_updated_i), len(shared_edits.keys()), sep=',')

                    # logging.info(f'Files changed total: {len(files_touched)}')
                    # logging.info(f'Datapoint level: {i}')
                    # logging.info("Changes:")
                    # logging.info(changes)
                    # logging.info("Label i Changes:")
                    # logging.info(labeli_changes[i])
                    # logging.info("Shared changes:")
                    # logging.info(len(shared_edits.keys()))

                except subprocess.CalledProcessError as e:
                    logging.error(f'Error while processing {datapoint}: {e.stderr}')
                    logging.error(f'Skipping remaining of the chain {chain}.')
                    break

                i += 1
                previous_sha = to_

        logging.info(f'Number of datapoints: {datapoint_counter}')


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) != 2:
        print('usage: `[python] generate_corpus.py <synthetic commits file> <repository path>')
        sys.exit(1)
    json_location = sys.argv[1]
    subject_location = sys.argv[2]

    load_dotenv() # Load .env file
    try:
        with open(json_location) as f:
            synthetic_chains = jsonpickle.decode(f.read())
    except FileNotFoundError:
        logging.error(f"File {json_location} not found")
        sys.exit(1)

    main(synthetic_chains, subject_location)