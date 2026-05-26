import logging
import json
import os
import re
import typing
from pathlib import Path

from ..parsers.command import Command
from ..gis import ogr_format, get_database_name, gdal_format, GisFormat
from ..tfpathlib import TuflowPath



logger = logging.getLogger('pytuflow')


def _command_type(fpath: str | Path) -> str:
    type_ = 'setting'
    if re.findall('^[012]d_', TuflowPath(fpath).lyrname, re.IGNORECASE):
        type_ = 'gis'
    elif TuflowPath(fpath).suffix.lower() in ['.asc', '.flt', '.tif', '.gpkg' '.nc', '.txt', '.tiff', '.gtif',
                                              '.gtiff', '.tif8', '.tiff8', '.bigtif', '.bigtiff']:
        type_ = 'grid'
    elif TuflowPath(fpath).suffix.lower() in ['.12da', '.xml']:
        type_ = 'tin'
    return type_


def build_gis_commands_from_file(fpaths: list[str], ref_cf: Path = None, spatial_db: Path = None) -> list[str]:
    """Build TUFLOW GIS commands from GIS file(s) and return a list of TUFLOW command strings.
    Similar to :func:`build_tuflow_command_string`, but can build multiple command strings but does not allow
    for the addition of numbers to the command string.

    Parameters
    ----------
    fpaths : list[str]
        A list of GIS file paths (as strings) to build the TUFLOW command from.
    ref_cf : Path, optional
        A reference control file (does not need to exist) to use when building the command. The control file
        is used to generate a relative reference for GIS file commands. If not provided, the routine will search
        nearby directories for the location of relevant control files, otherwise it will assume a standard relative
        path reference.
    spatial_db : Path, optional
        A spatial database file path that will be used when building GPKG commands. If it is provided and is the same
        as the GIS file reference, the command string will use the GPKG layer name only.

    Returns
    -------
    list[str]
        A list of TUFLOW command strings.
    """
    i = -1
    command_str = ''
    fpaths_ = fpaths.copy()
    while fpaths_:
        fpath = fpaths_.pop(0)
        if not fpath:
            continue
        i += 1

        type_ = _command_type(fpath)
        if type_ == 'setting':
            raise ValueError('Cannot build GIS commands from a setting command: {0}'.format(fpath))
        left, cf = guess_command_from_text(TuflowPath(fpath).lyrname, type_)
        if not left:
            logger.error('Could not guess command from text: {}'.format(fpath))
            raise ValueError('Could not guess command from text')

        ref_cf_ = ref_cf if ref_cf is not None else try_find_control_file(TuflowPath(fpath), cf)

        command = TuflowCommand(ref_cf_, fpath, spatial_db)
        command.command_left = left
        while fpaths_:
            fpath = fpaths_[0]
            if not fpath:
                fpaths_.pop(0)
                continue
            ref_cf_ = ref_cf if ref_cf is not None else try_find_control_file(TuflowPath(fpath), cf)
            if command.append(ref_cf_, fpath, spatial_db):
                fpaths_.pop(0)
            else:
                break
        if i == 0:
            command_str = command.command
        else:
            command_str = '{0}\n{1}'.format(command_str, command.command)
    return command_str.split('\n')


