import sys
import os

import networkx as nx

from tangle_concerns.generate_corpus import generate_pdg
from deltaPDG.Util.merge_deltaPDGs import merge_deltas_for_a_commit
from Util.general_util import get_pattern_paths


def merge_files_pdg(path_to_commit):
    paths = get_pattern_paths('*.java.dot', path_to_commit)
    print(paths)
    merged = merge_deltas_for_a_commit(paths)
    nx.drawing.nx_pydot.write_dot(merged, os.path.join(path_to_commit, 'merged.dot'))


def untangle(repository_path, revision, sourcepath, classpath):
    temp_path = '.tmp'
    id = 0
    extractor_path = 'extractors/codechanges-checker-0.1-all.jar'

    generate_pdg(revision, repository_path, id, temp_path, extractor_path, sourcepath, classpath)
    # generate_pdg: generate_corpus#worker (list files, make pdg for each file, make ∂pdg
    # -> pdg.dot

    # merge pdg: all pdg.dot for each file to merged.dot
    merge_files_pdg(os.path.join('./out/corpora_raw', revision))

    # wl_kernel_untangle_validate(merged.dot)

    #     export_results
    pass


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
