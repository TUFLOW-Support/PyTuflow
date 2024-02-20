import itertools


def make_one_dim(arr):
    return list(itertools.chain.from_iterable(arr))