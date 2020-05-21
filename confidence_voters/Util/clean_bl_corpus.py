import os
import sys

import jsonpickle

if __name__ == '__main__':
    output_folder = sys.argv[1]
    projects = sys.argv[2:]
    for project in projects:
        in_file = os.path.join(output_folder, project, 'bl_corpus.json')
        out_file = os.path.join(output_folder, project, 'bl_corpus_clean.json')
        with open(in_file) as f:
            corpus, file_len_map = jsonpickle.decode(f.read())
        corpus = {k: (i, [p for p in v if p[1].split('.')[-1] == 'cs']) for k, (i, v) in corpus.items()}
        new_corpus = dict()
        for k, (i, v) in corpus.items():
            concepts = list({p[-1] for p in v})
            v = [(ch, file, bc, ac, line, concepts.index(concept)) for ch, file, bc, ac, line, concept in v]
            new_corpus[k] = (len(concepts), v)
        new_corpus = {k: (i, v) for k, (i, v) in new_corpus.items() if i >= 1}
        with open(out_file, 'w') as f:
            f.write(jsonpickle.encode((new_corpus, file_len_map)))
