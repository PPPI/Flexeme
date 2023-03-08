import json
import os
import shutil
import subprocess
import pathlib

from sys import platform
import logging

import networkx as nx

import flexeme
from flexeme.deltaPDG.Util.merge_nameflow import add_nameflow_edges
from flexeme.deltaPDG.Util.pygraph_util import read_graph_from_dot, obj_dict_to_networkx

class PDG_Generator(object):
    """
    This class serves as a wrapper to abstract away calling the C# compiled PDG extractor
    """

    def __init__(self,
                 extractor_location,
                 repository_location,
                 sourcepath,
                 classpath,
                 target_filename="pdg.dot",
                 target_location=os.getcwd()):
        flexeme_root = pathlib.Path(os.path.dirname(flexeme.__file__)).parent
        self.location = flexeme_root / extractor_location
        self.repository_location = repository_location
        self.target_filename = target_filename
        self.target_location = target_location
        self.java_exec = os.getenv('FLEXEME_JAVA', "java")
        self.sourcepath = sourcepath
        self.classpath = classpath
        self.EXTRACTOR_OUTPUT_FILE = "pdg.dot" # Name of the file outputted by the generator.

    def __call__(self, filename):
        generate_a_pdg = None

        filename = filename.lstrip('/')

        if os.path.exists(os.path.join(self.repository_location, filename)):
            if platform == "linux" or platform == "linux2":  # linux
                generate_a_pdg = subprocess.Popen([self.location, '.', '.' + filename.replace('/', '\\')],
                                                  bufsize=1, cwd=self.repository_location)
                generate_a_pdg.wait()
            elif platform == "win32": # Windows

                generate_a_pdg = subprocess.Popen([self.location, '.', '.' + filename.replace('/', '\\')], bufsize=1,
                                                  cwd=self.repository_location)
                generate_a_pdg.wait()

            elif platform == "darwin": # MacOS
                generator_path = self.location.resolve()
                generate_a_pdg = subprocess.Popen([self.java_exec, '-cp', generator_path,
                                                   'org.checkerframework.flexeme.PdgExtractor',
                                                    filename, self.sourcepath, self.classpath],
                                                  cwd=self.repository_location)
                try:
                    generate_a_pdg.wait(timeout=300)
                except subprocess.TimeoutExpired as e:
                    logging.warning(f"PDG Generation timed out for {filename}")
                    raise e
            else:
                logging.error("Platform not supported")

            if not generate_a_pdg or generate_a_pdg.returncode:
                logging.error(f"PDG Generation failed for {filename}")
                exit(1)
        else:
            with open(os.path.join(self.repository_location, self.EXTRACTOR_OUTPUT_FILE), 'w') as f:
                f.write('digraph "extractedGraph"{\n}\n')

        try:
            shutil.move(os.path.join(self.repository_location, self.EXTRACTOR_OUTPUT_FILE),
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

    def set_sourcepath(self, sourcepath):
        self.sourcepath = sourcepath

    def set_classpath(self, classpath):
        self.classpath = classpath
