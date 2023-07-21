import json
import logging
import os
import sys
from threading import Thread
from dotenv import load_dotenv

import jsonpickle
import networkx as nx

from flexeme.deltaPDG.Util.mark_pdgs import LANG_JAVA
from flexeme.deltaPDG.Util.merge_deltaPDGs import merge_files_pdg
from flexeme.deltaPDG.Util.generate_pdg import PDG_Generator
from flexeme.deltaPDG.Util.git_util import Git_Util
from flexeme.deltaPDG.deltaPDG import deltaPDG
from flexeme.tangle_concerns.tangle_by_file import tangle_by_file
from flexeme.synthetic.project_layout import ProjectLayout
from flexeme.tangle_concerns.scan_and_clean_corpora import clean_graph
from flexeme.wl_kernel.wl_kernel_untangle import validate

logging.basicConfig(level=logging.DEBUG,
                    format='[%(asctime)s][%(name)s] %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[logging.StreamHandler()])

logging.getLogger("git.cmd").setLevel(logging.INFO)

load_dotenv()  # Load .env file


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


def generate_pdg(revision, repository_path, id_, temp_loc, extractor_location, sourcepath, classpath):
    logging.info(f"Flexeme generate PDG for {revision} in {repository_path}")
    repository_name = os.path.basename(repository_path)
    method_fuzziness = 100
    node_fuzziness = 100

    os.makedirs(temp_loc, exist_ok=True)
    git_handler = Git_Util(temp_dir=temp_loc)

    with git_handler as gh:
        v1 = gh.move_git_repo_to_tmp(repository_path)
        v2 = gh.move_git_repo_to_tmp(repository_path)
        temp_dir_worker = temp_loc + '/%d' % id_
        os.makedirs(temp_dir_worker, exist_ok=True)
        v1_pdg_generator = PDG_Generator(extractor_location=extractor_location,
                                         repository_location=v1,
                                         target_filename='before_pdg.dot',
                                         target_location=temp_dir_worker,
                                         sourcepath=sourcepath,
                                         classpath=classpath,
                                         )
        v2_pdg_generator = PDG_Generator(extractor_location=extractor_location,
                                         repository_location=v2,
                                         target_filename='after_pdg.dot',
                                         target_location=temp_dir_worker,
                                         sourcepath=sourcepath,
                                         classpath=classpath,
                                         )

        from git import Repo
        repo = Repo(v1)
        commit = repo.commit(revision)
        if len(commit.parents) == 0:
            logging.warning(f'Ignoring {revision} because the commit has no parents')
            return

        from_ = revision + '^'
        to_ = revision

        gh.set_git_to_rev(from_, v1)
        gh.set_git_to_rev(to_, v2)
        labeli_changes = dict()
        labeli_changes[0] = gh.process_diff_between_commits(from_, to_, v2)
        changes = gh.process_diff_between_commits(from_, to_, v2)
        files_touched = {filename for _, filename, _, _, _ in changes if
                         os.path.basename(filename).split('.')[-1] == 'java'}  # and not filename.endswith("Tests.java")

        for filename in sorted(files_touched):
            local_filename = os.path.normpath(filename.lstrip('/'))  # filename is local to the repository. It
            # shouldn't start with a '/'
            # we keep filename as is otherwise it breaks the comparison in the diff in mark_originating_commit()
            logging.info(f"Generating PDGs for {filename}")
            try:
                output_path = './out/corpora_raw/%s/%s/%s/%s.dot' % (
                    repository_name, to_, 0, os.path.basename(filename))
                logging.info(f"Generating PDG for {filename}@{from_}")
                v1_pdg_generator(local_filename)
                logging.info(f"Generating PDG for {filename}@{to_}")
                v2_pdg_generator(local_filename)

                logging.info(f"Building ∂PDG for {filename}")
                delta_gen = deltaPDG(temp_dir_worker + '/before_pdg.dot', m_fuzziness=method_fuzziness,
                                     n_fuzziness=node_fuzziness)
                delta_pdg = delta_gen(temp_dir_worker + '/after_pdg.dot',
                                      [ch for ch in changes if ch[1] == filename], LANG_JAVA)
                delta_pdg = mark_originating_commit(delta_pdg, mark_origin(changes, labeli_changes), filename)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                nx.set_node_attributes(delta_pdg, local_filename, "filepath")
                nx.drawing.nx_pydot.write_dot(delta_pdg, output_path)
            except Exception as e:
                raise e


def worker(work, subject_location, id_, temp_loc, extractor_location, layout: ProjectLayout):
    logger = logging.getLogger("worker" + str(id_))
    logger.info("Starting worker" + str(id_))
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
                                         target_location=temp_dir_worker,
                                         sourcepath=subject_location,
                                         classpath=subject_location
                                         )
        v2_pdg_generator = PDG_Generator(extractor_location=extractor_location,
                                         repository_location=v2,
                                         target_filename='after_pdg.dot',
                                         target_location=temp_dir_worker,
                                         sourcepath=subject_location,
                                         classpath=subject_location
                                         )
        for chain in work:
            logger.info('Working on chain: %s' % str(chain))
            from_ = chain[0]
            from git import Repo
            repo = Repo(v1)
            commit = repo.commit(from_)

            if len(commit.parents) == 0:
                logger.warning(f'Ignoring {from_} because the commit has no parents')
                continue

            gh.set_git_to_rev(from_ + '^', v1)
            gh.set_git_to_rev(from_, v2)
            labeli_changes = dict()
            labeli_changes[0] = gh.process_diff_between_commits(from_ + '^', from_, v2)
            previous_sha = from_
            i = 1

            try:
                for to_ in chain[1:]:
                    gh.cherry_pick_on_top(to_, v2)

                    changes = gh.process_diff_between_commits(from_ + '^', to_, v2)
                    labeli_changes[i] = gh.process_diff_between_commits(previous_sha, to_, v2)

                    i += 1
                    previous_sha = to_

                    # There will always be a monotonic number of files because the diff is always compared against the
                    # first commit of the chain (from_^).
                    files_touched = {filename for _, filename, _, _, _ in changes if
                                     os.path.basename(filename).split('.')[-1] == 'java'}  # and not filename.endswith(
                    # "Test.java")}

                    logger.info(f"{len(files_touched)} files affected between {from_ + '^'} and {to_}")
                    out_dir = './out/corpora_raw/%s/%s_%s/%d' % (repository_name, from_, to_, i)

                    try:
                        for filename in files_touched:
                            logger.info(f"Generating PDGs for {filename}")
                            try:
                                output_path = './out/corpora_raw/%s/%s_%s/%d/%s.dot' % (
                                    repository_name, from_, to_, i, os.path.basename(filename))

                                sourcepath = layout.get_sourcepath(from_ + '^')
                                classpath = layout.get_classpath(v1)

                                v1_pdg_generator.set_sourcepath(sourcepath)
                                v1_pdg_generator.set_classpath(classpath)
                                v1_pdg_generator(filename)

                                sourcepath = layout.get_sourcepath(to_)
                                classpath = layout.get_classpath(v2)
                                v2_pdg_generator.set_sourcepath(sourcepath)
                                v2_pdg_generator.set_classpath(classpath)
                                v2_pdg_generator(filename)

                                delta_gen = deltaPDG(temp_dir_worker + '/before_pdg.dot', m_fuzziness=method_fuzziness,
                                                     n_fuzziness=node_fuzziness)
                                delta_pdg = delta_gen(temp_dir_worker + '/after_pdg.dot',
                                                      [ch for ch in changes if ch[1] == filename], LANG_JAVA)
                                delta_pdg = mark_originating_commit(delta_pdg, mark_origin(changes, labeli_changes),
                                                                    filename)
                                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                nx.drawing.nx_pydot.write_dot(delta_pdg, output_path)
                            except Exception as e:
                                raise e
                        if len(files_touched) != 0:
                            merged_path = merge_files_pdg(out_dir)
                            clean_path = clean_graph(merged_path, repository_name)
                            validate([clean_path], 1, 1, repository_name)  # Flexeme's paper uses 1-hop clustering
                    except Exception as e:
                        logging.error("Error while processing synthetic commit %s_%s:" % (from_, to_))
                        logging.error(e)
            except Exception as e:
                logging.error("Error in chain %s:" % str(chain))
                logging.error(e)


