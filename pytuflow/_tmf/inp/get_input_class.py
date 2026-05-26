from . import setting, cf, file, folder, gis, grid, tin, comment, db, inp_build_state, mat, trd

from ..parsers.command import Command


def get_input_class(cmd: Command) -> type[inp_build_state.InputBuildState]:
    if cmd.is_read_gis():
        return gis.GisInput
    elif cmd.is_read_grid():
        return grid.GridInput
    elif cmd.is_read_tin():
        return tin.TinInput
    elif cmd.is_mat_dbase():
        return mat.MatDatabaseInput
    elif cmd.is_read_database():
        return db.DatabaseInput
    elif cmd.is_read_file():
        return trd.TuflowReadFileInput
    elif cmd.is_control_file() and not (cmd.is_quadtree_control_file() and cmd.is_quadtree_single_level()):
        return cf.ControlFileInput
    elif cmd.is_value_a_file():
        return file.FileInput
    elif cmd.is_folder(cmd.value, cmd.part_count, cmd.part_index):
        return folder.FolderInput
    elif cmd.is_valid():
        return setting.SettingInput
    elif cmd.command is None:
        return comment.CommentInput
    raise ValueError('Unknown command type: {}'.format(cmd.command)) from None
