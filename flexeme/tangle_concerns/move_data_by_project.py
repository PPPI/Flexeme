import distutils.dir_util
import os
import sys

import jsonpickle


def convert_chain_to_folder_names(list_of_chains):
    output = list()
    for chain in list_of_chains:
        from_ = chain[0]
        for to_ in chain[1:]:
            output.append(from_ + '_' + to_)
    return output


if __name__ == '__main__':
    mixed_loc = sys.argv[1]
    target_loc = sys.argv[2]
    projects_to_split = sys.argv[3:]
    projects_to_split_ = {}
    for project in projects_to_split:
        with open('./out/%s/%s_history.json' % (project, project)) as f:
            projects_to_split_[project] = jsonpickle.decode(f.read())
    projects_to_split = {p: convert_chain_to_folder_names(l) for p, l in projects_to_split_.items()}
    mixed_directories = os.listdir(mixed_loc)
    for mixed_dir in mixed_directories:
        for project, points in projects_to_split.items():
            if mixed_dir in points:
                src = mixed_loc + '/' + mixed_dir
                dst = target_loc + '/%s' % project + '/%s' % os.path.basename(mixed_dir)
                distutils.dir_util.copy_tree(src, dst, update=True)
