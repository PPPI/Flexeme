# FLEXEME
[![DOI](https://zenodo.org/badge/265828516.svg)](https://zenodo.org/badge/latestdoi/265828516)

This project provides several implementations for commit untangling and proposes a new representation of
git patches by projecting the patch onto a PDG.

## Repository Structure
We provide an artificial corpus and a way of building such corpora in `./tangle_concerns`.

We provide a reference implementation to obtain a 𝛿-PDG and augmenting a 𝛿-PDG with name-flow information
to obtain a Delta Name-flow Graph (𝛿-NFG) in `./deltaPDG`, the later is `./deltaPDG/Util/merge_nameflow.py`.

We provide the binary of the PDG extractor for C# code under `./extractor`. NOTE: this requires MS Windows to run.

We provide a reimplementation of the method described by Herzig et al.[[1]](#1) adapted to the C#
setting in `./confidence_voters`. In the same folder we provide our adaptation that works 
on our proposed 𝛿-PDG as `./confidence_voters/confidence_voters_graph_only.py`.

We provide a reimplementation of the method described by Barnett et al.[[2]](#2) in `./du_chain/DU_chains_closure.py`.
We remark that we do not provide special treatment to trivial partitions as defined by Barnett et al. which may impact 
observed performance.

We provide our proposed method under `./wl_kernel/wl_kernel_untangle.py`.

Evaluation drivers are provided under `./Util/[cv/graph]_evaluation_driver.py`.

We provide our evaluation analysis scripts under `./analysis` as a jupyter notebook.

## Dependencies
**Requires python 3.8**.

We recommend using a virtual environment to install the dependencies.
Use `python3 -m venv .venv` then `source .venv/bin/activate` and finally `pip install -e .` to install the 
dependencies.

###For Windows
Apart from the python requirements, the extractor requires running in a MS Windows system with .NET 4.5 installed.
We have not validated this under Wine in Linux. We have validated it to work under WSL1.

To install pygraphviz on Windows, one should apply the patch from [here](https://github.com/Kagami/pygraphviz/commit/fe442dc16accb629c3feaf157af75f67ccabbd6e) to a clone of the repository and install the patched repository using the steps from [here](https://github.com/pygraphviz/pygraphviz/issues/58) pointing to a 64-bit version of graphviz, obtainable from [here](https://ci.appveyor.com/project/ellson/graphviz/build/job/fry9cmn4jfegw13l/artifacts)

## Corpus
The corpus used to validate the approaches is artificially built to mimic 
real-world faults using the methodology proposed in Herzig et al.[[1]](#1): 

1. Have been committed by the same developer within 14 days of each other
    with no other commit by the same developer in between them.
2. Change namespaces whose names have a large prefix match.
3. Contain files that are frequently changed together.
4. Do not contain certain keywords (such as 'fix', 'bug', 'feature','implement') multiple times.

The first criterion mimics the process by which a developer forgets to commit
their working directory before picking up a new task. The next criterion is an
adaptation of Herzig et al.'s 'Change close packages' criterion to the C#
environment. The third considers files that are coupled in the version history,
thus creating a tangled commit not too dissimilar from commits that naturally
occurred. The intuition being that if commit *A* touches file *f<sub>A</sub>* and 
commit *B* touches file *f<sub>B</sub>*, s.t. *f<sub>A</sub>* and *f<sub>B</sub>* 
are frequently committed together, then *A* and *B* should be tangled. The final 
criterion is a heuristic to ensure that we do not consider tangling commits that 
we are certain are not atomic. We add this condition to mitigate the problem of 
tangling actually tangled commits which would cause an issue when computing 
ground truth.

As we cannot include the studied projects here, we instead link them here and provide the 
latest SHA used for this project:

| Project                                                         | LOC | # of Commits | Last revision |
|-----------------------------------------------------------------|-----|-------------|---------------|
| [Commandline](https://github.com/commandlineparser/commandline) | 11602 | 1556        | 67f77e1| 
| [CommonMark](https://github.com/Knagis/CommonMark.NET)          | 14613 | 418         | f3d5453|
| [Hangfire](https://github.com/HangfireIO/Hangfire)              | 40263 | 2889        | 175207c|
| [Humanizer](https://github.com/Humanizr/Humanizer)              | 56357 | 1647        | 604ebcc|
| [Lean](https://github.com/QuantConnect/Lean)                    | 242974 | 7086        | 71bc0fa|
| [Nancy](https://github.com/NancyFx/Nancy)                       | 79192 | 5497        | dbdbe94|
| [Newtonsoft.Json](https://github.com/JamesNK/Newtonsoft.Json)   | 71704 | 299         | 4f8832a|
| [Ninject](https://github.com/ninject/ninject)                   | 13656 | 784         | 6a7ed2b|
| [RestSharp](https://github.com/restsharp/RestSharp)             | 16233 | 1440        | b52b9be|
| [Jfreechart](https://github.com/jfree/jfreechart) (Java)        | TBD | 4218        | d6c1bf|

To reconstruct the corpus, one would first `git clone` under `./subjects` the project for which they are building it 
followed by 
a `git reset --hard <Last revision>`. With the project in the correct state, one would then use the scripts provided in 
`./tangle_concerns`.

Let's say we are recreating the data for **Commandline**, and are using WSL1 with Ubuntu to complete this task.
From the root of the project one would first run:
```bash
[../flexeme] $ python3 tangle_concerns/tangle_by_file.py Commandline
```
This should produce the file `./out/Commandline/Commandline_history_filtered_flat.json` which represents 
all the valid intervals of commits w.r.t. our tangle criteria. Next, one would run:
```bash
[../flexeme] $ python3 generate_corpus.py \
./out/Commandline/Commandline_history_filtered_flat.json \
./subjects/Commandline \
./temp \ # Temporary location used during this process
0 \ # Thread id numbering starts from this id, used to avoid overlap in ./temp
12 \ # Number of threads in use
./extractor/Release/PdgExtractor.exe  # Location of the PDG Extractor
```

Java:
```
 python tangle_concerns/generate_corpus.py out/basic.json subjects/basic .tmp 1 1 /Users/thomas/Workplace/Flexeme/extractors/codechanges-checker-all.jar
```

The last step creates a δPDG per file, scripts moving forward assume a single file per commit. To obtain that we want to run the following snippet over all generated data:
```python
from deltaPDG.Util.merge_deltaPDGs import merge_deltas_for_a_commit

for path_to_commit from all_paths:
    merged = merge_deltas_for_a_commit(get_pattern_paths('*.cs.dot', path_to_commit))
    nx.drawing.nx_pydot.write_dot(merged, os.path.join(path_to_commit, 'merged.dot'))
```
Please mind that later scripts assume the filename `merged.dot`. To generate `all_paths`, one can use the `*_history_filtered_flat.json` previously generated and the following logic: data is always in `./data/corpora/<Project Name>/<first sha in json chain>_<last sha in json chain>/<num commits merged>/`.

Finally, we want to ensure that the data generated reflect the correct number of _surviving_ concerns. To do this we run
a final script:
```bash
[../flexeme] $ python3 scan_and_clean_corpora.py Commandline
```

For convenience, we provide the final result of this process for all our subjects as `./data.zip` [here](https://liveuclac-my.sharepoint.com/:f:/g/personal/ucabpp1_ucl_ac_uk/EkNrHsAyWPZCkhOsXXvERmIBpiraNlREcEEO4keHUFdRhA?e=6vxyCs). Password: `Flexeme_data_2020`.

To generate the corpus needed to run the diff-regions baseline, one would use the scripts provided in `./confidence_voters/Util`.

One would have to first the `~_history.json` as described above, then generate the main corpus file as so:

```bash
[../flexeme] $ python3 ./confidence_voters/Util/generate_corpus_file.py \
<temp folder>
<Repository 1> \
...
<Repository n>
```

For example, for the project Commandline and the temporary folder `./temp`

```bash
[../flexeme] $ python3 ./confidence_voters/Util/generate_corpus_file.py ./temp Commandline
```

This corpus will not have correct concept numbers if used directly, so one should then run:

```bash
[../flexeme] $ python3 ./confidence_voters/Util/clean_bl_corpus.py ./out \
<Repository 1> \
...
<Repository n>
```

For Commandline, this would look like so:

```bash
[../flexeme] $ python3 ./confidence_voters/Util/clean_bl_corpus.py ./out Commandline
```

This will change the number of concepts to match the number of surviving concepts.

For convenience, we provide the final result of this process for all our subjects as `./out.zip` [here](https://liveuclac-my.sharepoint.com/:f:/g/personal/ucabpp1_ucl_ac_uk/EkNrHsAyWPZCkhOsXXvERmIBpiraNlREcEEO4keHUFdRhA?e=6vxyCs). Password: `Flexeme_data_2020`.

## 𝛿-PDG construction
To demonstrate how we generate 𝛿-PDG, consider this snippet:
```python
v1_pdg_generator = PDG_Generator(extractor_location=extractor_location,
                                 repository_location=v1,
                                 target_filename='before_pdg.dot',
                                 target_location='./temp/%d' % id_)
v2_pdg_generator = PDG_Generator(extractor_location=extractor_location,
                                 repository_location=v2,
                                 target_filename='after_pdg.dot',
                                 target_location='./temp/%d' % id_)
[...]
v1_pdg_generator(filename)
v2_pdg_generator(filename)
delta_gen = deltaPDG('./temp/%d/before_pdg.dot' % id_, m_fuzziness=method_fuzziness,
                     n_fuzziness=node_fuzziness)
delta_pdg = delta_gen('./temp/%d/after_pdg.dot' % id_,
                      [ch for ch in changes if ch[1] == filename])
```
The `v[1/2]_pdg_generator` is instantiated with the repository at version 1 and version 2 respectively.
They will output the PDGs as the specified filenames.
When we have a file touched by a patch, say `filename`, we then call these generators on the same file.
We instantiate the deltaPDG with the beforePDG. We then call it with the afterPDG.
`[ch for ch in changes if ch[1] == filename]` is the seed from where we start computing the 𝛿-PDG, it 
represents the changes that concern our considered file.

Note: To include the name-flow information in the construction, one must first run 
[RefiNym](https://github.com/askdash/refinym) by Dash et al.[[3]](#3) and store the result as `nameflow.json`.

## Evaluation
To re-run our evaluation consider the following scripts:

1. To run the Herzig et al. reimplementation:
```bash
[../flexeme] $ python3 ./Util/cv_evaluation_driver.py \
<number of repeats for timing> \
<csv filename> \
false \
<edge types kept> \
<If we should use file distance: true/false> \
<If we should use call distance: true/false> \
<If we should use dataflow: true/false> \
<If we should use namespace distance: true/false> \
<If we should use change coupling: true/false> \
<Repository 1> \
...
<Repository n>
```
For example for Commandline, with all confidence voters being used and all edges maintained (the paper setting):
```bash
[../flexeme] $ python3 ./Util/cv_evaluation_driver.py \
10 \
bl_results_fd_cd_d_ns_cc_ \
false \
all \
true \
true \
true \
true \
true \
Commandline
```

2. To run our adaptation of Herzig et al.'s method to work on our proposed 𝛿-PDG:
```bash
[../flexeme] $ python3 ./Util/cv_evaluation_driver.py \
<number of repeats for timing> \
<csv filename> \
true \
<Repository 1> \
...
<Repository n>
```
For example for Commandline, with all confidence voters being used and all edges maintained (the paper setting):
```bash
[../flexeme] $ python3 ./Util/cv_evaluation_driver.py 10 bl_graph true Commandline
```

3. To run the Barnett et al. reimplementation:
```bash
[../flexeme] $ python3 ./Util/graph_evaluation_driver.py \
<number of repeats for timing> \
du
<Repository 1> \
...
<Repository n>
```
For example for Commandline
```bash
[../flexeme] $ python3 ./Util/graph_evaluation_driver.py 10 du Commandline
```

4. To run the our proposed method:
```bash
[../flexeme] $ python3 ./Util/graph_evaluation_driver.py \
<number of repeats for timing> \
wl
<Repository 1> \
...
<Repository n>
```
For example for Commandline
```bash
[../flexeme] $ python3 ./Util/graph_evaluation_driver.py 10 wl Commandline
```

For convenience, we provide the evaluation results as `./out.zip` [here](https://liveuclac-my.sharepoint.com/:f:/g/personal/ucabpp1_ucl_ac_uk/EkNrHsAyWPZCkhOsXXvERmIBpiraNlREcEEO4keHUFdRhA?e=6vxyCs). Password: `Flexeme_data_2020`.

The method to CSV mapping is as follows:

| Method | CSV Filename|
|--------|-------------|
|Barnett et al.|du_results_raw|
|Herzig et al.|bl_results_fd_cd_d_ns_cc_|
|δ-PDG + CV|bl_graph_results|
|Heddle (δ-NFG + WL)|wl_all_1_results_raw|

## Analysis

We provide our analysis as a jupyter notebook: `./analysis/Exploring Results.ipynb`.
The notebook depends on the following python packages:
```
pandas numpy matplotlib seaborn networkx pydot tqdm jsonpickle
```

The results of the analysis is presented in the notebook itself. It also outputs the following files:
```
Accuracy[_by_concepts].pdf: The boxplot of the accuracy of the compared methods
Time[_by_concepts].pdf: The boxplot of the time taken of the compared methods
results.csv: The accuracy and time taken results to be converted to a LaTeX table
stats.csv: The final used corpus statistics to be converted to a LaTeX table
```

## Using the proposed methods
To use either confidence_voter approach to untangle a commit, call their `cluster_diffs` method.
Example from the evaluation harness:
```python
labels, time_ = cluster_diffs(concepts, # Number of concerns we target
                              data, # A preparsed representation of diff regions
                              delta_PDG_location, # Location of this commit's deltaPDG
                              file_lengthss, # Matrix that contains file lengths per commit
                              occurrence_matrix, # Co-occurrence matrix of files in the history of this project
                              file_index_map, # Lookup table from filenames to occurrence_matrix indices
                              times_, # Number of repeats for timing
                              use_file_dist=use_file_dist, # If we use the file distance voter
                              use_call_distance=use_call_distance, # If we use the call distance voter
                              use_change_coupling=use_change_coupling, # If we use the change coupling voter
                              use_data=use_data, # If we use the dataflow reachability voter
                              use_namespace=use_namespace) # If we use the namespace distance voter
```


To use our reimplementation of Barnett et al's method or our proposed method, call their `untangle` method.
Example adapted from the evaluation harness.
```python
if mode == 'du':
    du_untangle(graph, times)
else:
    wl_untangle(graph, times, k_hop)
```

1. `graph` represents the deltaPDG we wish to untangle.
1. `times` represents the number of repeats for timing, one would use `1` in practice.
1. `k_hop` represents the number of hops taken when building the forest of graphs prior to re-clustering via WL-kernel similarity
and agglomerative clustering.

## Cite

If you use this project, please cite the paper as follows:
```bibtex
@inproceedings{10.1145/3368089.3409693,
author = {P\^{a}rțachi, Profir-Petru and Dash, Santanu Kumar and Allamanis, Miltiadis and Barr, Earl T.},
title = {Flexeme: Untangling Commits Using Lexical Flows},
year = {2020},
isbn = {9781450370431},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
url = {https://doi.org/10.1145/3368089.3409693},
doi = {10.1145/3368089.3409693},
booktitle = {Proceedings of the 28th ACM Joint Meeting on European Software Engineering Conference and Symposium on the Foundations of Software Engineering},
pages = {63–74},
numpages = {12},
keywords = {graph kernels, clustering, commint untangling},
location = {Virtual Event, USA},
series = {ESEC/FSE 2020}
}
```

## References
<a id="1">[1]</a> Herzig, K., Just, S., & Zeller, A. (2016). The impact of tangled code changes on defect prediction models. 
Empirical Software Engineering, 21(2), 303–336. https://doi.org/10.1007/s10664-015-9376-6

<a id="2">[2]</a> Barnett, M., Bird, C., Brunet, J., & Lahiri, S. K. (2015). Helping developers help themselves: Automatic decomposition of 
code review changesets. Proceedings - International Conference on Software Engineering, 1(August 2014), 134–144. https://doi.org/10.1109/ICSE.2015.35

<a id="2">[3]</a> Dash, S. K., Allamanis, M., & Barr, E. T. (2018). RefiNym: using names to refine types. In Proceedings of the 2018 26th 
ACM Joint Meeting on European Software Engineering Conference and Symposium on the Foundations of Software Engineering - ESEC/FSE 2018 (pp. 107–117). https://doi.org/10.1145/3236024.3236042
