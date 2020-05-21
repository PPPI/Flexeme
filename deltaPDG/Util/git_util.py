import datetime
import email.utils as eut
import re
import shutil
import subprocess
import tempfile
from typing import Tuple, List, Any, Optional

commit_line = re.compile(r'commit [0-9a-f]{40}\n')
captured_commit_line = re.compile(r'(commit [0-9a-f]{40}\n)')


class Git_Util(object):
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir

    def _clean_up(self):
        for path in self.temp_paths:
            shutil.rmtree(path, ignore_errors=True)

    def __enter__(self):
        self.temp_paths = []
        return self

    def __exit__(self, *exc_details):
        self._clean_up()

    def move_git_repo_to_tmp(self, url: str) -> str:
        path = tempfile.mkdtemp(suffix=".gitYarn", dir=self.temp_dir)
        shutil.rmtree(path)
        shutil.copytree(url, path, symlinks=True, )

        self.temp_paths.append(path)
        return path

    @staticmethod
    def set_git_to_rev(sha: str, path: str):
        git_reset_process = subprocess.Popen(['git', 'checkout', '-f', sha], bufsize=1, cwd=path)
        git_reset_process.wait()

    @staticmethod
    def get_commits_for_file(filename: str, path: str) -> List[str]:
        git_log_process = subprocess.Popen(['git', 'log', '--format=oneline', '--follow', '--', filename],
                                           bufsize=1, cwd=path, stdout=subprocess.PIPE)
        result = list(map(lambda line: line.decode('utf-8', 'replace').strip().split(' ')[0],
                          git_log_process.stdout.readlines()))
        git_log_process.stdout.close()
        return result

    # git log HEAD~[newer_commit] -n 1 --format=%ad; \
    # git log HEAD~[older_commit] -n 1 --format=%ad
    @staticmethod
    def get_time_between_commits(old: str, new: str, path: str) -> datetime.timedelta:
        gen_str_process = subprocess.Popen(('git log ' + new + ' -n 1 --format=%ad').split(' '),
                                           bufsize=1, cwd=path, stdout=subprocess.PIPE)
        dates = list()
        dates += list(map(lambda line: eut.parsedate_to_datetime(line.decode('utf-8', 'replace').strip()),
                          gen_str_process.stdout.readlines()))
        gen_str_process.stdout.close()
        gen_str_process = subprocess.Popen(('git log ' + old + ' -n 1 --format=%ad').split(' '),
                                           bufsize=1, cwd=path, stdout=subprocess.PIPE)
        dates += list(map(lambda line: eut.parsedate_to_datetime(line.decode('utf-8', 'replace').strip()),
                          gen_str_process.stdout.readlines()))
        gen_str_process.stdout.close()
        if len(dates) == 2:
            return dates[0] - dates[1]
        else:
            return datetime.timedelta(days=999999999)

    @staticmethod
    def cherry_pick_on_top(sha: str, path: str):
        git_cherry_process = subprocess.Popen(['git', 'cherry-pick', '--strategy=recursive', '-X', 'theirs', '-n', sha],
                                              bufsize=1, cwd=path)
        git_cherry_process.wait()

    @staticmethod
    def get_current_head(path: str) -> str:
        get_head_process = subprocess.Popen(['git', 'rev-parse', 'HEAD'],
                                            bufsize=1, stdout=subprocess.PIPE, cwd=path).stdout
        show_lines = list(map(lambda line: line.decode('utf-8', 'replace'), get_head_process.readlines()))
        get_head_process.close()

        return show_lines[0]

    @staticmethod
    def process_diff_between_commits(sha_old: str, sha_new: str, path: str) -> List[Tuple[str, str, int, int, str]]:
        diff_show_process = subprocess.Popen(['git', 'diff', '%s..%s' % (sha_old, sha_new)],
                                             bufsize=1, stdout=subprocess.PIPE, cwd=path).stdout
        show_lines = list(map(lambda line: line.decode('utf-8', 'replace'), diff_show_process.readlines()))
        diff_show_process.close()

        current_index = 0
        diffs = []
        if current_index < len(show_lines):
            current_diff = ''
            while True:
                curr_line = show_lines[current_index]
                if current_index + 1 == len(show_lines):  # We reached the EOF
                    current_diff += curr_line
                    diffs.append(current_diff.strip())
                    break
                elif (curr_line.startswith('diff --git')) or (
                        curr_line.startswith('diff --cc')):  # New diff for this commit
                    if current_diff != '':
                        diffs.append(current_diff.strip())
                    current_diff = curr_line
                else:
                    current_diff += curr_line
                current_index += 1

        return [v for sublist in list(map(Git_Util.process_diff_output, diffs)) for v in sublist]

    @staticmethod
    def get_commit_msg(sha: str, path: str) -> str:
        commit_msg_process = subprocess.Popen(('git log --format=%B -n 1 ' + sha).split(' '),
                                              bufsize=1, stdout=subprocess.PIPE, cwd=path).stdout
        show_lines = list(map(lambda line: line.decode('utf-8', 'replace'), commit_msg_process.readlines()))
        commit_msg_process.close()

        return '\n'.join(show_lines)

    @staticmethod
    def get_all_commit_hashes(path: str) -> List[str]:
        commit_hashes_process = subprocess.Popen(['git', 'log', '--branches=*', '--format=oneline'], bufsize=1,
                                                 stdout=subprocess.PIPE, cwd=path).stdout
        commit_hashes = commit_hashes_process.readlines()
        commit_hashes_process.close()
        return list(map(lambda line: line.decode('utf-8', 'replace').split(' ')[0].strip(), commit_hashes))

    @staticmethod
    def parse_git_log_entry(entry: str) -> Optional[Tuple[str, str, datetime.datetime, str, Any]]:
        """
        The expected format is:
        commit <sha>[ (Pointer indication for a particular repository)]
        Author: <Name> <email>
        Date: <timestamp>
        <Multi-line commit messge>
        <Individual file diffs>^n
        """
        entry = entry.split('\n')
        if any('Merge: ' in e for e in entry):
            return None

        sha = entry[0].split()[1].strip()
        try:
            author = entry[1].lstrip()[len('Author: '):entry[1].index('<')].strip()
        except ValueError:
            return None  # No author => we cannot verify our construction requirement
        try:
            date = eut.parsedate_to_datetime(entry[2].lstrip()[len('Date: '):])
        except TypeError:
            return None  # No date => we cannot verify our construction requirement

        msg_and_diff = re.split(r'(diff --.*\n)', '\n'.join(entry[3:]))
        msg = msg_and_diff[0]

        diffs = msg_and_diff[1:]
        diffs = [i1 + i2 for i1, i2 in zip(diffs[0::2], diffs[1::2])]
        diffs = [v for sublist in list(map(Git_Util.process_diff_output, diffs)) for v in sublist]

        return sha, author, date, msg, diffs

    @staticmethod
    def get_all_commit_hashes_authors_dates_messages(path: str) -> List[Tuple[str, str, datetime.datetime, str, Any]]:
        commit_hashes_process = subprocess.Popen(['git', 'log', '--branches=*', '--unified=0'], bufsize=1,
                                                 stdout=subprocess.PIPE, cwd=path).stdout
        commit_hashes = commit_hashes_process.read().decode('utf-8', 'replace')
        commit_hashes_process.close()
        list_of_commit_metadata = re.split(captured_commit_line, commit_hashes)[1:]
        list_of_commit_metadata = [i1 + i2 for i1, i2 in
                                   zip(list_of_commit_metadata[0::2], list_of_commit_metadata[1::2])]
        return [e for e in [Git_Util.parse_git_log_entry(e) for e in list_of_commit_metadata] if e is not None]

    @staticmethod
    def get_author(sha: str, path: str) -> str:
        commit_show_process = subprocess.Popen(['git', 'show', '--format=fuller', '--unified=0', sha],
                                               bufsize=1, stdout=subprocess.PIPE, cwd=path).stdout
        show_lines = list(map(lambda line: line.decode('utf-8', 'replace'), commit_show_process.readlines()))
        commit_show_process.close()

        # Sanity check that we are looking at the expected commit
        assert (len(show_lines) > 0)
        assert (show_lines[0].split(' ')[-1].strip().startswith(sha))

        # Navigate to the start of the commit diff
        current_index = 0
        while not (show_lines[current_index].startswith('Author')):
            current_index += 1
        author = show_lines[current_index].split(':')[-1][1:].strip().split('<')[0][:-1]
        return author

    @staticmethod
    def process_a_commit(sha: str, path: str) -> Tuple[str, List[Tuple[str, str, int, int, str]]]:
        commit_show_process = subprocess.Popen(['git', 'show', '--format=fuller', '--unified=0', sha],
                                               bufsize=1, stdout=subprocess.PIPE, cwd=path).stdout
        show_lines = list(map(lambda line: line.decode('utf-8', 'replace'), commit_show_process.readlines()))
        commit_show_process.close()

        # Sanity check that we are looking at the expected commit
        assert (len(show_lines) > 0)
        assert (show_lines[0].split(' ')[-1].strip().startswith(sha))

        # Navigate to the start of the commit diff
        current_index = 0
        while not (show_lines[current_index].startswith('Author')):
            current_index += 1
        author = show_lines[current_index].split(':')[-1][1:].strip().split('<')[0][:-1]
        current_index += 4
        while not (show_lines[current_index] == '\n'):
            current_index += 1
        current_index += 1
        if current_index < len(show_lines):
            while True:
                curr_line = show_lines[current_index]
                current_index += 1
                if curr_line == '\n':
                    break
                if current_index == len(show_lines):  # We reached EOF in title, i.e. the commit has no diff-s
                    break
        # End of navigation to start of diff

        diffs = []
        if current_index < len(show_lines):
            current_diff = ''
            while True:
                curr_line = show_lines[current_index]
                if current_index + 1 == len(show_lines):  # We reached the EOF
                    current_diff += curr_line
                    diffs.append(current_diff.strip())
                    break
                elif (curr_line.startswith('diff --git')) or (
                        curr_line.startswith('diff --cc')):  # New diff for this commit
                    if current_diff != '':
                        diffs.append(current_diff.strip())
                    current_diff = curr_line
                else:
                    current_diff += curr_line
                current_index += 1

        diffs = [v for sublist in list(map(Git_Util.process_diff_output, diffs)) for v in sublist]
        return author, diffs

    @staticmethod
    def process_git_blame(file, path):
        commit_show_process = subprocess.Popen(['git', 'blame', file],
                                               bufsize=1, stdout=subprocess.PIPE, cwd=path).stdout
        show_lines = list(map(lambda line: line.decode('utf-8', 'replace'), commit_show_process.readlines()))
        commit_show_process.close()
        lines = [(line[:line.index('(') - 1][:8], line[line.index(')') + 2:]) for line in show_lines]
        return lines

    @staticmethod
    def merge_diff_into_diff_regions(diff: List[Tuple[str, str, int, int, str]]) \
            -> List[Tuple[str, str, Tuple[int, int], Tuple[int, int], str]]:
        additions = [ch for ch in diff if ch[0] == '+']
        deletions = [ch for ch in diff if ch[0] == '-']
        result = list()
        if len(additions) > 0:
            type, file, line_no, _, line = additions[0]
            previous = (type, file, (line_no, line_no), (-1, -1), line)
            for type, file, line_no, _, line in additions[1:]:
                if line_no - previous[2][-1] == 1:
                    previous = (previous[0], previous[1], (previous[2][0], line_no), previous[3],
                                previous[-1] + '\n' + line)
                else:
                    result.append(previous)
                    previous = (type, file, (line_no, line_no), (-1, -1), line)

        if len(deletions) > 0:
            type, file, _, line_no, line = deletions[0]
            previous = (type, file, (-1, -1), (line_no, line_no), line)
            for type, file, _, line_no, line in deletions[1:]:
                if line_no - previous[3][-1] == 1:
                    previous = (previous[0], previous[1], previous[2], (previous[2][0], line_no),
                                previous[-1] + '\n' + line)
                else:
                    result.append(previous)
                    previous = (type, file, (-1, -1), (line_no, line_no), line)

        return result

    @staticmethod
    def process_diff_output(diff: str) -> List[Tuple[str, str, int, int, str]]:
        header = 0
        lines = diff.split('\n')
        while not (lines[header].startswith('@@')):
            header += 1
            if header == len(lines):
                return list()
        header -= 2
        lines = lines[header:]
        filepath = re.sub(r'^("?)[ab]/', r'\1/', lines[1 if 'new file mode' in diff else 0][4:])
        diff = lines[2:]
        segmented_diffs = list()
        add_ctr = 0
        del_ctr = 0
        for line in diff:
            line = line.strip()
            if line.startswith('@@'):
                del_ctr = int(line.split(' ')[1].split(',')[0][1:])
                add_ctr = int(line.split(' ')[2].split(',')[0][1:])
            elif line.startswith('-'):
                segmented_diffs.append(('-', filepath, -1, del_ctr, line[1:]))
                del_ctr += 1
            elif line.startswith('+'):
                segmented_diffs.append(('+', filepath, add_ctr, -1, line[1:]))
                add_ctr += 1
            elif line.startswith('\\ No newline at end of file'):
                pass
            else:
                segmented_diffs.append((' ', filepath, add_ctr, del_ctr, line))
                del_ctr += 1
                add_ctr += 1

        return [p for p in segmented_diffs if p[0] != ' ']
