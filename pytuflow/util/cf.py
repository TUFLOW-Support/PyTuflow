"""control file module

Utilities to help build control file commands.

Examples
--------
:func:`build_tuflow_command_string` can be used to help build TUFLOW command strings. It allows basic use, and
more complicated use when multiple inputs are required for a single command.

>>> from pytuflow.util.cf import build_tuflow_command_string
>>> build_tuflow_command_string('Tutorial Model == ON')  # basic use
'Tutorial Model == ON'
>>> build_tuflow_command_string(r'C:\TUFLOW\model\gis\2d_code_001_R.shp')  # GIS input, the correct command will be chosen
'Read GIS Code == gis\\2d_code_001_R.shp'
>>> build_tuflow_command_string([r'C:\TUFLOW\model\gis\2d_zsh_L.shp', r'C:\TUFLOW\model\gis\2d_zsh_P.shp'])  # Multiple GIS inputs
'Read GIS Z Shape == gis\\2d_zsh_L.shp | gis\\2d_zsh_P.shp'
>>> build_tuflow_command_string([r'C:\TUFLOW\model\gis\2d_mat_001_R.shp', 2])  # Use the 2nd attribute for a material command
'Read GIS Mat == gis\\2d_mat_001_R.shp | 2'

Multiple commands can be build using :func:`build_gis_commands_from_file` which reads a GIS files and returns a list of commands

>>> from pytuflow.util.cf import build_gis_commands_from_file
>>> build_gis_commands_from_file([r'C:\TUFLOW\model\gis\2d_code_001_R.shp'])
['Read GIS Code == gis\\2d_code_001_R.shp']
>>> build_gis_commands_from_file([r'C:\TUFLOW\model\gis\2d_code_001_R.shp', r'C:\TUFLOW\model\gis\2d_mat_001_R.shp'])
['Read GIS Code == gis\\2d_code_001_R.shp', 'Read GIS Mat == gis\\2d_mat_001_R.shp']
>>> build_gis_commands_from_file([r'C:\TUFLOW\model\gis\2d_code_001_R.shp', r'C:\TUFLOW\model\gis\2d_zsh_L.shp', r'C:\TUFLOW\model\gis\2d_zsh_P.shp'])
['Read GIS Code == gis\\2d_code_001_R.shp', 'Read GIS Z Shape == gis\\2d_zsh_L.shp | gis\\2d_zsh_P.shp']
"""


from pytuflow.tmf.tmf.tuflow_model_files.utils.commands import (build_tuflow_command_string,
                                                                build_gis_commands_from_file, guess_command_from_text,
                                                                try_find_control_file)


# nasty hack to get autosummary automodule to work
build_tuflow_command_string.__module__ = 'pytuflow.util.cf'
build_gis_commands_from_file.__module__ = 'pytuflow.util.cf'
guess_command_from_text.__module__ = 'pytuflow.util.cf'
try_find_control_file.__module__ = 'pytuflow.util.cf'
