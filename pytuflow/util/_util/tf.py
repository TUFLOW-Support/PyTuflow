"""TUFLOW binary/version utilities.

This module contains functions to register/save TUFLOW versions and their binary file paths. This
enables specific versions of TUFLOW to be called easily in other utilities/functions within
the TUFLOW library, and also by the user in scripts and workflows.

Examples
--------
How to register a TUFLOW binary file path:

>>> # Register a specific TUFLOW binary version
>>> from pytuflow.util import register_tuflow_binary, tuflow_binaries
>>> register_tuflow_binary('2023-03-AE', 'C:/TUFLOW/releases/2023-03-AE/TUFLOW_iSP_w64.exe')
>>> tuflow_binaries.get('2023-03-AE')
'C:/TUFLOW/releases/2023-03-AE/TUFLOW_iSP_w64.exe'

How to register a folder containing multiple TUFLOW releases:

>>> # Register a folder containing multiple TUFLOW releases
>>> from pytuflow.util import register_tuflow_binary_folder, tuflow_binaries
>>> register_tuflow_binary_folder('C:/TUFLOW/releases')
>>> tuflow_binaries.get('2023-03-AE')
'C:/TUFLOW/releases/2023-03-AE/TUFLOW_iSP_w64.exe'
"""


from pytuflow._tmf.tmf.tuflow_model_files.utils.tuflow_binaries import (TuflowBinaries, tuflow_binaries,
                                                                       register_tuflow_binary,
                                                                       register_tuflow_binary_folder)
