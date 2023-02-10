import sys
import os

import networkx as nx

from flexeme.tangle_concerns.generate_corpus import generate_pdg
from flexeme.deltaPDG.Util.merge_deltaPDGs import merge_deltas_for_a_commit
from flexeme.Util.general_util import get_pattern_paths
from flexeme.tangle_concerns.scan_and_clean_corpora import clean_graph
from flexeme.wl_kernel.wl_kernel_untangle import validate


def merge_files_pdg(path_to_commit):
    paths = get_pattern_paths('*.java.dot', path_to_commit)
    merged = merge_deltas_for_a_commit(paths)
    merged_path = os.path.join(path_to_commit, 'merged.dot')
    nx.drawing.nx_pydot.write_dot(merged, merged_path)
    return merged_path


def untangle(repository_path, revision, sourcepath, classpath):
    temp_path = '.tmp'
    id = 0
    extractor_path = 'extractors/codechanges-checker-0.1-all.jar'

    repository_path = os.path.abspath(os.path.normpath(repository_path))
    corpus_name = os.path.basename(repository_path)

    generate_pdg(revision, repository_path, id, temp_path, extractor_path, sourcepath, classpath)

    # merge pdg: all pdg.dot for each file to merged.dot
    merged_path = merge_files_pdg(os.path.join('./out/corpora_raw', corpus_name, revision, '0'))

    # cleaning and normalize the groups across all changed files.
    clean_path = clean_graph(merged_path, corpus_name)

    validate([clean_path], 1, 2, "Cli-1")
    # -> Results in data/corpora_clean/Cli-1/Cli-1/1/merged_output_wl_x.dot
    # -> Nodes with X:.... are labelled. X: is the label.s

    # Converting results to the benchmark format is done in the benchmark itself.


def main():
    args = sys.argv[1:]

    if len(args) < 2:
        print("Expected 2 arguments: <repository path> <revision>")
        exit(-1)

    repository_path = args[0]
    revision = args[1]
    sourcepath = args[2]
    classpath = args[3]

    untangle(repository_path, revision, sourcepath, classpath)


if __name__ == "__main__":
    main()
