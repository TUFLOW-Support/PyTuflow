import itertools
import typing


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


def list_depth(lst: typing.Iterable) -> int:
    def is_bottom(lst1: typing.Iterable) -> bool:
        return all(isinstance(x, (float, int, str)) for x in lst1)

    dep = 1
    lst_ = lst
    while not is_bottom(lst_):
        dep += 1
        try:
            lst_ = lst_[0]
        except (TypeError, IndexError):
            break

    return dep
