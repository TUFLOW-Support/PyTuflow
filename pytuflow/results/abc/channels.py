from pytuflow.types import PathLike

from .time_series_result_item import TimeSeriesResultItem


class Channels(TimeSeriesResultItem):
    """Abstract base class for channel result item."""

    def __init__(self, fpath: PathLike, *args, **kwargs) -> None:
        """
        Parameters
        ----------
        fpath : PathLike
            Path to the Channel result file.
        """
        super().__init__(fpath)
        #: str: Name or Source of the result item. Always 'Channel'.
        self.name = 'Channel'
        #: str: Domain of the result item. Always '1d'.
        self.domain = '1d'
        #: str: Domain of the result item. Always 'channel'.
        self.domain_2 = 'channel'

    def ds_node(self, id: str) -> str:
        """Return downstream node of channel with ID.

        Parameters
        ----------
        id : str
            Channel ID.

        Returns
        -------
        str
            Downstream node ID.
        """
        return self.df.loc[id, 'DS Node']

    def us_node(self, id: str) -> str:
        """Return upstream node of channel with ID.

        Parameters
        ----------
        id : str
            Channel ID.

        Returns
        -------
        str
            Upstream node ID.
        """
        return self.df.loc[id, 'US Node']

    def downstream_channels(self, id: str) -> list[str]:
        """Return downstream channel of channel with ID.

        Parameters
        ----------
        id : str
            Channel ID.

        Returns
        -------
        str
            Downstream channel ID.
        """
        nd = self.ds_node(id)
        return self.df[self.df['US Node'] == nd].index.tolist()

    def upstream_channels(self, id: str) -> list[str]:
        """Return upstream channel of channel with ID.

        Parameters
        ----------
        id : str
            Channel ID.

        Returns
        -------
        str
            Upstream channel ID.
        """
        nd = self.us_node(id)
        return self.df[self.df['DS Node'] == nd].index.tolist()
