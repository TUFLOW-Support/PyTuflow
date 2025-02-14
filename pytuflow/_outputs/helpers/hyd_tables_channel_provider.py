import io
import re
from typing import TextIO

import numpy as np
import pandas as pd


class HydTablesChannelProvider:
    """Provider class for reading and storing channel data from a TUFLOW 1d_ta_tables check file."""

    def __init__(self):
        #: bool: Whether the provider is finished reading
        self.finished = False
        #: dict: The database of channels
        self.database = {}

    def read_next(self, fo: TextIO):
        """Read the next channel from the open file object. Check the :code:`finished` attribute to see if the provider
        has finished reading.

        Parameters
        ----------
        fo : TextIO
            Open file object to read the channel from.
        """
        buffer = io.StringIO()
        while True:
            marker = fo.tell()
            line = fo.readline()
            if re.findall(r'^Channel', line):
                info = re.split(r'[\[\] ]', line)
                channel_id = info[1].strip()
                cross_sections = re.findall(r'XS\d{5}', line)
                xs1 = cross_sections[0]
                xs2 = None
                if len(cross_sections) > 1:
                    xs2 = cross_sections[1]
                while True:
                    line_ = fo.readline()
                    if line_ == '\n' or not line_ or [x for x in line_.split(',') if x][0] == '\n':
                        break
                    a = line_.split(',')
                    try:
                        float(a[0])
                    except ValueError:
                        if a[0] != '"Bed"' and a[0] != '' and a[0] != '""' and a[0] != '"Inactive"':
                            a[-1] = a[-1].strip()
                            a.append('"Message"\n')
                            line_ = ','.join(a)
                    buffer.write(line_)
                buffer.seek(0)
                self.add_channel_entry(buffer, channel_id)
                return
            elif not line:
                self.finished = True
                return

    def add_channel_entry(self, fo: TextIO, channel_id: str):
        """Add a channel entry to the database.

        Parameters
        ----------
        fo : TextIO
            Open file object containing the channel data.
        channel_id : str
            The channel ID.
        """
        df = pd.read_csv(fo)
        df.columns = df.columns.str.lower()
        df.drop(df.columns[df.columns.str.contains('unnamed')], axis=1, inplace=True)
        if df.message.dtype == np.float64:
            df.message = df.message.astype(str)
            df.message = ''
        df.set_index('elevation', inplace=True)
        df.columns = df.columns.str.split('(', n=1).str[0]
        self.database[channel_id] = df
