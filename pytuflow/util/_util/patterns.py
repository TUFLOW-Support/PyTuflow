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


from ..._tmf.tmf.tuflow_model_files.tfstrings.patterns import (increment_fpath, expand_and_get_files)