def build_tuflow_command_string(input_text: str | list[str], ref_cf: Path = None,
                                spatial_db: Path = None) -> str:
    """Build a single line TUFLOW command string from input_text. Useful for generating GIS commands from a GIS file(s).
    If input_text is a list, it must be a list of (at least one) GIS files and numbers. If input_text is a string,
    it must be a TUFLOW command or a single string file path to a GIS file.

    Similar to :func:`build_gis_commands_from_file`, but assumes input text makes up a single command string which
    allows for the addition of numbers to the command string. It also allows for non-GIS commands to be passed in.

    As an example, a list of GIS Z shape layers will produce single TUFLOW command string referencing the Z shape
    layers. Another example, if a layer is passed in with a number, the number will be appended to the command string.

    Example

    ::


        >>> build_tuflow_command_string(["C:/TUFLOW/model/2d_zsh_EG00_001_L.shp", r"C:/TUFLOW/model/2d_zsh_EG00_001_P.shp"])
        'Read GIS Z Shape == ..\\model\\2d_zsh_EG00_001_L.shp | ..\\model\\2d_zsh_EG00_001_P.shp\\n'

        >>> build_tuflow_command_string(["C:/TUFLOW/model/gis/2d_mat_EG00_001_R.shp", 2])
        'Read GIS Mat == ..\\gis\\2d_mat_EG00_001_R.shp | 2\\n'

    Parameters
    ----------
    input_text : str or list[str]
        A string or list of strings to build the TUFLOW command from. The string can be a TUFLOW command, a GIS file path,
        or a list of GIS file paths and numbers.
    ref_cf : Path, optional
        A reference control file (does not need to exist) to use when building the command. The control file
        is used to generate a relative reference for GIS file commands. If not provided, the routine will search
        nearby directories for the location of relevant control files, otherwise it will assume a standard relative
        path reference.
    spatial_db : Path, optional
        A spatial database file path that will be used when building GPKG commands. If it is provided and is the same
        as the GIS file reference, the command string will use the GPKG layer name only.

    Returns
    -------
    str
        A single line TUFLOW command string.
    """
    from ..settings import TCFConfig
    command = Command('', TCFConfig())

    cmd = None
    if isinstance(input_text, str):
        if not input_text.strip():
            return input_text
        if '!' in input_text and not input_text.split('!')[0].strip():
            return input_text
        if '==' not in input_text and not Path(input_text).suffix:
            return input_text

    cf = 'tcf'
    if isinstance(input_text, list) or ' == ' not in input_text:
        if isinstance(input_text, list):
            text = input_text[0]
        else:
            text = input_text

        type_ = _command_type(text)
        if isinstance(input_text, list) and input_text:
            left, cf = guess_command_from_text(TuflowPath(input_text[0]).lyrname, type_)
        else:
            left, cf = guess_command_from_text(TuflowPath(input_text).lyrname, type_)
        if not left:
            logger.error('Could not guess command from text: {}'.format(text))
            raise ValueError('Could not guess command from text')
    else:
        cmd = Command(input_text, command.config)
        left, right = cmd.command_orig, cmd.value_orig
        input_text = [x.strip() for x in right.split('|')]
        text = input_text[0]
        if len(input_text) == 1:
            input_text = input_text[0]

    settings = command.config
    if ref_cf:
        settings.control_file = ref_cf
    else:
        settings.control_file = try_find_control_file(TuflowPath(text), cf)
    if spatial_db:
        settings.spatial_database = spatial_db
    input_text = concat_command_values(TuflowPath(settings.control_file), input_text, TuflowPath(settings.spatial_database))
    input_text = f'{left} == {input_text}'
    if cmd:
        input_text = cmd.re_add_comments(input_text, rel_gap=True)

    if input_text and input_text[-1] != '\n':
        input_text = f'{input_text}\n'

    return input_text


def guess_command_from_text(text: str, cmd_type: str) -> tuple[str, str]:
    """Guess the TUFLOW command and control file type from some text and given a type. Only works for GIS/GRID/TIN
    commands.

    e.g.

    ::


        >>> guess_command_from_text('2d_zsh_EG00_001_L.shp', 'gis')
        ('Read GIS Z Shape', 'TCF')

        >>> guess_command_from_text('elevation.tif', 'grid')
        ('Read Grid Zpts', 'TCF')

    Parameters
    ----------
    text : str
        The text to guess the command from.
    cmd_type : str
        The type of command to guess from. Can be one of 'gis', 'grid', or 'tin'.

    Returns
    -------
    tuple[str, str]
        The guessed command and control file type.
    """
    json_file = TuflowPath(__file__).parent.parent.parent / 'data' / 'command_db.json'
    with json_file.open() as f:
        data = json.load(f)
        if cmd_type:
            data = data.get(cmd_type)
            if not data:
                return '', ''
        if isinstance(data, str):
            return data, ''
        for key, value in data.items():
            if key.lower() in text.lower():
                return value['cmd'], value['cf']
    return '', ''


