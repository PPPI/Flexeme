from setuptools import setup, find_packages

setup(
    name='flexeme',
    version='0.1.0',
    packages=find_packages(include=['flexeme', 'flexeme.*']),
    license='MIT',
    description='',
    python_requires='==3.8.15',
    install_requires=['jsonpickle', 'scipy', 'tqdm', 'networkx==2.3', 'numpy==1.23.5', 'rapidfuzz', 'pygraphviz',
                      'pydot', 'grakel', 'nltk', 'python-dotenv','GitPython'],
    entry_points={
        'console_scripts': ['flexeme=flexeme.app:main']
    }
)
