#!/bin/bash

# Creates synthetic commits for all projects in the dataset.
# Results are written to `out/<repository>/<repository>_history_filtered_flat.json`.
python3 tangle_concerns/tangle_by_file.py glide
python3 tangle_concerns/tangle_by_file.py netty
python3 tangle_concerns/tangle_by_file.py antlr4
python3 tangle_concerns/tangle_by_file.py nomulus
python3 tangle_concerns/tangle_by_file.py cassandra
python3 tangle_concerns/tangle_by_file.py realm-java
python3 tangle_concerns/tangle_by_file.py deeplearning4j
python3 tangle_concerns/tangle_by_file.py storm
python3 tangle_concerns/tangle_by_file.py rocketmq
python3 tangle_concerns/tangle_by_file.py elasticsearch