import re
from datetime import datetime, timezone
from pathlib import Path

from .mesh_driver import MeshDriver

try:
    from netCDF4 import Dataset
    has_nc = True
except ImportError:
    has_nc = False
    Dataset = 'Dataset'

try:
    from dateutil import parser
except ImportError:
    parser = 'parser'


class NCMeshDriver(MeshDriver):

    def __init__(self, mesh: Path):
        super().__init__(mesh)
        self.reference_time = datetime(1990, 1, 1, tzinfo=timezone.utc)
        self.valid = False

    @staticmethod
    def parse_reference_time(string):
        if 'hour' in string:
            units = 'h'
        elif 'second' in string:
            units = 's'
        else:
            units = string.split(' ')[0]

        rt_string = string.split('since')[-1].strip() if 'since' in string else string
        if parser != 'parser':
            try:
                rt = parser.parse(rt_string)
                if rt.tzinfo is None:
                    rt = rt.replace(tzinfo=timezone.utc)
                return True, units, rt
            except parser.ParserError:
                pass

        rt = None
        if re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', string):
            rt = datetime.strptime(re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', string)[0],
                                   '%Y-%m-%d %H:%M:%S')
        elif re.findall(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', string):
            rt = datetime.strptime(re.findall(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', string)[0],
                                   '%Y-%m-%dT%H:%M:%S')

        if rt is not None:
            if rt.tzinfo is None:
                rt = rt.replace(tzinfo=timezone.utc)
            return True, units, rt

        return False, units, datetime(1990, 1, 1)  # a default value
