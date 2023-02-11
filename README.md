# FLEXEME
[![DOI](https://zenodo.org/badge/265828516.svg)](https://zenodo.org/badge/latestdoi/265828516)

This project provides several implementations for commit untangling and proposes a new representation of
git patches by projecting the patch onto a PDG.

Please see [ORIGINAL_INSTRUCTIONS](./ORIGINAL_INSTRUCTIONS.md) document for the documentation of the original fork.

## How To
1. Cloning subjects: `./subjects clone_subjects.sh`
2. Creating synthetic commits `./synthetize_commits.sh`
3. Generate ∂PDGs for each file (e.g., jfreechart) `python3 tangle_concerns/generate_corpus.py 
   out/jfreechart/jfreechart_history_filtered_flat.json  subjects/jfreechart .antlr-tmp 1 1 extractors/codechanges-checker-0.1-all.jar
`
4. (Merge files into `merged.dot`)
5. Clean merged.dot `python3 tangle_concerns/scan_and_clean_corpora.py basic`
6. Evaluate `python ./Util/graph_evaluation_driver.py 1 wl 20 basic`

### Importing Flexeme to your projects
1. Clone this repository locally.
2. Install this repository `pip install -e path/to/flexeme/clone`.
3. Run Flexeme with `flexeme`.