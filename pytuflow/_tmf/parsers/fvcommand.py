from pathlib import Path
import json
import typing
import re

from .command import Command, _ParseContext, EventCommand
from ..settings import TCFConfig
from ..tfpathlib import TuflowPath


FV_CONTROL_FILES = [
    'INCLUDE',
    'EVENT FILE', 'SEDIMENT CONTROL FILE', 'WATER QUALITY CONTROL FILE', 
    'WQ CONTROL FILE', 'PARTICLE TRACKING CONTROL FILE'
]


with (Path(__file__).parent / '..' / 'data' / 'fv_blocks.json').open() as f:
    _FV_BLOCK_TYPES = json.load(f)


class _FVBlockType:

    def __init__(self, block_id: str, block_data: dict):
        self.block_id = block_id
        self.block_data = block_data
        self.command = block_data.get('command', block_id)

    def end_command(self) -> str:
        return self.block_data.get('end command', f'End {self.command.upper() if len(self.command) <= 2 else self.command.title()}')

    def is_correct_end_command(self, end_command: str) -> bool:
        return end_command.upper() == self.end_command().upper()
    
    def get_subblock(self, subblock_command: str) -> '_FVBlockType':
        subblocks = self.block_data.get('subblocks', [])
        for subblock in subblocks:
            data = _get_fv_block(subblock, cf_context='', level='subblock', search_for='id')
            if data.command.upper() == subblock_command.upper():
                return data
        raise KeyError(f'Unknown FV block sub-command {subblock_command} for block {self.command}')


def _get_fv_block(filter_string: str, cf_context: str, level: str, search_for: str = 'command') -> _FVBlockType:
    """search_for: 'command' to match the command string, 'id' to match the block id."""
    if level == 'block':
        block_data_iter = _FV_BLOCK_TYPES[level][cf_context].items()
    elif level == 'subblock':
        block_data_iter = _FV_BLOCK_TYPES[level].items()
    for block_id, block_data in block_data_iter:
        command_str = block_id
        if search_for == 'command':
            command_str = block_data.get('command', block_id)
        if command_str.upper() == filter_string.upper():
            return _FVBlockType(block_id, block_data)
    raise KeyError(f'Unknown FV block command: {filter_string}')


