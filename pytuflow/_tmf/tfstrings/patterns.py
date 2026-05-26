import logging
import re
from pathlib import Path

import numpy as np
from typing import Any

from ..tmf_types import PathLike
from ..tfstrings.globify import globify



logger = logging.getLogger('pytuflow')

var_regex = re.compile(r'(<<\w{3,}>>|<<[A-DF-RT-df-rt-z]+.+>>|<<~s\D\w+~>>|<<~e\D\w+~>>|<<~s[A-z]+~>>|<<~e[A-z]+~>>)')
wildcard_regex = re.compile(r'<<.+>>')


def extract_names_from_pattern(string_with_var: str, extraction_string: str, pattern: str) -> dict[str, str]:
    """Given a string with variables in it (e.g. 2d_code_<<~s~>>_001.shp) and an input string to compare to
    (e.g. 2d_code_M01_001.shp) a variable value can be extracted for the variable name (<<~s~>> = 'M01').

    The return is a dictionary with the variable name/value pair e.g. {'<<~s~>>': 'M01'}

    The pattern should be a regex pattern. This routine will extract multiple variables if found in the template
    string (e.g. pattern '<<~s\\d~>>' could extract <<~s1~>> and <<~s2~>> from the template string). The variable
    may appear multiple times in the name and that is ok.

    There are given situations where it is not possible to resolve what the variable name since it could be
    expanded in multiple ways (e.g. 2d_code_<<~e1~>><<~e2~>>_001.shp - 2d_code_100yr2hr_001.shp).
    Because the variables are not delimited, the values could be expanded in multiple ways. Where this happens
    the return name will be the same as the variable name (e.g. {'<<~e1~>>': '<<~e1~>>', '<<~e2~>>': '<<~e2~>>'}).

    Another example of when it may struggle to figure out the variable value is when event variable names are
    used. As event variables don't follow a specific pattern (aren't surrounded by <<>>) then it isn't possible
    to recognise them unless you have a list of them.

    Parameters
    ----------
    string_with_var : str
        The string with variables in it.
    extraction_string : str
        The string to compare to.
    pattern : str
        The regex pattern to use to extract the variable names.

    Returns
    -------
    dict[str, str]
        The variable name/value pair.
    """
    extracted_names = {}
    for var_name in re.findall(pattern, string_with_var, flags=re.IGNORECASE):
        if var_name in extracted_names:
            continue
        extracted_names[var_name] = None
        if re.findall(r'<<~[EeSs]1?~>>', var_name):  # <<~s~>> will be treated the same as <<~s1~>>
            var_name_ = re.sub(r'1?~>>', '1?~>>', var_name)
        else:
            var_name_ = var_name

        names = identify_expanded_name(string_with_var, extraction_string, var_name_)

        if len(set(names)) > 1:
            name_ = [x for x in names if x][0]
        elif not names[0]:
            name_ = var_name
        else:
            name_ = names[0]

        extracted_names[var_name] = name_

    return extracted_names


def identify_expanded_name(string_with_var: str, extraction_string: str, var_name: str) -> list[str]:
    """Given a string with variables in it, an extraction string to compare to, and a variable name, this
    routine will identify what the variable name has expanded to.

    Unlike :func:`extract_names_from_pattern`, the pattern should be specific, not a regex pattern
    (e.g. should be '<<~s1~>>' not <<~[se]\\d.~>>). This routine is used by :func:`extract_names_from_pattern`
    to do most of the heavy lifting in terms of identifying the name for a specific variable.

    The return type is a list of found variable values (as the variable name could appear multiple times e.g.
    2d_code_<<~s1~>>_<<~s1~>>_001.shp). It is up to the calling routine to check if the return names are consistent.

    If it isn't possible to determine the variable value, the return will be a list of empty strings for each
    time the variable appears in the string.

    Parameters
    ----------
    string_with_var : str
        The string with variables in it.
    extraction_string : str
        The string to compare to.
    var_name : str
        The variable name to identify.

    Returns
    -------
    list[str]
        The variable values.
    """

    # check to see if the variable name is 'isolated' (i.e. not directly next to another variable name)
    # if it is not isolated, don't try and expand as it's not possible to figure out the variable value is
    # trying to expand it could lead to incorrect results which is worse than not finding anything
    if re.findall(f'(<<.+?>>){var_name}', string_with_var, flags=re.IGNORECASE) or \
            re.findall(f'{var_name}(<<.+?>>)', string_with_var, flags=re.IGNORECASE):
        isolated_scenario_name = False
        for match in re.finditer(var_name, string_with_var, flags=re.IGNORECASE):
            span = match.span()
            if span[0] > 1:
                if string_with_var[span[0] - 2:span[0]] == '>>':
                    continue
            if span[1] < len(string_with_var) - 1:
                if string_with_var[span[1]:span[1] + 2] == '<<':
                    continue
            isolated_scenario_name = True
        if not isolated_scenario_name:
            return ['' for _ in range(len(re.findall(var_name, string_with_var, flags=re.IGNORECASE)))]

    # break the input string into parts around the variable name(s)
    # (e.g. 2d_code_<<~s1~>>_001.shp -> ['2d_code_', '_001.shp'])
    # check for other possible variable names that could appear in the string and replace with globbing
    # build regex patterns for each part then index where they appear in the extraction string
    # any part that has not been found will be the missing variable value(s)
    # the tricky part can be knowing when to use a greedy match or lazy match and when to insert additional globbing
    s_parts = re.split(var_name, string_with_var, flags=re.IGNORECASE)
    names = []
    i2_prev = -1
    for k in range(len(s_parts) - 1):
        s1 = '.+?'.join([re.escape(x) for x in s_parts[:k+1]])
        if len(s_parts) > k + 1:
            if len(s_parts) > k + 2:
                if s1[-2:] == '>>':
                    s1 = f'{s1}(?={".+".join([re.escape(x) for x in s_parts[k+1:]])})'
                else:
                    s1 = f'{s1}(?=.+{".+".join([re.escape(x) for x in s_parts[k + 1:]])})'
            else:
                s1 = f'{s1}(?=.+{re.escape(s_parts[k + 1])})'
        s2 = '.+?'.join([re.escape(x) for x in s_parts[k+1:]])
        s1_ = re.sub('<<.+?>>', '.+?', s1, flags=re.IGNORECASE)
        s2_ = re.sub('<<.+?>>', '.+?', s2, flags=re.IGNORECASE)
        i2 = -2
        i3 = 0
        found_match = True
        input_string_ = extraction_string
        while i2 < i2_prev and found_match:
            found_match = False
            for m in re.finditer(s1_, input_string_, flags=re.IGNORECASE):
                found_match = True
                _, i2 = m.span()
                break
            i2 += i3
            i3 = i2 + 1
            input_string_ = extraction_string[i2 + 1:]

        if not found_match:
            names.append('')
            continue

        i2_prev = i2

        found_match = True
        j2 = -1
        j3 = 0
        input_string_ = extraction_string
        while j2 < i2 and found_match:
            found_match = False
            for m in re.finditer(s2_, input_string_, flags=re.IGNORECASE):
                found_match = True
                j2, _ = m.span()
                j2 += j3
                j3 = j2 + 1
                input_string_ = extraction_string[j2 + 1:]
                break

        names.append(extraction_string[i2:j2])

    return names


