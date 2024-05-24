"""patterns module.

This module contains functions to help with pattern matching in file names to find, resolve, and expand variables
in text and file paths. This module also contains functions to help with TUFLOW file name incrementing.

Examples
--------
>>> # increment the file path
>>> increment_fpath('path/to/2d_code_001_R.shp', 'auto')
'path/to/2d_code_002_R.shp'
>>> increment_fpath('path/to/2d_code_001_R.shp', '005')
'path/to/2d_code_005_R.shp'

>>> # expand wildcard to get all matching files
>>> expand_and_get_files(r'C:\TUFLOW\model\gis', '2d_code_<<~s~>>_R.shp')
['C:\\TUFLOW\\model\\gis\\2d_code_001_R.shp', 'C:\\TUFLOW\\model\\gis\\2d_code_002_R.shp', ...]
"""


from pytuflow.tmf.tmf.tuflow_model_files.utils.patterns import (extract_names_from_pattern, identify_expanded_name,
                                                                replace_exact_names, get_geom_ext, get_iter_number,
                                                                name_without_number_part, auto_increment_name,
                                                                increment_new_name, increment_fpath, contains_variable,
                                                                expand_and_get_files)

# nasty hack to get autosummary automodule to work
extract_names_from_pattern.__module__ = 'pytuflow.util.patterns'
identify_expanded_name.__module__ = 'pytuflow.util.patterns'
replace_exact_names.__module__ = 'pytuflow.util.patterns'
get_geom_ext.__module__ = 'pytuflow.util.patterns'
get_iter_number.__module__ = 'pytuflow.util.patterns'
name_without_number_part.__module__ = 'pytuflow.util.patterns'
auto_increment_name.__module__ = 'pytuflow.util.patterns'
increment_new_name.__module__ = 'pytuflow.util.patterns'
increment_fpath.__module__ = 'pytuflow.util.patterns'
contains_variable.__module__ = 'pytuflow.util.patterns'
expand_and_get_files.__module__ = 'pytuflow.util.patterns'
