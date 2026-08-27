import os
import typing
from pathlib import Path

from .crs import CRS


if typing.TYPE_CHECKING:
    from osgeo import osr


class FmToEstryArgs:
    """Class for collecting and handling command line arguments"""

    def __init__(self, *args):
        self.argv = args
        if self.argv and Path(self.argv[0]).name in ['main.py', 'fm_to_estry.exe']:
            self.argv = self.argv[1:]
        self.argv_lower = [x.lower() for x in self.argv]
        self.nargv = len(self.argv)

    def help(self) -> bool:
        if '-help' in self.argv_lower:
            return True
        if not self.argv:
            return True
        return False

    def out(self, default) ->  Path:
        """
        Return output directory. Order of directory priority:
            1: -out <dir> / -o <dir>
            2: batch file working directory

        :return: None
        """

        self.wkdir = os.getcwd()
        out = None
        if '-o' in self.argv_lower:
            i = self.argv_lower.index('-o')
            if self.nargv > i + 1:
                out = Path(os.getcwd()) / self.argv[i+1]
        if not out:
            if '-out' in self.argv_lower:
                i = self.argv_lower.index('-out')
                if self.nargv > i + 1:
                    out = (Path(os.getcwd()) / self.argv[i+1]).resolve()

        if out is None:
            out = default
        if not Path(out).exists():
            Path(out).mkdir(parents=True)
        return Path(out)

    def log_file(self, output_dir: Path) -> Path:
        """
        Collect logging arguments

        :return: str - full path to log file
        """
        logfile = None
        if '-logfile' in self.argv_lower:
            i = self.argv_lower.index('-logfile')
            if self.nargv > i + 1:
                if not self.argv[i+1][0] == '-':
                    ext = os.path.splitext(self.argv_lower[i + 1])[1]
                    if ext != '.gxy' and ext != '.dat':
                        logfile = (Path(os.getcwd()) / self.argv[i+1]).resolve()
            if logfile is None:
                logfile = output_dir / 'fm_to_estry.log'

        if logfile:
            return Path(logfile)

    def list_unconverted(self, output_dir: Path) -> typing.Union[str, None]:
        unconverted_file = None
        if '-list-unconverted' in self.argv_lower:
            i = self.argv_lower.index('-list-unconverted')
            if self.nargv > i + 1:
                if not self.argv[i+1][0] == '-':
                    ext = os.path.splitext(self.argv_lower[i + 1])[1]
                    if ext != '.gxy' and ext != '.dat':
                        unconverted_file = (Path(os.getcwd()) / self.argv[i + 1]).resolve()
            if unconverted_file is None:
                unconverted_file = output_dir / 'unconverted_files.txt'

        return unconverted_file

    def gxy(self) -> str:
        """
        Collect .gxy file

        :return: str - full path to GXY file
        """
        gxy = None
        exts = [os.path.splitext(x)[1] for x in self.argv_lower]
        if '.gxy' in exts:
            i = exts.index('.gxy')
            gxy = (Path(os.getcwd()) / self.argv[i]).resolve()

        return gxy

    def dat(self) -> str:
        """
        Collect .dat file

        :return: str - full path to dat file
        """
        dat = None
        exts = [os.path.splitext(x)[1] for x in self.argv_lower]
        if '.dat' in exts:
            i = exts.index('.dat')
            dat = (Path(os.getcwd()) / self.argv[i]).resolve()

        return dat

    def crs(self) -> 'osr.SpatialReference':
        """
        Collect crs / projection

        :return: int
        """
        if '-crs' in self.argv_lower:
            i = self.argv_lower.index('-crs')
            if self.nargv > i + 1:
                return CRS(self.argv[i+1]).crs

    def gis_format(self) -> str:
        if '-gpkg' in self.argv_lower:
            return 'GPKG'
        if '-shp' in self.argv_lower:
            return 'SHP'
        if '-mif' in self.argv_lower:
            return 'MIF'
        if '-tab' in self.argv_lower:
            return 'TAB'
        return 'GPKG'

    def check(self) -> bool:
        return '-check' in self.argv_lower or '-raw' in self.argv_lower

    def co(self) -> dict:
        """
        Collect conversion options

        :return: dict
        """
        d = {}
        argv = list(self.argv)
        while argv:
            a = argv.pop(0)
            if a.lower() == '-co':
                if argv:
                    key, val = argv.pop(0).split('=')
                else:
                    raise ValueError('No value for -co argument')
                d[key] = val
        return d

    def loglimit(self) -> int:
        if '-loglimit' in self.argv_lower:
            i = self.argv_lower.index('-loglimit')
            if self.nargv > i + 1:
                return int(self.argv[i+1])
            else:
                raise ValueError('No value for -loglimit argument')
        return -1


if __name__ == '__main__':
    print('This file is not the entry point. Use fm_to_estry.py')