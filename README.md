# FLEXEME

Java implementation of Flexeme based on the original implementation of Flexeme.

Please see [ORIGINAL_INSTRUCTIONS](./ORIGINAL_INSTRUCTIONS.md) document for the documentation of the original 
Flexeme repository.

## Requirements
**Requires python 3.8.**

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

1. Cloning subjects: `./subjects/clone_subjects.sh`.
2. Creating synthetic commits `./synthetize_commits.sh`. Outputs results in 
   `out/<repository>/<repository>_history_filtered_flat.json`.
3. Generate ∂PDGs for each file and each synthetic commit: `python3 flexeme/tangle_concerns/generate_corpus.py 
   out/storm/storm_history_filtered_flat.json subjects/storm/ .tmp/storm 1 12 extractors/codechanges-checker-0.1-all.
   jar`
   - 
4. (Merge files into `merged.dot`)
5. Clean merged.dot files `python3 tangle_concerns/scan_and_clean_corpora.py storm`
   - in: out/corpora_raw/**merged.dot
   - out: data/corpora_clean/**
6. Evaluate `python ./Util/graph_evaluation_driver.py 1 wl 1 repo1 repo2 repo3 ... repoN`
    - `1`: Number of times to run the clustering (for measuring performance)
    - `wl`: Graph clustering method to use.
    - `1`: Number of hops.
    - `repo1 repo2 repo3 ... repoN`: List of subjects to evaluate.


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