def replace_exact_names(pattern: str, name_map: dict[str, Any], input_string: str) -> str:
    """Use regex substitution to replace variable names with their values.

    The pattern is a regex pattern or if the 'pattern' argument == 'variable pattern' it will
    use the precompiled regex pattern that is specifically for TUFLOW variable names that won't
    select event or scenario names e.g. <<~s1~>> or <<~e1~>>  or even <<s>> or <<e>>.

    The map is a dictionary of variable names and their values. The map is assumed to not include the <> or ~.
    The keys should also be capitalised e.g. <<~s1~>> would be 'S1' in the map.

    The input string is the string to be modified.

    The routine is not case sensitive and treat variable names <<~e~>> and <<~s~>> as <<~e1~>> and <<~s1~>>.
    The routine will also maintain the variable value type i.e. if the value is an integer, the return value
    will be an integer.

    Parameters
    ----------
    pattern : str
        The regex pattern to use to find the variable names. Or 'variable pattern' to use the precompiled
        regex pattern for TUFLOW variable names.
    name_map : dict[str, Any]
        The variable name/value pair.
    input_string : str
        The string to modify.

    Returns
    -------
    str
        The modified string.
    """

    # noinspection PyUnreachableCode
    if not isinstance(input_string, str):
        return input_string

    if pattern == 'variable pattern':
        regex = var_regex
    else:
        regex = re.compile(pattern, flags=re.IGNORECASE)

    output_string = input_string
    for item in regex.findall(input_string):
        if re.findall(r'<<~[SsEe]~>>', item):
            key = re.sub(r'~>>', '1~>>', item)
        else:
            key = item
        if re.findall(r'<<~[SsEe]', item):
            key = key.strip('<~>').upper()
        else:
            key = key.strip('<>').upper()
        if key not in name_map:
            continue
        type_ = type(name_map[key])
        output_string = output_string.replace(item, str(name_map[key]))
        if type_ == float or type_ == np.float64 or type_ == np.float32:
            output_string = float(output_string)
        elif type_ == int or type_ == np.int64 or type_ == np.int32:
            output_string = int(output_string)

    return output_string


def contains_variable(string: str) -> bool:
    """Check if the string contains a variable.

    Examples
    --------
    >>> contains_variable('2d_code_<<~s~>>_001.shp')
    True

    Parameters
    ----------
    string : str
        The input string.

    Returns
    -------
    bool
        True if the string contains a variable, False otherwise.
    """
    return bool(wildcard_regex.findall(string))


def expand_and_get_files(parent: PathLike, relpath: str, patterns: list[str] = ()) -> list[Path]:
    """Expand pattern and return list of files. The parent should not contain any variables. The relpath may contain
    variables. If :code:`patterns` is included, the relpath will be expanded based on the patterns. If no patterns are
    included, the relpath will be expanded based on standard TUFLOW variable convention (i.e. <<>>).

    Parameters
    ----------
    parent : PathLike
        The parent directory.
    relpath : str
        The relative path.
    patterns : list[str], optional
        The patterns to use for expanding the relpath, by default ().

    Returns
    -------
    list[Path]
        The list of files.
    """
    parent = Path(parent)
    req_expanding = False
    if patterns:
        for pattern in patterns:
            if re.findall(relpath, pattern):
                req_expanding = True
                break
        relpath_glob = globify(relpath, patterns)
    else:
        if contains_variable(relpath):
            req_expanding = True
        relpath_glob = globify(relpath, ['<<.+>>'])

    if not req_expanding:
        return [parent / relpath]

    try:
        return [x for x in parent.glob(relpath_glob) if x.is_file()]
    except NotImplementedError:  # this is thrown if relpath is not in-fact a relative path, but an absolute path
        fpath = Path(relpath)
        i = -1
        for i, part in enumerate(fpath.parts):
            if contains_variable(part):
                break
        if i == -1:
            return [fpath]  # shouldn't get here
        parent = Path().joinpath(*fpath.parts[:i])
        relpath = str(Path().joinpath(*fpath.parts[i:]))
        return [x for x in parent.glob(relpath) if x.is_file()]
