import sys
from datetime import datetime
from pathlib import Path
import logging

from .helpers.help import help_string
from .helpers.args import FmToEstryArgs
from .helpers.system import set_environment
from .helpers.gis import init_gdal_error_handler
from .helpers.logging import (set_logging_level, FmtoEstryStreamHandler,
                                         FmToEstryFileHandler)
from .helpers.settings import get_fm2estry_settings
from .parsers.dat import DAT
from .parsers.gxy import GXY
from .utils.fm_to_estry import fm_to_estry
from .. import __version__


logger = logging.getLogger('pytuflow')
settings = get_fm2estry_settings()


def main():
    """Main program"""

    # initialise environment and variables
    set_environment()
    init_gdal_error_handler()

    # initialise some settings here
    args = FmToEstryArgs(*sys.argv)
    dat = args.dat()
    gxy = args.gxy()
    settings.dat_fpath_ = dat
    settings.output_dir = args.out(settings.output_dir)

    # logging
    sh = FmtoEstryStreamHandler()
    logger.addHandler(sh)
    fh = None
    if args.log_file(settings.output_dir):
        logfile = args.log_file(settings.output_dir)
        fh = FmToEstryFileHandler(logfile)
        logger.addHandler(fh)
    set_logging_level('INFO')

    logger.info("PyTUFLOW Version: {0}".format(__version__))
    logger.info('Run Date: {0:%Y}-{0:%m}-{0:%d} {0:%H}:{0:%M}\n'.format(datetime.now()))

    if args.help():
        logger.info(help_string())
        input('Press Enter to exit...')
        sys.exit(0)

    # check dat and gxy
    if not dat:
        logger.error('No DAT file specified')
    if not gxy:
        logger.error('No GXY file specified')
    logger.info('DAT: {0}'.format(dat))
    logger.info('GXY: {0}'.format(gxy))
    if fh:
        logger.info('LOG: {0}'.format(logfile))
    if not Path(dat).exists():
        logger.error('DAT file does not exist')
        sh.release_warnings()
        if fh:
            fh.release_warnings(args.loglimit())
        sys.exit(1)
    if not Path(gxy).exists():
        logger.error('GXY file does not exist')
        sh.release_warnings()
        if fh:
            fh.release_warnings(args.loglimit())
        sys.exit(1)

    # settings
    logger.info('\nParsing settings...')
    logger.info('Logging limit set to: {0}'.format(args.loglimit()))
    logger.info('Output for unconverted units: {0}'.format(args.list_unconverted(settings.output_dir)))
    settings.crs = args.crs()
    settings.gis_format = args.gis_format()
    settings.conversion_options(args.co())
    logger.info('Settings:\n{0}'.format(settings))

    def callback(prog: int) -> None:
        term = sh.terminator
        sh.terminator = ''
        if fh:
            fh.terminator = ''
        if prog % 10 == 0:
            logger.info(prog)
        else:
            logger.info('.')
        sh.terminator = term
        if fh:
            fh.terminator = term

    logger.info('\nLoading DAT file...')
    dat = DAT(dat, callback)
    logger.info('\nFinished loading DAT file. Loaded {0} units.'.format(len(dat.units)))
    if sh.held_records:
        logger.info(f'Encountered {len(sh.held_records)} warnings:')
        sh.release_warnings()
        if fh:
            fh.release_warnings(args.loglimit())
    else:
        logger.info('No warnings encountered.')
    logger.info('\nLoading GXY file...')
    logger.info('Reading file...')
    gxy = GXY(gxy, callback=callback, unit_count=len(dat.units))
    logger.info('\nLinking to DAT...')
    dat.add_gxy(gxy)
    logger.info('\nFinished loading GXY file.')
    if sh.held_records:
        logger.info(f'Encountered {len(sh.held_records)} warnings:')
        sh.release_warnings()
        if fh:
            fh.release_warnings(args.loglimit())
    else:
        logger.info('No warnings encountered.')

    if args.check():
        logger.info('\nWriting check files...')
        dat.write_check()
        logger.info('Finished writing check files.')

    logger.info('\nConverting DAT file...')
    nconv = fm_to_estry(dat, args.list_unconverted(settings.output_dir))
    logger.info('\nFinished converting DAT file. Converted {0} units.'.format(nconv))
    if sh.held_records:
        logger.info(f'Encountered {len(sh.held_records)} warnings:')
        sh.release_warnings()
        if fh:
            fh.release_warnings(args.loglimit())
    else:
        logger.info('No warnings encountered.')
    logger.info('\nFinished.')


if __name__ == '__main__':
    main()
