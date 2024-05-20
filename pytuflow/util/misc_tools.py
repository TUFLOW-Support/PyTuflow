import itertools


def flatten(arr: list[list]) -> list:
    """Flatten a 2D list into a 1D list. Assumes 2D list is rectangular.

    Parameters
    ----------
    arr : list[list]
        2D list to flatten.

    Returns
    -------
    list
        Flattened 1D list.
    """
    return list(itertools.chain.from_iterable(arr))
