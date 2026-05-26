import re
from pathlib import Path

from ..tfpathlib import TuflowPath
from .geom_suffix import get_geom_suffix


def get_iter_number(in_name: str, geom_ext: str) -> str:
    """Identify and return the iteration number if it exists within the input name. It is assumed any file extensions
    are removed before calling this routine.

    Examples
    --------
    >>> get_iter_number('2d_code_001_R', '_R')
    '001'

    Parameters
    ----------
    in_name : str
        The input name.
    geom_ext : str
        The geometry extension (e.g. '_R').

    Returns
    -------
    str
        The iteration number.
    """
    iter_number = re.findall(r'\d+[a-z]{{0,2}}(?={0}$)'.format(geom_ext), in_name)
    if iter_number:
        return iter_number[0]
    return '001'


def name_without_number_part(name_: str) -> str:
    """Return the input name without the iteration number. It is assumed any file extensions are removed before calling
    this routine.

    Examples
    --------
    >>> name_without_number_part('2d_code_001_R')
    '2d_code_R'

    Parameters
    ----------
    name_ : str
        The input name.

    Returns
    -------
    str
        The name without the iteration number.
    """
    number_part = re.findall(r'_\d+[a-z]{0,2}(?:_[PLR])?$', name_, flags=re.IGNORECASE)
    if number_part:
        return re.sub(re.escape(number_part[0]), '', name_)
    return name_


def auto_increment_name(in_name: str) -> str:
    """Automatically increment the input name by one. The zero padding should be respected based on the input.
    If a number does not exist in the name, one is added. It is assumed any file extensions are removed
    before calling this routine.

    Examples
    --------
    >>> auto_increment_name('2d_code_001_R')
    '2d_code_002_R'
    >>> auto_increment_name('2d_code_R')
    '2d_code_001_R'

    Parameters
    ----------
    in_name : str
        The input name.

    Returns
    -------
    str
        The incremented name.
    """
    ext = ''
    if TuflowPath(in_name).suffix:
        ext = TuflowPath(in_name).suffix
        in_name = TuflowPath(in_name).stem

    number_part = re.findall(r'_\d+[a-z]{0,2}(?:_[PLR])?$', in_name, flags=re.IGNORECASE)
    geom_ext = get_geom_suffix(in_name)

    if not number_part:
        if geom_ext:
            out_number_part = f'_001{geom_ext}'
            return re.sub(re.escape(geom_ext), re.escape(out_number_part), in_name) + ext
        else:
            return f'{in_name}_001{ext}'

    out_name = re.sub(re.escape(number_part[0]), '', in_name)
    iter_number = get_iter_number(number_part[0], geom_ext)
    pad = len(iter_number)
    iter_number = f'{int(iter_number) + 1:0{pad}d}'
    return f'{out_name}_{iter_number}{geom_ext}{ext}'


def increment_new_name(name_: str, inc: str) -> str:
    """Increment the name with the given increment. The increment should be a string representing a number, or 'auto' or
    'inplace'. If 'auto' is given, the name will be automatically incremented. If 'inplace' is given, the name will not
    be changed.

    Examples
    --------
    >>> increment_new_name('2d_code_001_R', 'auto')
    '2d_code_002_R'
    >>> increment_new_name('2d_code_001_R', 'inplace')
    '2d_code_001_R'
    >>> increment_new_name('2d_code_001_R', '005')
    '2d_code_005_R'

    Parameters
    ----------
    name_ : str
        The input name.
    inc : str
        The increment number (as a string), or 'auto' or 'inplace'.

    Returns
    -------
    str
        The incremented name.
    """
    if inc.lower() == 'inplace':
        return name_
    elif inc.lower() == 'auto':
        return auto_increment_name(name_)
    else:
        return f'{name_without_number_part(TuflowPath(name_).stem)}_{inc}{TuflowPath(name_).suffix}'


def increment_fpath(fpath: str | Path, inc: str) -> TuflowPath:
    """Increment the file path with the given increment. The increment should be a string representing a number, or
    'auto', or 'inplace'. If 'auto' is given, the name will be automatically incremented. If 'inplace' is given, the
    name will not be changed.

    See :func:`increment_new_name` for more information.

    Parameters
    ----------
    fpath : PathLike
        The input file path.
    inc : str
        The increment number (as a string), or 'auto' or 'inplace'.

    Returns
    -------
    TuflowPath
        The incremented file path.
    """
    p = TuflowPath(fpath)
    return TuflowPath(f'{p.parent}/{increment_new_name(p.name, inc)}')