class FVCommand(Command):
    COMMAND_CONTEXT = 'hydrodynamics'

    def __init__(self, line: str, config: TCFConfig | _ParseContext, parent: Path = None, part_index: int = -1, line_number: int = None):
        super().__init__(line, config, parent, part_index, line_number)
        self.fv_blocks = []
        if self.is_wq_control_file() and self.config.wq_model_directories:
            self.reload_value()

    @staticmethod
    def from_command(command: 'Command', cls: type = None) -> 'Command':
        return Command.from_command(command, cls or FVCommand)
    
    def get_water_quality_model_directory(self) -> Path:
        def blocks_are_same(blocks1, blocks2):
            if not blocks1:
                return True
            if not blocks2:
                return False
            if blocks1 == blocks2:
                return True
            return blocks_are_same(blocks1, blocks2[:-1])
        
        def strip_blocks(define_blocks):
            return [x for x in define_blocks if x.type in ['SCENARIO', 'EVENT']]
            
        self_blocks = strip_blocks(self.define_blocks)
        wq_model_directories = sorted(self.config.wq_model_directories, key=lambda cmd: len(strip_blocks(cmd.define_blocks)), reverse=True)
        for cmd in self.config.wq_model_directories:
            if blocks_are_same(strip_blocks(cmd.define_blocks), self_blocks):
                return Path(cmd.value_expanded_path)
        return self.parent.parent
    
    def reload_value(self):
        if not self.is_wq_control_file() or not self.config.wq_model_directories:
            super().reload_value()
            return
        self.value = self.expand(self.value_orig)
        parent = self.get_water_quality_model_directory() / self.parent.name
        self.value_expanded_path = self._expander.expand_path(parent, self)
        self.part_count = self.get_part_count()
    
    def iter_files(self):
        if not self.is_wq_control_file() or not self.config.wq_model_directories:
            yield from super().iter_files()
        else:
            # temporarily override parent property
            parent = self.parent  # save
            self.parent = self.get_water_quality_model_directory() / self.parent.name
            yield from super().iter_files()
            self.parent = parent  # restore
    
    def is_fv_block(self) -> bool:
        """Returns if the command is the start of an FV block, regardless of the specific block type."""
        if not self.is_valid():
            return False
        for _, parent_block_data in _FV_BLOCK_TYPES['block'].items():
            for block_id, block_data in parent_block_data.items():
                command_str = block_data.get('command', block_id)
                if self.command.upper() == command_str.upper():
                    return True
        for _, subblock_data in _FV_BLOCK_TYPES['subblock'].items():
            command_str = subblock_data.get('command', None)
            if command_str and self.command.upper() == command_str.upper():
                return True
        return False
        
    def is_fv_bc_block(self) -> bool:
        if not self.is_valid():
            return False
        try:
            block = _get_fv_block(self.command, self.COMMAND_CONTEXT, level='block')
            return block.block_id == 'bc'
        except KeyError:
            return False
        
    def is_fv_grid_definition_file_block(self) -> bool:
        if not self.is_valid():
            return False
        try:
            block = _get_fv_block(self.command, self.COMMAND_CONTEXT, level='block')
            return block.block_id == 'grid definition file'
        except KeyError:
            return False
        
    def is_end_fv_block(self) -> bool:
        if self.is_valid():
            return self.command.startswith('END') and 'TIME' not in self.command and 'DATE' not in self.command and 'IF' not in self.command
        return False
    
    def get_fv_block(self) -> _FVBlockType:
        if not self.is_fv_block():
            raise ValueError(f'Command {self.command} is not an FV block.')
        if not self.fv_blocks:
            return _get_fv_block(self.command, self.COMMAND_CONTEXT, level='block')
        else:
            parent_block = self.fv_blocks[-1].get_fv_block()
            return parent_block.get_subblock(self.command)
    
    def is_acceptable_block(self) -> bool:
        try:
            _ = self.get_fv_block()
            return True
        except KeyError:
            return False
    
    def is_correct_end_fv_block(self) -> bool:
        if self.is_end_fv_block():
            try:
                parent_block = self.fv_blocks[-1].get_fv_block()
                return parent_block.is_correct_end_command(self.command)
            except KeyError:
                return False
        return False
    
    def get_part_count(self) -> int:
        if self.is_fv_block():
            return self.value.count(',') + 1 if self.value else 0
        return super().get_part_count()
    
    def parts(self) -> typing.Generator['FVCommand', None, None]:
        """Yields parts of the command, splitting by | if present. The yielded Command object will be a copy
        and not be the original Command object."""
        if not self.value_orig:
            return
        
        if not self.is_fv_block():
            for part in super().parts():
                yield FVCommand.from_command(part)
            return
        
        val = self.value if self.value is not None else self.value_orig
        for i, part in enumerate(str(val).split(',')):
            string = f'{self.command_orig} == {part.strip()}'
            cmd = FVCommand(string, self.config, self.parent, i)
            cmd.part_count = self.part_count
            yield cmd

    def is_file(self, text: str, total_parts: int, index: int) -> bool:
        if self.is_fv_block() and self.command == 'BC' and index == 2:
            try:
                float(text)
                return False
            except ValueError:
                return True
        elif self.is_fv_grid_definition_file_block():
            return True
        elif self.is_fv_block():
            return False
        return super().is_file(text, total_parts, index)
    
    def is_number(self, text: str, total_parts: int, index: int) -> bool:
        if self.is_fv_block() and self.command == 'BC' and index == 1:
            return False
        if self.is_fv_block() and self.command == 'BC' and index == 2:
            try:
                float(text)
                return True
            except ValueError:
                return False
        elif self.is_fv_block():
            return False
        if self.is_bc_header():
            return False
        return super().is_number(text, total_parts, index)
    
    def return_number(self):
        if self.is_valid() and self.command == 'NTRACER':
            try:
                return int(self.value)
            except ValueError:
                return self.value
        return super().return_number()
    
    def is_bc_header(self):
        return self.is_valid() and bool(re.findall(r'(?:BC|WQ|SED|TRACE)\s+HEADER', self.command))
    
    def is_control_file(self):
        """Returns whether command is referencing a control file."""
        if self.command and re.findall(r'^READ\s', str(self.command)) and self.command != 'READ FILE':
            cmd = re.sub(r'^READ\s', '', self.command)
        else:
            cmd = self.command
        return cmd in FV_CONTROL_FILES and self.value is not None and TuflowPath(self.value).suffix.upper() != '.CSV'
    
    def is_wq_model_directory(self) -> bool:
        """Returns whether command is referencing a water quality model directory."""
        return self.is_valid() and self.command == 'WATER QUALITY MODEL DIRECTORY'
    
    def is_wq_control_file(self) -> bool:
        """Returns whether command is referencing a water quality control file."""
        return self.is_valid() and self.command == 'WATER QUALITY CONTROL FILE'
    
    def is_include_salinity(self) -> bool:
        return self.is_valid() and self.command == 'INCLUDE SALINITY'
    
    def is_include_temperature(self) -> bool:
        return self.is_valid() and self.command == 'INCLUDE TEMPERATURE'
    
    def is_include_sediment(self) -> bool:
        return self.is_valid() and self.command == 'INCLUDE SEDIMENT'
    
    def is_switched_on(self) -> bool:
        if self.value and self.value.split(',')[0].strip() == '1':
            return True
        elif self.value and self.value.split(',')[0].strip() == '0':
            return False
        return False
    
    def is_folder(self, text: str, total_parts: int, index: int) -> bool:
        return super().is_folder(text, total_parts, index) or self.is_wq_model_directory()
    

class FVSedCommand(FVCommand):
    COMMAND_CONTEXT = 'sediment'

    @staticmethod
    def from_command(command: 'Command', cls: type = None) -> 'Command':
        return Command.from_command(command, cls or FVSedCommand)


class FVPTMCommand(FVCommand):
    COMMAND_CONTEXT = 'particle tracking'
    
    @staticmethod
    def from_command(command: 'Command', cls: type = None) -> 'Command':
        return Command.from_command(command, cls or FVPTMCommand)


class FVWaterQualityCommand(FVCommand):
    COMMAND_CONTEXT = 'water quality'

    @staticmethod
    def from_command(command: 'Command', cls: type = None) -> 'Command':
        return Command.from_command(command, cls or FVWaterQualityCommand)


def get_fv_command(fpath: Path, command: Command) -> FVCommand:
    if fpath.suffix.lower() == '.fvc':
        fv_command = FVCommand.from_command(command)
    elif fpath.suffix.lower() == '.fvsed':
        fv_command = FVSedCommand.from_command(command)
    elif fpath.suffix.lower() == '.fvptm':
        fv_command = FVPTMCommand.from_command(command)
    elif fpath.suffix.lower() == '.fvwq':
        fv_command = FVWaterQualityCommand.from_command(command)
    elif fpath.suffix.lower() == '.tef':
        fv_command = EventCommand.from_command(command)
    else:
        raise ValueError(f'Unsupported control file type {fpath.suffix} for FV command parsing')

    return fv_command
