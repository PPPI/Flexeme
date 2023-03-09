import json
import logging
import subprocess


class ProjectLayout:

    def __init__(self, d4j_project_name, repository_path: str, classpath):
        """
        :param layout_changes:
        """
        self.d4j_project_name = d4j_project_name
        self.classpath = classpath
        self.layout_changes = self.load_layout_changes()
        self.repository_path = repository_path

    def load_layout_changes(self):
        """
        Load the layout changes from the json file.
        Changes are ordered from newest to oldest.
        """
        with open("defects4j/layout_changes.json") as f:
            data = json.load(f)
        return data

    def get_sourcepath(self, commit):
        for change in self.layout_changes[self.d4j_project_name]:
            if self.is_ancestor(change['commit'], commit):
                return change['sourcepath']
        logging.warning("No sourcepath found for commit %s" % commit)
        return None

    def is_ancestor(self, possible_ancestor, commit):
        """
        Check if `id` is an ancestor of `commit`.
        """
        process = subprocess.run(['git', 'merge-base', '--is-ancestor', possible_ancestor, commit],
                                 cwd=self.repository_path)
        if process.returncode == 0:
            return True
        elif process.returncode == 1:
            return False
        else:
            raise Exception("git merge-base --is-ancestor failed")

    def get_classpath(self, commit):
        return self.classpath