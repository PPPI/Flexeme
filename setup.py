from setuptools import setup

setup(
    name='flexeme',
    version='0.0.1',
    packages=['Util', 'deltaPDG', 'deltaPDG.Util', 'tangle_concerns', 'wl_kernel', 'confidence_voters',
              'confidence_voters/Util'],
    url='',
    license='MIT',
    author='',
    author_email='',
    description='', install_requires=['jsonpickle', 'scipy', 'tqdm', 'networkx', 'numpy', 'rapidfuzz', 'pygraphviz',
                                      'pydot', 'grakel', 'nltk']
)
