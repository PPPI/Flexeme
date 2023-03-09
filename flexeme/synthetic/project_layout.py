import json
import logging
import subprocess
import tempfile

class ProjectLayout:
    """
    This class is used to retrieve the classpath and sourcepath for a given Defects4j project.
    The sourcepath changes between versions of the project. For example if the project changes its layout.
    The classpath doesn't change between versions but can have local or global dependencies.

    TODO: Retrieving the classpath could be speed up by storing the classpath for each project in a file. Local paths
    are represented with a placeholder name.
    """

    def __init__(self, d4j_project_name, repository_location):
        """
        :param: d4j_project_name: Name of the Defects4j project
        """
        self.d4j_project_name = d4j_project_name
        self.repository_location = repository_location
        self.classpath, self.placeholder = self.retrieve_classpath()
        self.layout_changes = self.load_layout_changes()

    def retrieve_classpath(self):
        classpath = ""
        # Checkout Defects4j project
        bug_id = '1f'

        work_dir = tempfile.mkdtemp()
        # work_dir = '/tmp/placeholder'
        checkout = subprocess.run(['defects4j', 'checkout', '-p', self.d4j_project_name, '-v', bug_id, '-w', work_dir], check=True,
                                      capture_output=True)

        if checkout.returncode != 0:
            logging.error('Checkout failed')
            return None

        cp_compile = subprocess.run(['defects4j', 'export', '-p', 'cp.compile', '-w', work_dir], check=True,
                                      capture_output=True)

        classpath += str(cp_compile.stdout.decode())

        cp_test = subprocess.run(['defects4j', 'export', '-p', 'cp.test', '-w', work_dir], check=True,
                                      capture_output=True)

        classpath += ":" + str(cp_test.stdout.decode())
        return classpath, work_dir

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
                                 cwd=self.repository_location)
        if process.returncode == 0:
            return True
        elif process.returncode == 1:
            return False
        else:
            raise Exception("git merge-base --is-ancestor failed")

    def get_classpath(self, repository_path):
        return self.classpath.replace(self.placeholder, repository_path)