def try_find_control_file(file: Path, cf: str) -> Path:
    """Given a file path and control file type, try and find the control file within the nearby directories.
    If the control file cannot be found, a dummy control file will be returned with the name :code:`__dummy__.tcf`
    (the extension will match the control file type).

    Parameters
    ----------
    file : Path
        The file path to search from.
    cf : str
        The control file type to search for. Can be one of 'TCF', 'ECF', 'TGC', 'TBC', etc.

    Returns
    -------
    Path
        The control file path.
    """
    if 'tuflow control file' in cf.lower():
        ext = '.tcf'
    elif 'estry control file' in cf.lower():
        ext = '.ecf'
    elif 'geometry control file' in cf.lower():
        ext = '.tgc'
    elif 'bc control file' in cf.lower():
        ext = '.tbc'
    elif re.findall(r'\(.*\)', cf):
        ext = re.findall(r'\(.*\)', cf)[0].strip('()')
    else:
        ext = f'.{cf.lower()}'
    tf_dir = find_parent_dir(file, 'tuflow')
    model_dir = find_parent_dir(file, 'model')
    if tf_dir and model_dir:
        if len(model_dir.parts) - len(tf_dir.parts) > 3 or len(tf_dir.parts) <= 2:
            root = model_dir.parent
        else:
            root = tf_dir
    elif model_dir:
        root = model_dir.parent
    elif tf_dir:
        root = tf_dir
    else:
        root = file.parent.parent.parent
        if ext == '.tcf':
            return root / 'runs' / '__dummy__.tcf'
        else:
            return root / 'model' / '__dummy__{0}'.format(ext)
    matching_file = find_highest_matching_file(root, '*{0}'.format(ext))
    if matching_file:
        return matching_file
    else:
        if ext == '.tcf':
            return root / 'runs' / '__dummy__.tcf'
        else:
            return root / 'model' / '__dummy__{0}'.format(ext)


def find_parent_dir(start_loc: str | Path, dir_name: str, max_levels: int = -1) -> Path:
    start_loc: Path = Path(start_loc)
    nparts = len(start_loc.parts)
    if max_levels == -1 and dir_name.lower() in [x.lower() for x in start_loc.parts]:
        for i, part in enumerate(reversed(start_loc.parts)):
            if part.lower() == dir_name.lower():
                return Path(os.path.join('', *start_loc.parts[:nparts - i]))
    elif dir_name.lower() in [x.lower() for x in start_loc.parts[nparts-max_levels:]]:
        for i, part in enumerate(reversed(start_loc.parts)):
            if part.lower() == dir_name.lower():
                return Path(os.path.join('', *start_loc.parts[:nparts - i]))
    raise ValueError('Could not determine parent directory for {0} in {1}'.format(dir_name, start_loc))


def find_highest_matching_file(start_loc: typing.Union[str, Path], pattern: str) -> Path | None:
    start_loc = Path(start_loc)
    if len(start_loc.parts) < 3:
        return None
    files = [file for file in start_loc.glob('**/{0}'.format(pattern))]
    if files:
        nparts = 1000
        chosen_file = None
        for file in files:
            if len(file.parts) < nparts:
                nparts = len(file.parts)
                chosen_file = file
        return chosen_file
    return None


def concat_command_values(control_file: 'TuflowPath', values: list[str], spatial_database: 'TuflowPath') -> str:
    # noinspection PyUnreachableCode
    if not isinstance(values, list):
        values = [values]
    if not values:
        return ''

    tf_cmd = TuflowCommand(control_file, values[0], spatial_database)
    if not tf_cmd:
        return ' | '.join(values)
    if len(values) > 1:
        for value in values[1:]:
            tf_cmd.append(control_file, value, spatial_database)
    return tf_cmd.command_right


class TuflowCommand:

    def __new__(cls, control_file, fpath, spatial_database):
        if not isinstance(fpath, (int, float)):
            fpath = TuflowPath(fpath)

        try:
            fmt = ogr_format(fpath)
        except (ValueError, RuntimeError, FileNotFoundError):
            try:
                fmt = gdal_format(fpath)
            except (ValueError, RuntimeError, FileNotFoundError):
                if fpath.is_file():
                    fmt = 'TIN'
                    logger.warning('MinorConvertException: Format assumed to be "TIN"')
                else:
                    fmt = None
                    logger.warning('MinorConvertException: Format unknown')
        except TypeError:
            fmt = 'NUMBER'

        if fmt == GisFormat.GPKG:
            cls = TuflowCommandGPKG
        elif fmt == GisFormat.SHP:
            cls = TuflowCommandSHP
        elif fmt == GisFormat.MIF:
            cls = TuflowCommandMapinfo
        elif fmt == 'NUMBER':
            cls = TuflowCommandNumber
        elif fmt in [GisFormat.TIF, GisFormat.ASC, GisFormat.FLT, GisFormat.NC]:
            cls = TuflowCommandRaster
        elif fmt == 'TIN':
            cls = TuflowCommandTin
        else:
            raise ValueError('Unknown TUFLOW command type for file: {0}'.format(fpath))
        return super().__new__(cls)

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, self.name)

    def __init__(self, control_file, fpath, spatial_database) -> None:
        self.valid = False
        self._left = ''
        self.ds = fpath
        self.file, self.name = get_database_name(self.ds)
        self.file = TuflowPath(self.file)
        self.cf = control_file
        self.spatial_database = spatial_database
        self.valid = self.cf is not None

    @property
    def command(self) -> str:
        if self.valid:
            return '{0} == {1}'.format(self.command_left, self.command_right)
        return ''

    @property
    def command_right(self) -> str:
        if self.valid:
            if self.cf.stem == '__dummy__':
                relpath = r'..\model\{0}'.format(self.file.name) if self.cf.suffix == '.tcf' else r'gis\{0}'.format(self.file.name)
            else:
                relpath = os.path.relpath(self.file, str(self.cf.parent))
            return '{0}'.format(relpath)
        return ''

    @property
    def command_left(self) -> str:
        if self.valid:
            return self._left
        return ''

    @command_left.setter
    def command_left(self, value: str):
        self._left = value

    def append(self, control_file, ds, spatial_database) -> bool:
        return False


