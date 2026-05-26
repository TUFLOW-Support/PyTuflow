import logging
import typing
from pathlib import Path

from ..parsers.dat import DAT
from .output_writer import OutputWriter


logger = logging.getLogger('pytuflow')


def fm_to_estry(dat: DAT, unconverted_fpath: typing.Union[Path, None]) -> int:
    if unconverted_fpath:
        if not unconverted_fpath.parent.exists():
            unconverted_fpath.parent.mkdir(parents=True)
        fo = unconverted_fpath.open('w')
    cnt = 0
    unconverted = 0
    size = len(dat.units)
    dat.reset_progress()
    output_writer = OutputWriter()
    i = -1
    try:
        for i, unit in enumerate(dat.units):
            output = unit.convert()
            output_writer.write(output)
            if unit.converted:
                cnt += 1
            else:
                unconverted += 1
            if not unit.converted and unconverted_fpath:
                fo.write(unit.uid + '\n')
            if dat.callback and size:
                dat._prog_bar.progress_callback(i + 1, size)
    except Exception as e:
        logger.error('Unexpected error occurred that stopped conversion (unit number {0}): {1}'.format(i, e))
    finally:
        output_writer.finalize()
        if unconverted_fpath:
            fo.close()
    return cnt
