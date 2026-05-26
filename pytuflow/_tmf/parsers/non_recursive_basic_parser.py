import dataclasses
import typing
from pathlib import Path

from .block import DefineBlock
from .command import Command, EventCommand

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..settings import TCFConfig, _ParseContext


@dataclasses.dataclass
class _ParseState:
    """Mutable state threaded through the get_commands() loop."""
    define_blocks: list = dataclasses.field(default_factory=list)
    block_names: list = dataclasses.field(default_factory=list)
    block_types: list = dataclasses.field(default_factory=list)
    neg_blocks: list = dataclasses.field(default_factory=list)
    was_end_define: bool = False
    was_else_if: bool = False
    was_else: bool = False
    was_start_define: bool = False


def get_commands(control_file: Path, settings: 'TCFConfig | _ParseContext') -> typing.Generator[Command, None, None]:
    """Parse the control file and yield commands."""
    if not control_file.exists():
        return

    state = _ParseState()

    with control_file.open(errors='surrogateescape') as f:
        for i, line in enumerate(f):
            command = Command(line, settings, line_number=i + 1)
            if state.was_end_define and state.define_blocks:
                state.define_blocks.pop()
                if state.neg_blocks:
                    for _ in range(len(set(state.neg_blocks[-1])) - 1):
                        state.define_blocks.pop()
                state.was_end_define = False
                if state.was_else or not state.was_else_if:
                    state.block_names.pop()
                    state.block_types.pop()
                    state.neg_blocks.pop()
                    state.was_else = False
                    state.was_else_if = False
            if command.is_end_define():
                state.was_end_define = True
                if command.is_else_if():
                    state.was_else_if = True
                else:
                    state.was_else_if = False
            if command.is_start_define():
                if state.was_start_define:  # if consecutive define blocks with no lines in-between - insert dummy command
                    command_ = Command('', settings)
                    command_.define_blocks = state.define_blocks
                    yield command_
                state.was_start_define = True
                define_block_name = command.value
                define_block_type = command.define_start_type()
                state.define_blocks.append(DefineBlock(define_block_type, define_block_name))
                if define_block_name is not None:
                    neg_block_names = ' | '.join([f'!{x.strip()}' for x in define_block_name.split('|')])
                else:
                    neg_block_names = ''
                if command.is_else_if():
                    state.block_names[-1].append(neg_block_names)
                    state.block_types[-1].append(define_block_type)
                    state.neg_blocks[-1].append(neg_block_names)
                else:
                    state.block_names.append([neg_block_names])
                    state.block_types.append([define_block_type])
                    state.neg_blocks.append([neg_block_names])
                if state.was_end_define:
                    define_block = state.define_blocks.pop(-2)
                    state.define_blocks[-1].first_if_written = define_block.first_if_written
                    state.define_blocks[-1].any_if_written = define_block.any_if_written
                    state.was_end_define = False
            else:
                state.was_start_define = False
            if state.define_blocks:
                command.in_define_block = True
                if command.is_else():
                    state.was_else = True
                    block = state.define_blocks.pop()
                    db = [DefineBlock(f'{type_} (ELSE)', name_) for type_, name_ in zip(state.block_types[-1], state.block_names[-1])]
                    for x in db:
                        x.any_if_written = block.any_if_written
                        x.first_if_written = block.first_if_written
                    state.define_blocks.extend(db)
                elif command.is_else_if():
                    block = state.define_blocks.pop()
                    state.define_blocks.extend([DefineBlock(type_, name_) for type_, name_ in zip(state.block_types[-1][:-1], state.block_names[-1][:-1])])
                    state.define_blocks.append(block)
                    state.block_types[-1].pop(0)
                    state.block_names[-1].pop(0)

            command.define_blocks = state.define_blocks
            if command.is_check_folder():
                command.set_check_folder_prefix(settings)

            yield command


def get_event_commands(control_file: Path, settings: 'TCFConfig | _ParseContext') -> typing.Generator[EventCommand, None, None]:
    in_event = False
    event_name = None
    bc_event_text = None
    bc_event_name = None
    event_start_command = None
    for command in get_commands(control_file, settings):
        command = EventCommand.from_command(command)
        if command.is_end_define_event():
            if bc_event_name and bc_event_text:
                cmd = EventCommand(f'BC Event Source == {bc_event_text} | {bc_event_name}', settings)
                cmd.event_name = event_name
                cmd.define_blocks = command.define_blocks
                yield cmd
            in_event = False
            event_name = None
            bc_event_text = None
            bc_event_name = None
            if event_start_command:  # this means the define event block was empty - but we still want to yield for it
                yield event_start_command
                event_start_command = None
        elif in_event:
            command.event_name = event_name
            if command.value:
                event_start_command = None  # don't need this anymore
            if command.is_bc_event_name():
                bc_event_name = command.value
            elif command.is_bc_event_text():
                bc_event_text = command.value
            yield command
        elif command.is_start_define_event():
            in_event = True
            event_name = command.value
            event_start_command = command
        elif command.is_event_source():
            yield command
        elif command.is_bc_event_text() or command.is_bc_event_name():
            raise NotImplementedError('Pytuflow does not support "BC Event Text == " and "BC Event Name == " commands '
                                      'outside "Define Event" blocks within TEF files.')
