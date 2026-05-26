import re
import sys
import typing
from pathlib import Path

from..tfpathlib import TuflowPath
from ..settings import TCFConfig, _ParseContext
from ..gis import ogr_format, ogr_geom_types, GisFormat
from .line import TuflowLine


CONTROL_FILES = [
    'GEOMETRY CONTROL FILE', 'BC CONTROL FILE', 'ESTRY CONTROL FILE', 'EVENT FILE', 'READ FILE',
    'RAINFALL CONTROL FILE', 'EXTERNAL STRESS FILE', 'QUADTREE CONTROL FILE', 'AD CONTROL FILE',
    'ESTRY CONTROL FILE AUTO', 'SWMM CONTROL FILE'
    ]


class Command(TuflowLine):
    """Class for handling TUFLOW command."""

    def __init__(self, line: str, config: TCFConfig | _ParseContext, parent: Path = None, part_index: int = -1, line_number: int = None):
        super().__init__(line, config, parent)
        self.comment = ''
        self.comment_index = 0
        self.leading_whitespace = ''
        self.command_orig, self.value_orig = self.strip_command(line)
        self.iter_geom_index = -1
        self.geom_count = 0
        self.in_define_block = False
        self._define_blocks = []
        self.empty_geom = None
        self.check_file_prefix = None
        self.value = None
        self.value_expanded_path = None
        self.part_index = part_index  # -1 means it hasn't been separated into parts yet
        self.part_count = 0
        self.line_number = line_number

        self.command = self.command_orig.upper() if self.command_orig is not None else None

        # tuflow treats "/path/to/file" the same as "./path/to/file" - therefore, so must this parser
        abs_path = re.findall(r'(([A-Za-z]:\\)|\\\\)', str(self.value_orig)) and sys.platform == 'win32'
        if not abs_path and self.is_value_a_file() and str(self.value_orig)[0] in ['\\', '/']:
            self.value_orig = f'.{self.value_orig}'

        # expand the value (variables, gpkg syntax) and expand the path to its absolute value
        if self.value_orig:
            self.value = self.expand(self.value_orig)
            if self.is_value_a_folder() or self.is_value_a_file():
                self.value_expanded_path = self.expand_paths()
            self.part_count = self.value.count('|') + 1

        # estry auto stuff
        if self.is_control_file() and str(self.value).upper() == 'AUTO' or self.command == 'ESTRY CONTROL FILE AUTO':
            self.value = config.control_file.with_suffix('.ecf').name
            self.value_expanded_path = config.control_file.with_suffix('.ecf')
            self.part_count = 1

        # spatial database command
        if self.is_spatial_database_command():
            config.set_spatial_database(self.value)
            self.config.set_spatial_database(self.value)

        # check file prefix stuff
        if self.is_check_folder():
            self.check_file_prefix = self.check_folder_prefix()  # local to this command (i.e. not aware if referring to 1d or 2d)

    def __str__(self):
        return self.original_text

    @property
    def define_blocks(self):
        return self._define_blocks

    @define_blocks.setter
    def define_blocks(self, value):
        if value:
            self._define_blocks = value

    def reload_value(self):
        if self.value_orig:
            self.value = self.expand(self.value_orig)
            if self.is_value_a_folder() or self.is_value_a_file():
                self.value_expanded_path = self.expand_paths()
            self.part_count = self.value.count('|') + 1

    def is_number(self, text: str, total_parts: int, index: int) -> bool:
        if not self.is_valid() or not self.value_orig:
            return False

        if index == -1:  # not separated into parts yet - just check the first part for this case
            for cmd in self.parts():
                return cmd.is_number(cmd.value, cmd.part_count, cmd.part_index)

        if self.is_folder(text, total_parts, index):
            return False

        # basic number check
        try:
            float(str(text).strip())
            return True
        except (ValueError, TypeError, AttributeError):
            pass
        is_var = bool(re.match(r'^<<.+>>$', str(text).strip()))
        if not is_var:  # if it is not a variable, then it either is or isn't a number
            return False

        # a number of situations where a variable could be used in place of a number
        # check the specific command, index, and total parts to determine if a number is expected
        if self.is_mat_dbase() and index == 1:
            return True
        if self.is_modify_conveyance() and index == 1:
            return True
        if self.is_read_gis() and index == 0 and total_parts > 1:
            return True
        if self.is_read_grid() and index == 1 and not self.looks_like_gpkg_layer_name(text, total_parts, index):
            return True
        return False

    def is_file(self, text: str, total_parts: int, index: int) -> bool:
        """Checks if the text is a file path."""
        if not self.is_valid() or not self.value_orig or self.is_number(text, total_parts, index):
            return False

        if self.is_mi_prj_string() or self.is_prj_string() or self.is_uk_hazard_formula():
            return False

        is_a_file = (self.is_read_gis() or self.is_read_grid() or self.is_read_tin() or self.is_control_file()
                     or self.is_read_file() or
                     (self.is_read_projection() and not self.is_mi_prj_string() and not self.is_prj_string())
                     or self.is_read_database() or self.is_spatial_database_command())
        if is_a_file:
            return True

        # if it has a suffix that isn't just a number, then it should also be considered a file
        p = TuflowPath(str(self.value))
        if not p.suffix:
            return False
        try:
            float(p.suffix)
            return False
        except (ValueError, TypeError, AttributeError):
            return True

    def is_folder(self, text: str, total_parts: int, index: int) -> bool:
        """Checks if the text is a folder path."""
        return self.is_log_folder() or self.is_output_folder() or self.is_check_folder()

    def should_add_mif_extension(self, text: str, total_parts: int, index: int) -> bool:
        """Adds the .mif extension to the text if it is a GIS file."""
        return False

    def looks_like_gpkg_layer_name(self, text: str, total_parts: int, index: int) -> bool:
        """Checks if the text looks like a GPKG layer name."""
        return (not self.is_number(text, total_parts, index) and not Path(text).suffix and len(Path(text).parts) == 1
                and not self.is_folder(text, total_parts, index))

    def count_geom(self):
        """Returns the number of geometry types in the READ GIS command.

        E.g.
         - MIF file with 2 geometry types will return 2
         - "gis\\shape_file_L.shp | gis\\shape_file_P.shp" - will return 2 - does not check for uniqueness of geometry types
        """
        count = 0
        for i, value in enumerate(str(self.value_expanded_path).split('|')):
            if self.is_value_a_number(value=value, iter_index=i):
                pass
            elif self.is_modify_conveyance() and i > 0:
                pass
            else:
                if ogr_format(self.value_expanded_path) == GisFormat.MIF:
                    count += len(ogr_geom_types(self.value_expanded_path))
                else:
                    count += 1  # shp / gpkg only contains 1 geom type - don't need to know what it is

        return count

    def parts(self) -> typing.Generator['Command', None, None]:
        """Yields parts of the command, splitting by | if present. The yielded Command object will be a copy
        and not be the original Command object."""
        if not self.value_orig:
            return
        val = self.value if self.value is not None else self.value_orig
        for i, part in enumerate(str(val).split('|')):
            string = f'{self.command_orig} == {part.strip()}'
            cmd = Command(string, self.config, self.parent, i)
            cmd.part_count = self.part_count
            yield cmd

    def gis_format(self, settings, value=None) -> GisFormat:
        """Return GIS vector format as an OGR Format driver name (.e.g. 'ESRI Shapefile')
        of input file in READ GIS command.
        """
        if not self.is_valid() or self.value is None and not self.is_read_gis():
            return GisFormat.Unknown

        no_ext_is_mif = not settings.spatial_database or len(TuflowPath(self.value).parts) > 1

        if value is None:
            value = self.value

        return ogr_format(value, no_ext_is_mif)

    def is_vector_file(self):
        if self.part_index == -1:
            for cmd in self.parts():
                return cmd.is_vector_file()
        if self.is_read_gis() and self.part_index == 0 and not self.is_value_a_number_3():
            return True
        if (self.is_read_grid() or self.is_read_tin()) and self.part_index == 1 and not self.is_value_a_number_3():
            return True
        return False

    def is_raster_file(self):
        if self.part_index == -1:
            for cmd in self.parts():
                return cmd.is_raster_file()
        if self.is_read_grid() and self.part_index == 0:
            return True
        if self.is_modify_conveyance() and self.part_index == 2:
            return True
        return False

    def is_tin_file(self):
        if self.part_index == -1:
            for cmd in self.parts():
                return cmd.is_tin_file()
        if self.is_read_tin() and self.part_index == 0:
            return True
        return False

    def is_spatial_database_command(self):
        """Returns True/False if command is setting the spatial database."""
        return self.command == 'SPATIAL DATABASE'

    def re_add_comments(self, new_command, rel_gap = False):
        """Re-add any comments after the command - try and maintain their position as best as possible."""
        if self.comment:
            if len(new_command) >= self.comment_index and not rel_gap:
                self.comment_index = len(new_command) + 1
            if rel_gap and self.comment_index > 0:
                i = self.comment_index - 1
                orig_text = self.original_text.replace('\t', '    ')
                while i + 1 > len(orig_text) or orig_text[i] == ' ' and i > 0:
                    if orig_text[i] == ' ':
                        i -= 1
                dif = max(self.comment_index - i - 1, 1)
            else:
                dif = self.comment_index - len(new_command)
            new_command = f'{new_command}{" " * dif}{self.comment}'

        return f'{new_command}\n'

    def is_valid(self):
        """Returns if command contains a valid command (i.e. not a comment or blank)."""
        return self.command is not None

    def is_control_file(self):
        """Returns whether command is referencing a control file."""
        if self.command and re.findall(r'^READ\s', str(self.command)) and self.command != 'READ FILE':
            cmd = re.sub(r'^READ\s', '', self.command)
        else:
            cmd = self.command
        return cmd in CONTROL_FILES and self.value is not None and TuflowPath(self.value).suffix.upper() != '.CSV'

    def is_event_file(self):
        """Return whether command is referencing the TUFLOW EVENT FILE."""
        return self.command == 'EVENT FILE'

    def is_quadtree_control_file(self):
        """Return whether command is referencing QUADTREE CONTROL FILE."""
        return self.command == 'QUADTREE CONTROL FILE'

    def is_quadtree_single_level(self):
        """Return whether command is referencing a single level quadtree domain."""
        return self.is_quadtree_control_file() and self.value.upper() == 'SINGLE LEVEL'

    def is_bc_dbase_file(self):
        """Returns whether command is referencing the bc_dbase.csv."""
        return self.command == 'BC DATABASE' or self.command == 'AD BC DATABASE'

    def is_pit_inlet_dbase_file(self):
        """Returns whether command is referecing the pit_inlet_dbase.csv"""
        return self.command and ('PIT INLET DATABASE' in self.command or 'DEPTH DISCHARGE DATABASE' in self.command)

    def is_rainfall_grid(self):
        """Returns whether command is referencing READ GRID RF"""
        return self.is_rainfall_grid_nc() or self.is_rainfall_grid_csv()

    def is_rainfall_grid_csv(self):
        """Returns whether the command is referencing READ GRID RF == CSV"""
        return self.command == 'READ GRID RF' and self.value is not None \
               and TuflowPath(self.value).suffix.upper() == '.CSV'

    def is_rainfall_grid_nc(self):
        """Returns whether the command is referencing READ GRID RF == NC"""
        return self.command == 'READ GRID RF' and self.value_orig is not None \
               and TuflowPath(self.value_orig).suffix.upper() == '.NC'

    def is_prj_file(self):
        return self.is_valid and self.is_read_projection() and TuflowPath(self.value_orig).suffix.upper() == '.PRJ'

    def is_prj_string(self) -> bool:
        """Returns whether command is a PRJ string."""
        return self.is_valid() and ('PROJCS[' in self.value_orig.upper() or 'GEOGCS[' in self.value_orig.upper() or
                                    'PARAMETER[' in self.value_orig.upper())

    def is_read_xf(self):
        return self.is_valid and self.value_orig and TuflowPath(self.value_orig).suffix.upper() in ['.XF4', '.XF8']

    def is_read_swmm_inp(self):
        return self.is_valid and self.value_orig and self.command == 'READ SWMM'

    def is_read_gis(self):
        """Returns whether command is a 'READ GIS' command."""
        return (self.is_valid()
               and ('READ GIS' in self.command or 'CREATE TIN ZPTS' in self.command or 'READ MI' in self.command or
                    'READ MID' in self.command or 'READ ROWCOL' in self.command or 'WRITE GIS' in self.command or self.is_read_projection()) and
                not self.is_mi_prj_string() and not self.is_mi_prj_string() and not self.is_gpkg_proj_string())

    def is_read_grid(self):
        """Returns whether command is a 'READ GRID' command."""
        return self.is_valid() and ('READ GRID' in self.command or self.is_tif_projection()) and self.value_orig is not None \
               and TuflowPath(self.value_orig).suffix.upper() != '.CSV' and 'RF' not in self.command and not self.is_gdal_auth_code()

    def is_read_file(self):
        """Returns whether command is a 'READ FILE' command."""
        return self.command == 'READ FILE'

    def is_read_tin(self):
        """Returns whether command is a 'READ TIN' command."""
        return self.is_valid() and 'READ TIN' in self.command

    def is_log_folder(self):
        """Returns whether command is a 'LOG FILE' command."""
        return self.is_valid() and self.command == 'LOG FOLDER'

    def is_output_folder(self):
        """Returns whether command is a 'OUTPUT FOLDER' command."""
        return self.is_valid() and bool(re.findall(r'(1D\s+)?OUTPUT FOLDER$', self.command))

    def is_check_folder(self):
        """Returns whether command is a 'CHECK FOLDER' command."""
        return self.is_valid() and bool(re.findall(r'(1D\s+)?WRITE CHECK FILES?$', self.command)) and 'OFF' not in self.value_orig

    def check_folder_prefix(self):
        if self.value_orig and self.value_orig[-1] in ['\\', '/']:  # check for trailing slash
            return ''
        elif self.value_orig:  # otherwise value is a check file prefix
            p = Path(str(self.value_orig))
            return p.stem
        return ''

    def set_check_folder_prefix(self, config: TCFConfig | _ParseContext):
        check_file_prefix = self.check_folder_prefix()
        if check_file_prefix:
            if config.control_file.suffix.lower() == '.tcf' and '1D' not in self.command and '1D DOMAIN' not in [x.type for x in sum([], self.define_blocks)]:
                config.check_file_prefix_2d = check_file_prefix
                if config.check_file_prefix_1d:
                    config.check_file_prefix_1d = check_file_prefix
            else:
                config.check_file_prefix_1d = check_file_prefix

    def is_value_a_folder(self):
        return self.is_folder(str(self.value), self.part_count, self.part_index)

    def is_value_a_file(self):
        val = self.value if self.value is not None else self.value_orig
        return self.is_file(str(val), self.part_count, self.part_index)

    def is_mi_prj_string(self):
        return self.command is not None and self.value_orig and self.value_orig.startswith('CoordSys')

    def is_gpkg_proj_string(self):
        return self.command is not None and self.value_orig and self.value_orig.count('|') > 2

    def is_read_projection(self):
        """Returns whether command is a set model projection command."""
        return self.command is not None and 'PROJECTION' in self.command and 'CHECK' not in self.command \
            and (bool(re.findall(r'\.(shp)|(prj)|(mi)|(gpkg)', str(self.value_orig), flags=re.IGNORECASE)) or
                 TuflowPath(self.value_orig).suffix == '' or self.is_mi_prj_string())

    def is_uk_hazard_formula(self):
        return self.command is not None and self.command == 'UK HAZARD FORMULA'

    def is_tif_projection(self):
        return self.command is not None and 'PROJECTION' in self.command and 'TIF' in self.command

    def is_gdal_auth_code(self):
        try:
            return self.command is not None and self.value_orig and self.value_orig.count(':') == 1 and float(self.value_orig.split(':')[1])
        except (ValueError, TypeError, AttributeError):
            return False

    def value_looks_like_gpkg_layer_name(self) -> bool:
        p = TuflowPath(self.value)
        return re.findall(r'^<<.+>>$', str(self.value).strip()) and not p.suffix and len(p.parts) == 1

    def is_value_a_number_3(self):
        """Returns whether the value of the command is a number."""
        return self.is_number(str(self.value), self.part_count, self.part_index)

    def is_value_a_number(self, value=None, iter_index=None):
        """Returns whether the value of the command is a number."""
        if not self.is_valid() or not self.value_orig:
            return False

        if iter_index is None:
            iter_index = self.iter_geom_index

        if value is None:
            value = self.value

        return self.is_value_a_number_2(value, self.value_orig, iter_index)

    @staticmethod
    def is_value_a_number_2(value, value_orig, iter_index):
        if value is None:
            return False
        try:
            if value is not None:
                float(value)
            else:
                float(str(value_orig))
            return True
        except (ValueError, TypeError):
            if iter_index == 1 and re.findall('^<<.+?>>$', value.strip()) and re.findall('<<.+?>>', value)[0] == value.strip():
                return True
            return False

    def return_number(self):
        if '<<' in str(self.value):
            return self.value
        if (self.is_set_code() or self.is_set_mat() or self.is_set_soil() or
                self.is_read_mat() or self.is_read_soil() or self.is_read_code()):
            return int(self.value)
        else:
            return float(self.value)

    def is_value_a_number_tuple(self) -> bool:
        number = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
        var = r'<<.+>>'
        if not self.is_valid() or not self.value:
            return False

        # check if it just matches a number tuple pattern
        if re.match(fr'^{number}(?:(?:[\s\t]+|,[\s\t]*){number})+$', str(self.value).strip()):
            return True

        # check if maybe the value has a variable in it which is stopping the above pattern from matching
        has_var = re.match(fr'^(?:{var}|{number})(?:(?:[\s\t]+|,[\s\t]*)(?:{var}|{number}))+', str(self.value).strip())
        if not has_var:
            return False

        # check if it matches a commnad that expects a number tuple
        if self.is_grid_size() or self.is_route_cutoff_values():
            return True

        return False

    def return_number_tuple(self):
        vals = []
        for x in re.split(r'[\s\t]+|,\s*', str(self.value)):
            if self.is_grid_size_n_m():
                vals.append(int(x) if '<<' not in x else x)
            else:
                vals.append(float(x) if '<<' not in x else x)
        return tuple(vals)

    def is_grid_size(self) -> bool:
        return self.is_valid() and (self.is_grid_size_n_m() or self.is_grid_size_x_y())

    def is_grid_size_n_m(self) -> bool:
        return self.is_valid() and self.command == 'GRID SIZE (N,M)'

    def is_grid_size_x_y(self) -> bool:
        return self.is_valid() and self.command == 'GRID SIZE (X,Y)'

    def is_route_cutoff_values(self) -> bool:
        return self.is_valid() and self.command == 'SET ROUTE CUTOFF VALUES'

    def is_map_output_format(self):
        """
        Returns whether command is READ MAP OUTPUT FORMAT and
        contains any output grids formats that should be converted.
        """
        if self.command == 'MAP OUTPUT FORMAT':
            return re.findall(r'(ASC|FLT|GPKG|TIF|NC)', self.value, flags=re.IGNORECASE)

        return False

    def is_map_output_setting(self):
        """Returns whether command is a setting for a grid map output

        e.g. ASC Map Output Interval
        """
        return 'MAP OUTPUT INTERVAL' in self.command or 'MAP OUTPUT DATA TYPES' in self.command \
               and re.findall(r'(ASC|FLT|GPKG|TIF|NC)', self.command)

    def is_table_link(self):
        """Returns whether READ GIS command is also a Read GIS Table Links command."""
        return self.is_valid() and self.is_read_gis() and 'TABLE LINK' in self.command

    def is_z_shape(self):
        """Returns whether READ GIS command is also a READ GIS Z SHAPE command."""
        return self.is_valid() and self.is_read_gis() \
               and ('Z SHAPE' in self.command or 'Z LINE' in self.command or 'CREATE TIN ZPTS' in self.command)

    def is_2d_zpts(self):
        """Returns whether READ GIS command is also a READ GIS Zpts command."""
        return self.is_valid() and (self.is_read_gis() or self.is_read_grid) \
               and 'ZPTS' in self.command

    def is_modify_conveyance(self):
        """Returns whether READ GIS command is also a READ GIS Zpts Modify Conveyance command."""
        return self.is_2d_zpts() and 'MODIFY CONVEYANCE' in self.command

    def is_2d_lfcsh(self):
        """Returns whether READ GIS command is also a READ GIS LAYERED FC SHAPE command."""
        return self.is_valid() and self.is_read_gis() \
                and 'LAYERED FC SHAPE' in self.command or 'FLC' in self.command

    def is_2d_bc(self, control_file = None):
        """Returns whether READ GIS command is also a 2d READ GIS BC command."""
        if control_file is None:
            control_file = self.config.control_file
        if control_file is None:
            return self.is_valid() and self.is_read_gis() and 'BC' in self.command
        else:
            return self.is_valid() and self.is_read_gis() and 'BC' in self.command and control_file.suffix.upper() == '.TBC'

    def is_set_code(self):
        return self.is_valid() and 'SET CODE' in self.command

    def is_set_mat(self):
        return self.is_valid() and 'SET MAT' in self.command

    def is_set_soil(self):
        return self.is_valid() and 'SET SOIL' in self.command

    def is_read_code(self):
        return self.is_valid() and ('READ GIS CODE' in self.command or 'READ MI CODE' in self.command)

    def is_read_mat(self):
        return self.is_valid() and ('READ GIS MAT' in self.command or 'READ MI MAT' in self.command)

    def is_read_soil(self):
        return self.is_valid() and ('READ GIS SOIL' in self.command or 'READ MI SOIL' in self.command)

    def can_use_multiple_gis_inputs(self, control_file):
        """Returns whether the command can use multiple files on the same line (usually separated by | )."""
        return self.is_z_shape() or self.is_2d_bc(control_file) or self.is_2d_lfcsh() or self.is_2d_zpts()

    def is_gis_format(self):
        """Returns whether command is setting the model GIS FORMAT."""
        return self.command == 'GIS FORMAT'

    def is_grid_format(self):
        """Returns whether command is setting the model GRID FORMAT."""
        return self.command == 'GRID FORMAT' or self.command == 'RF GRID FORMAT'

    def is_read_database(self):
        """Returns whether command is a database command."""
        return self.is_mat_dbase() or self.is_bc_dbase_file() or self.is_rainfall_grid() \
            or self.is_pit_inlet_dbase_file() or self.is_soil_dbase() or self.is_xs_dbase()

    def is_mat_dbase(self):
        """Returns whether command is a Read Material(s) File"""
        return self.is_mat_csv() or self.is_mat_tmf()

    def is_mat_csv(self):
        """Returns whether command is a Read Material(s) File == .CSV"""
        return self.is_valid() and self.value and TuflowPath(self.value).suffix.upper() == '.CSV'\
               and bool(re.findall(r'^READ MATERIALS? FILE', self.command))

    def is_mat_tmf(self):
        """Returns whether command is a Read Material(s) File == .TMF"""
        return self.is_valid() and self.value and TuflowPath(self.value).suffix.upper() != '.CSV'\
               and bool(re.findall(r'^READ MATERIALS? FILE', self.command))

    def is_soil_dbase(self):
        """Returns whether command is a Read Soil(s) File"""
        return self.is_valid() and self.value and TuflowPath(self.value).suffix.upper() == '.TSOILF' \
                  and bool(re.findall(r'^READ SOILS? FILE', self.command))

    def is_xs_dbase(self):
        """Returns whether command is a XS Database command"""
        return self.is_valid() and self.value and 'XS DATABASE' in self.command

    def is_start_define(self):
        """Returns whether command is the start of a define block."""
        return self.is_valid() and bool(re.findall(r'^(DEFINE|(ELSE\s*)?IF|START 1D)', self.command))

    def is_end_define(self):
        if self.is_valid():
            return bool(re.findall(r'^(END DEFINE|END\s*IF|END 1D|ELSE IF)', self.command))

        return False

    def is_else_if(self):
        if self.is_valid():
            return bool(re.findall(r'^(ELSE\s*IF)', self.command))

        return False

    def is_else(self):
        if self.is_valid():
            return bool(re.findall(r'^(ELSE)$', self.command.strip()))

        return False

    def define_start_type(self):
        """Returns the type of block the define block is."""
        if not self.is_valid():
            return None

        if self.command == 'DEFINE EVENT':
            return 'EVENT DEFINE'
        elif re.findall(r'^(DEFINE|(ELSE\s*)?IF)', self.command):
            return re.sub(r'^(DEFINE|(ELSE\s*)?IF)', '', self.command).strip()
        elif self.command == 'START 1D DOMAIN':
            return '1D DOMAIN'
        else:
            return None

    def in_1d_domain_block(self):
        for define_block in self.define_blocks:
            if define_block.type == '1D DOMAIN':
                return True

        return False

    def in_scenario_block(self, scenario_name=None):
        if not self.define_blocks:
            return False

        in_scenario = True
        if isinstance(scenario_name, str):
            scenario_name = [scenario_name]
        for define_block in reversed(self.define_blocks):
            if define_block.type in ['EVENT', 'SCENARIO']:
                if scenario_name is None:
                    return True
                elif not scenario_name:
                    return False
                found = False
                for sn in scenario_name:
                    if not [x.strip().upper() for x in define_block.name.split('|') if x.strip()[0] != '!']:
                        found = True
                        break
                    if sn.upper() in [x.strip().upper() for x in define_block.name.split('|') if x.strip()[0] != '!']:
                        found = True
                        break

                if not found:
                    in_scenario = False

        return in_scenario

    def in_output_zone_block(self, output_zone_name=None):
        for define_block in self.define_blocks:
            if define_block.type == 'OUTPUT ZONE':
                if output_zone_name is None:
                    return True
                if isinstance(output_zone_name, str):
                    if output_zone_name.upper() in [x.strip().upper() for x in define_block.name.split('|')]:
                        return True
                elif isinstance(output_zone_name, list):
                    for sn in output_zone_name:
                        if sn.upper() in [x.strip().upper() for x in define_block.name.split('|')]:
                            return True

        return False

    def is_output_zone(self):
        return self.command and 'MODEL OUTPUT ZONE' in self.command

    def specified_output_zones(self):
        return [x.strip() for x in re.split(r'[\s|]', self.value) if x.strip()]

    def is_set_variable(self):
        return self.is_valid() and 'SET VARIABLE' in self.command

    def parse_variable(self):
        return self.command.split('SET VARIABLE')[1].strip(), self.value

    def is_set_command(self):
        return self.is_valid() and not self.is_set_variable() and re.findall('^SET', self.command)

    def is_event_source(self):
        """Returns whether command is defining the event source."""
        return self.command == 'BC EVENT SOURCE'

    def is_bc_event_name(self) -> bool:
        return self.command == 'BC EVENT NAME'

    def is_bc_event_text(self) -> bool:
        return self.command == 'BC EVENT TEXT'

    def correct_comment_index(self, command):
        """Fix comment index by turning tabs into spaces."""
        tab_len = 4

        command_len = len(command.strip())
        tab_count = command[command_len:].count('\t')
        if tab_count == 0:
            return

        i = command_len
        for c in command[command_len:]:
            if c == ' ':
                i += 1
            elif c == '\t':
                if i % tab_len != 0:
                    i = (int(i / tab_len) + 1) * tab_len
                else:
                    i += tab_len

        self.comment_index = i

    def strip_command(self, text):
        """
        Strip command into components:

        'Command == Value  ! comment  # comment'
        """
        t = text
        c, v, self.comment = None, None, ''
        if t.strip() and not t[0] in ('!', '#'):
            if '!' in t or '#' in t:
                i = t.index('!') if '!' in t else 9e29
                j = t.index('#') if '#' in t else 9e29
                self.comment_index = k = min(i, j)
                t, self.comment = t[:k], t[k:].strip()
                self.correct_comment_index(t)
            if '==' in t:
                c, v = t.split('==', 1)
                v = v.strip()
            else:
                c, v = t, None
            if c.strip():
                self.leading_whitespace = re.split(r'\w', c, flags=re.IGNORECASE)[0]
            c = c.strip(' \n\t|')

        return c, v


class EventCommand(Command):
    """Class for handling commands in the TEF."""

    def __init__(self, line: str, config: TCFConfig | _ParseContext, parent: Path = None, part_index: int = -1):
        super().__init__(line, config, parent, part_index)
        self.event_name = ''

    @staticmethod
    def from_command(command: Command):
        event_cmd = EventCommand(command.original_text, command.config, command.parent)
        event_cmd.define_blocks = command.define_blocks
        for block in command.define_blocks:
            if block.type == 'EVENT DEFINE':
                event_cmd.event_name = block.name
                break
        return event_cmd

    def is_start_define_event(self):
        """Returns whether command is starting a DEFINE EVENT block."""
        return self.command == 'DEFINE EVENT'

    def is_end_define_event(self):
        """Returns whether command is ending a DEFINE EVENT black."""
        return self.command == 'END DEFINE'

    def get_event_source(self):
        """Parse the event source command and return the wildcard and replacement text."""
        if not self.is_valid():
            return None, None

        if not self.is_event_source():
            return None, None

        event_def = [x.strip() for x in str(self.value).split('|', 1)]
        if len(event_def) >= 2:
            return event_def[0], event_def[1]
        elif event_def:
            return event_def[0], None
        else:
            return None, None
