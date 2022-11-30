import json
import os
import shutil
import subprocess

from sys import platform
import logging

import networkx as nx

from deltaPDG.Util.merge_nameflow import add_nameflow_edges
from deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx


class PDG_Generator(object):
    """
    This class serves as a wrapper to abstract away calling the C# compiled PDG extractor
    """

    def __init__(self, extractor_location, repository_location, target_filename="pdg.dot", target_location=os.getcwd()):
        self.location = extractor_location
        self.repository_location = repository_location
        self.target_filename = target_filename
        self.target_location = target_location

    def __call__(self, filename):
        logging.info(f"Generating PDG for {filename} in temporary repository {self.repository_location}")

        generate_a_pdg = None
        if platform == "linux" or platform == "linux2":  # linux
            generate_a_pdg = subprocess.Popen([self.location, '.', '.' + filename.replace('/', '\\')],
                                              bufsize=1, cwd=self.repository_location)
            generate_a_pdg.wait()
        elif platform == "win32": # Windows

            generate_a_pdg = subprocess.Popen([self.location, '.', '.' + filename.replace('/', '\\')], bufsize=1,
                                              cwd=self.repository_location)
            generate_a_pdg.wait()

        elif platform == "darwin": # MacOS
            generate_a_pdg = subprocess.Popen(['java', '-jar', self.location, '.' + filename],
                                              cwd=self.repository_location)
            generate_a_pdg.wait()
            # print(f"Return code {generate_a_pdg.returncode}")
            # print(generate_a_pdg.stdout)
            # print(generate_a_pdg.stderr)
        else:
            print("Platform not supported")

        if not generate_a_pdg or generate_a_pdg.returncode:
            logging.error(f"PDG Generation failed for {filename}")
            exit(1)

        try:
            shutil.move(os.path.join(self.repository_location, 'pdg.dot'),
                        os.path.join(self.target_location, self.target_filename))
        except FileNotFoundError:
            logging.error("Diagram not found for " + filename)

        try:
            # shutil.move(os.path.join(self.repository_location, 'nameflows.json'),
            # os.path.join(self.target_location, 'nameflows_' + self.target_filename.split('.')[0] + '.json'))
            with open(os.path.join(self.repository_location, 'nameflows.json'), encoding='utf-8-sig') as json_data:
                nameflow_data = json.loads(json_data.read())

            # Normalise the nameflow json
            if nameflow_data is not None:
                for node in nameflow_data['nodes']:
                    file, line = node['Location'].split(' : ')
                    node['Location'] = (file[len(self.repository_location):]
                                        if self.repository_location in file
                                        else file,
                                        line)
                    node['Infile'] = \
                        os.path.normcase(os.path.normpath(filename)) == os.path.normcase(os.path.normpath(file[1:]))

            nameflow_data['relations'] = [[] if v is None else v for v in nameflow_data['relations']]

            # And add nameflow edges
            apdg = obj_dict_to_networkx(read_graph_from_dot(os.path.join(self.target_location, self.target_filename)))
            apdg = add_nameflow_edges(nameflow_data, apdg)
            nx.drawing.nx_pydot.write_dot(apdg, os.path.join(self.target_location, self.target_filename))

        except FileNotFoundError:
            # No file, nothing to add
            pass