class TuflowCommandMapinfo(TuflowCommand):
    pass


class TuflowCommandRaster(TuflowCommand):
    pass


class TuflowCommandTin(TuflowCommand):
    pass


class TuflowCommandNumber(TuflowCommand):

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, self.ds)

    def __init__(self, control_file, fpath, spatial_database):
        super().__init__(control_file, fpath, spatial_database)
        self.ds = fpath
        self.valid = True

    @property
    def command_right(self) -> str:
        return str(self.ds)


class TuflowCommandSHP(TuflowCommand):

    def __init__(self, control_file, fpath, spatial_database) -> None:
        super().__init__(control_file, fpath, spatial_database)
        self._in_right = False
        self.commands = []
        self.commands.append(self)

    def appendable(self, command: 'TuflowCommand') -> bool:
        appendable_types = ['2d_zsh', '2d_bc', '2d_ztin', '2d_vzsh', '2d_bg', '2d_lfcsh']
        for a in appendable_types:
            if a.lower() in self.name.lower() and a.lower() in command.name.lower():
                return True
        return False

    def append(self, control_file, ds, spatial_database) -> bool:
        command = TuflowCommand(control_file, ds, spatial_database)
        if self.valid and command.valid and self.appendable(command):
            if len(self.commands) > 1 and type(command) != type(self):
                for c in self.commands:
                    if type(c) == type(command):
                        c.commands.append(command)
                        return True
            self.commands.append(command)
            return True
        return False

    def command_iter(self) -> typing.Generator['TuflowCommand', None, None]:
        for command in self.commands:
            yield command

    @property
    def command_right(self) -> str:
        if self.valid:
            if len(self.commands) == 1 or self._in_right:
                return super().command_right
            self._in_right = True
            rhs = ' | '.join([x.command_right for x in self.command_iter()])
            self._in_right = False
            return rhs
        return ''


class TuflowCommandGPKG(TuflowCommandSHP):

    def __init__(self, control_file, fpath, spatial_database) -> None:
        super().__init__(control_file, fpath, spatial_database)
        self.type = 'name' if TuflowPath(self.file) == TuflowPath(spatial_database) else 'path'

    @property
    def command_right(self) -> str:
        if self.valid and self.type == 'name':
            return ' | '.join([x.name for x in self.command_iter()])
        if self.valid and len(self.commands) == 1 and self.file.stem.lower() == self.name.lower():
            return super().command_right
        dbs = [x for x, y in self.db_iter()]
        if self.valid and len(dbs) == 1:
            return '{0} >> {1}'.format(TuflowCommand.command_right.fget(self), ' && '.join([x.name for x in self.command_iter()]))
        elif self.valid:
            commands = []
            for db, command in self.db_iter():
                relpath = os.path.relpath(db, str(command.cf.parent))
                if isinstance(command, TuflowCommandGPKG):
                    c = '{0} >> {1}'.format(relpath, ' && '.join(self.names(db)))
                else:
                    c = TuflowCommandSHP.command_right.fget(command)
                commands.append(c)
            return ' | '.join(commands)
        return ''

    def db_iter(self):
        db = []
        for command in self.command_iter():
            if command.file not in db:
                db.append(command.file)
                yield command.file, command

    def names(self, db) -> typing.List[str]:
        return [x.name for x in self.command_iter() if x.file == db]
