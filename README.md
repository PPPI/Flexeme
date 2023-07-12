# FLEXEME

Java implementation of Flexeme based on the original implementation of Flexeme.

Please see [ORIGINAL_INSTRUCTIONS.md](./ORIGINAL_INSTRUCTIONS.md) document for the documentation of the original 
Flexeme repository.

## Requirements
- **Requires Python 3.8.**
- Requires Java 8 on the path
- Requires Java 11 in `FLEXEME_JAVA` environment variable

## Installation
1. Install Graphviz https://graphviz.org/.
2. Create a virtual environment `python3 -m venv .venv`.
3. Activate the virtual environment `source .venv/bin/activate`.
4. Install Flexeme `pip install -e .`
   - If the dependency `pygraphviz` fails to install. Visit https://pygraphviz.github.io/documentation/stable/install.html and follow the instructions for your OS.
5. Run `cp .env-template .env` and fill in the environment variables in `.env`:
    - `JAVA11_HOME`: Location of the **Java 11** executable to run the PDG extractor. Requires Java 11. (e.g., `"$HOME/.sdkman/candidates/java/11.0.18-amzn/bin/java`")

## Synthetic Benchmark
Run Flexeme on the synthetic benchmark.

**input**: path to repository

**output**: untangling accuracy for repository

Steps:
1. Create lists of commit ids (e.g., [a, b, c, d]). A list of commit ids represents multiple synthetic commits of 
   varrying size (named 'concerns'). e.g.,
    - a to b represent a synthetic commit with 1 concern
    - a to c represent a synthetic commit with 2 concerns
    - a to d represent a synthetic commit with 3 concerns
2. Generate ∂PDGs for each synthetic commits:
    - Each file changed in the synthetic commit gets a ∂PDG
3. Merge file-based ∂PDG into a single ∂PDG to represent the synthetic commit.
4. Normalization of labels in ∂PDGs.
5. Evaluation (runs the untangling on the ∂PDGs).
6. Report untangling accuracy.

### Running the benchmark

1. Checkout Defects4J repository `git clone $D4J_HOME/project_repos/commons-lang.git 
   /private/tmp/commons-lang`.
2. Creating synthetic commits `python3 flexeme/tangle_concerns/tangle_by_file.py /private/tmp/commons-lang 
   /private/tmp/ .`.
3. Generate ∂PDGs and evaluate: `python3 
   flexeme/tangle_concerns/generate_corpus.py 
   out/storm/storm_history_filtered_flat.json /private/tmp/commons-lang .tmp/storm`.
4. Results are saved in `out/commons-lang/`. 

### Layout changes
The file `defects4j/layout_changes.json` contains the changes in repository layouts for sourcepath for Defects4J 
projects. The file is necessary for running the synthetic benchmark. The changes are ordered from newest to oldest.

When untangling a commit, the scripts find the correct layout by checking if the newest layout change commit is an 
ancestor.
If it is not, it will check the next older layout change commit until it finds an ancestor. If no ancestor is found, 
a warning is logged and the layout returned is `None`.

The layout changes are added manually from the `dir_layout.csv` project-specific file stored in the Defects4J 
repository. The entries in `dir_layout.csv` are ordered either from new to old or from old to new. Before adding a 
new project in `defects4j/layout_changes.json`, verify which order is used in `dir_layout.csv`.


## Untangle Commits
Run Flexeme to untangle a commit in a local repository.
1. Clone this repository locally.
2. Install Flexeme `pip install -e path/to/flexeme/clone`
3. Run `flexeme <repository> <commit> <sourcepath> <classpath> <output_file>`.
    - `repository`: Path to the repository.
    - `commit`: Commit to untangle.
    - `sourcepath`: Java sourcepath to compile the files of `commit`.
    - `classpath`: Java classpath to compile the files of `commit`.
    - `output_file`: Where the results are stored.
