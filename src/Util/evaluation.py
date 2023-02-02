import numpy as np
import scipy.optimize


def evaluate(labels, truth, q=None):
    if len(truth) == 0 or q == 0:
        return float('nan'), float('nan')
    q = max(truth, default=0) + 1 if q is None else q
    if q == 1:
        hit = 0
        for i in range(len(truth)):
            hit += (truth[i] == labels[i])
        acc = hit / len(truth)
        acc = max(acc, 1 - acc)
        overlap = float('nan')
    elif q == 2:
        hit = 0
        for i in range(len(truth)):
            hit += (truth[i] == labels[i])
        acc = hit / len(truth)
        acc = max(acc, 1 - acc)
        overlap = 2 * (acc - .5)
    else:
        cost = np.zeros(shape=(q, q))
        for a in range(q):
            for b in range(q):
                relevant_slice = truth[labels == a]
                cost[a][b] -= len(relevant_slice[relevant_slice == b]) ** 2

        _, col_ind = scipy.optimize.linear_sum_assignment(cost)

        for n in range(len(labels)):
            labels[n] = col_ind[labels[n]] if 0 <= labels[n] < q else -1
        hit = 0
        for i in range(len(truth)):
            hit += (truth[i] == labels[i])
        acc = hit / len(truth)
        overlap = (acc - 1 / q) / (1 - 1 / q)
    return acc, overlap