if __name__ == '__main__':
    """
    Run the synthetic benchmark.
    """

    if len(sys.argv) != 4:
        print('To use this script please run as `[python] generate_corpus.py '
              '<synthetic commits file> <repository path> <work directory>')
        sys.exit(1)
    json_location = sys.argv[1]
    subject_location = os.path.abspath(sys.argv[2])
    temp_loc = os.path.abspath(sys.argv[3])
    id_ = 1  # int(sys.argv[4])
    n_workers = 1  # int(sys.argv[5])
    extractor_location = 'extractors/codechanges-checker-0.1.2-all.jar'

    if not os.path.exists(subject_location):
        print(f"Subject location {subject_location} does not exists")

    os.makedirs(temp_loc, exist_ok=True)

    load_dotenv()  # Load .env file

    # Create commit chains if the file doesn't exists.
    try:
        with open(json_location) as f:
            list_to_tangle = jsonpickle.decode(f.read())
    except FileNotFoundError:
        list_to_tangle = tangle_by_file(subject_location, temp_loc)
        with open(json_location, 'w') as f:
            f.write(json.dumps(list_to_tangle))

    logging.info(f"Found {len(list_to_tangle)} commit chains")
    chunck_size = int(len(list_to_tangle) / n_workers)
    list_to_tangle = [list_to_tangle[i:i + chunck_size] for i in range(0, len(list_to_tangle), chunck_size)]

    repository_name_to_d4j_name = {
        'commons-math': 'Math',
        'commons-lang': 'Lang',
        'joda-time': 'Time',
        'closure-compiler': 'Closure'
    }

    project_name = repository_name_to_d4j_name[os.path.basename(subject_location)]

    logging.info("Looking into " + project_name + " project.")

    layout = ProjectLayout(project_name, subject_location)
    threads = []
    for work in list_to_tangle:
        t = Thread(target=worker, args=(work, subject_location, id_, temp_loc, extractor_location, layout))
        id_ += 1
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
