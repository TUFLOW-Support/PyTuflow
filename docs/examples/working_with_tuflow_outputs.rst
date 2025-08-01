.. _working_with_tuflow_outputs:

Working with TUFLOW Outputs
===========================

Most of the common TUFLOW outputs are supported by ``pytuflow``. This includes: :class:`TPC<pytuflow.TPC>`,
:class:`XMDF<pytuflow.XMDF>`, and :class:`NCGrid<pytuflow.NCGrid>`. Static, single result outputs such as ``TIF`` and ``ASC``
are not supported as ``pytuflow`` would not offer much more additional functionality over the standard Python libraries.

Output classes all derive from the same base class, and as such, share a common interface. This makes the accessing
data from the outputs consistent and mostly format agnostic. There are some slight differences between a time-series
output, which uses IDs, and a map output, which uses coordinates. However, the method names and usage are the same.

The examples below use models from the `TUFLOW Example Model Dataset <https://wiki.tuflow.com/TUFLOW_Example_Models>`_.

TPC
---

The :class:`TPC<pytuflow.TPC>` class can be loaded by initialising the class with the path to the ``.tpc`` file, or
by using the :meth:`TCF.tpc()<pytuflow.TCF.tpc>` method. The below example uses results from ``EG15_001.tcf``.

.. code-block:: pycon

    >>> from pytuflow import TPC
    >>> tpc = TPC('path/to/results/plot/EG15_001.tpc')

or

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG15_001.tcf')
    >>> tpc = tcf.context().tpc()

Result Information
^^^^^^^^^^^^^^^^^^

Information can be obtained from the results, such as the IDs, result types, and the time steps using
:meth:`TPC.ids()<pytuflow.TPC.ids>`, :meth:`TPC.data_types()<pytuflow.TPC.data_types>`, and
:meth:`TPC.times()<pytuflow.TPC.times>` methods respectively.

.. code-block:: pycon

    >>> tpc.ids()
    ['FC01.1_R.1', 'FC01.1_R.2', 'FC01.2_R.1', ..., 'Pipe8', 'Pipe9']

    >>> tpc.data_types()
    ['water level',
     'mass balance',
     'node flow regime',
     'flow',
     'velocity',
     'channel entry losses',
     'channel additional losses',
     'channel exit losses',
     'channel flow regime']

    >>> tpc.times()
    [0.0, 0.016666666666666666, 0.03333333333333333, ..., 2.9833333333333334, 3.0]

These methods also accept an optionals ``filter_by`` argument, which can be used to filter the return data by
a given domain, geometry, data type, or ID. For example, to get the IDs only for 2D domain (PO) results:

.. code-block:: pycon

    >>> tpc.ids(filter_by='po')
    []

In this case, there are no 2D results in the TPC file, so an empty list is returned. We can also filter by geometry,
and we can conbine the geometry filter with the domain filter:

.. code-block:: pycon

    >>> tpc.ids('1d/line')
    ['FC01.1_R', 'FC01.2_R', 'FC04.1_C', 'Pipe0', 'Pipe1', ..., 'Pit8', 'Pit9']

    >>> tpc.ids('channel')
    ['FC01.1_R', 'FC01.2_R', 'FC04.1_C', 'Pipe0', 'Pipe1', ..., 'Pit8', 'Pit9']

The ``"channel"`` filter is a shorthand for ``"1d/line"`` since channels are only a 1D type. A similar shorthand exists
for ``"1d/point"`` and ``"node"``.

Time-Series
^^^^^^^^^^^

Time-series data can be accessed using the :meth:`TPC.time_series()<pytuflow.TPC.time_series>` method:

.. code-block:: pycon

    >>> tpc.time_series('Pipe1', 'flow')
              channel/flow/Pipe1
    time
    0.000000               0.000
    0.016667               0.009
    0.033333               0.040
    0.050000               0.075
    0.066667               0.106
    ...                      ...
    2.933333               0.000
    2.950000               0.000
    2.966667               0.000
    2.983334               0.000
    3.000000               0.000

Since a given ID could exist in multiple domains, for example, a 1D node, a 2D PO point, and a RL point could all
have the same name (TUFLOW allows this), the return DataFrame header will include the domain, result type, and ID
in the column name.

It's also possible to pass in a list of IDs and/or result types to the :meth:`TPC.timeseries()<pytuflow.TPC.timeseries>`
method to get multiple time-series at once:

.. code-block:: pycon

    >>> tpc.time_series(['Pipe1', 'Pipe2'], ['flow', 'velocity'])
              channel/flow/Pipe1  channel/flow/Pipe2  channel/velocity/Pipe1  channel/velocity/Pipe2
    time
    0.000000               0.000               0.000                   0.000                   0.000
    0.016667               0.009               0.005                   0.510                   0.456
    0.033333               0.040               0.014                   0.740                   0.567
    0.050000               0.075               0.021                   0.875                   0.632
    0.066667               0.106               0.029                   0.966                   0.681
    ...                      ...                 ...                     ...                     ...
    2.933333               0.000               0.000                   0.000                   0.000
    2.950000               0.000               0.000                   0.000                   0.000
    2.966667               0.000               0.000                   0.000                   0.000
    2.983334               0.000               0.000                   0.000                   0.000
    3.000000               0.000               0.000                   0.000                   0.000

Section
^^^^^^^

TPC section data returns a long section from the given channel ID to either the outlet of the connected channels,
or if a second channel ID is provided, to that channel.

.. code-block:: pycon

    >>> tpc.section('Pipe1', 'h', 1.)
        branch_id channel      node  offset        h
    0           0   Pipe1      Pit2     0.0  43.7653
    6           0   Pipe1      Pit3    26.6  43.7654
    1           0  Pipe19      Pit3    26.6  43.7654
    7           0  Pipe19     Pit16    58.3  43.7652
    2           0   Pipe5     Pit16    58.3  43.7652
    8           0   Pipe5     Pit15    94.8  43.7652
    3           0   Pipe6     Pit15    94.8  43.7652
    9           0   Pipe6     Pit14   126.2  43.7654
    4           0  Pipe15     Pit14   126.2  43.7654
    10          0  Pipe15     Pit13   140.0  43.7653
    5           0  Pipe16     Pit13   140.0  43.7653
    11          0  Pipe16  Pipe16.2   212.8  43.7648

In the example above, we use the well known short-hand ``"h"`` for the ``"water level"`` result type. ``pytufow``
accepts well known short-hands for result types, and it's worth nothing that the column name in the returned DataFrame
will be set based on the result type the user provided. For example, in the example above, ``"h"`` is provided and the
column name is set to ``"h"``. If the user provided ``"water level"``, then column would be set to ``"water level"``.
This is also true for the :meth:`TPC.time_series()<pytuflow.TPC.timeseries>`.

A flow trace downstream could branch into multiple channels that go in different directions, the
:meth:`TPC.section()<pytuflow.TPC.section>` method will return data for all branches. The ``branch_id`` column
is used to identify the branch. If the data is used for plotting, the ``branch_id`` can be used to group the data.

XMDF and NCGrid
---------------

The :class:`XMDF<pytuflow.XMDF>` and :class:`NCGrid<pytuflow.NCGrid>` classes are both map output classes and
the methods for accessing the data are identical. Currently the :class:`XMDF<pytuflow.XMDF>` class requires
QGIS Python libraries, which means it needs to be used either inside QGIS, or a QGIS Python environment with QGIS
initialised.

The :class:`NCGrid<pytuflow.NCGrid>` class does not require QGIS, and just requires the ``netCDF`` Python package.
Therefore the :class:`NCGrid<pytuflow.NCGrid>` format is the preferred format for map outputs if you want to use
``pytuflow`` outside of QGIS.

QGIS Environment
^^^^^^^^^^^^^^^^

This section isn't going to go into detail about how to set up a QGIS environment, but it is going to give a broad
overview on how you could set one up.

1. The key to setting up a QGIS Python environment can be copied from the ``bin/python-qgis.bat`` file that can be
   found in the QGIS installation directory. You can can either copy the environment setup from this batch file and
   create your own batch file that uses the same setup and then runs your Python script, or starts your IDE.
   Alternatively, you can copy the Python paths (``sys.path``) and executable path (``sys.executable``) and set them
   up in your IDE Python interpreter settings. The latter is the preferred method, and is possible in most IDEs such
   as PyCharm.
2. The second step, once you have your Python environment setup, is to initialise QGIS in your script, as this
   is required to initialise QGIS' providers.

   .. code-block:: pycon

        >>> from qgis.core import QgsApplication
        >>> qapp = QgsApplication([], False)
        >>> qapp.initQgis()

The alternative is to execute your script from within QGIS, which does not require the above steps. You will
be required to install ``pytuflow``, which can be done either using ``pip`` in the ``OSGeo4W Shell`` or
since QGIS 3.32, you can run shell commands from the Python console using ``!``. For example, to install
``pytuflow`` you can run the following command in the Python console: ``!pip install --upgrade pytuflow``

NCGrid
^^^^^^

The map output examples below will use the :class:`NCGrid<pytuflow.NCGrid>` class, as it is easier to setup in most Python
environments, however, as stated above, the methods are identical for the :class:`XMDF<pytuflow.XMDF>` class.

Similar to the :class:`TPC<pytuflow.TPC>` class, the :class:`NCGrid<pytuflow.NCGrid>` class can be loaded by
initialising the class with the path to the ``.nc`` file. Unlike the :class:`TPC<pytuflow.TPC>` class, the
:class:`TCF<pytuflow.TCF>` class does not have a method to load the ``NCGrid`` automatically. The reason for this, is that
the ``.tpc`` output is always created by TUFLOW, whereas the ``.nc`` output is optional. It is very easy to
obtain the path to the ``.nc`` file from your TUFLOW model. The example below uses results from
``EG00_001.tcf``, which will need to be modified to add the ``"NC"`` map output format.

.. code-block:: pycon

    >>> from pytuflow import TCF, NCGrid
    >>> tcf = TCF('path/to/EG00_001.tcf')
    >>> nc_path = tcf.context().output_folder_2d() / f'{tcf.context().output_name()}.nc'
    >>> ncgrid = NCGrid(nc_path)
    >>> from pytuflow import TCF, NCGrid
    >>> tcf = TCF('path/to/EG00_001.tcf')
    >>> nc_path = tcf.context().output_folder_2d() / f'{tcf.context().output_name()}.nc'
    >>> ncgrid = NCGrid(nc_path)
    >>> from pytuflow import TCF, NCGrid
    >>> tcf = TCF('path/to/EG00_001.tcf')
    >>> nc_path = tcf.context().output_folder_2d() / f'{tcf.context().result_name()}.nc'
    >>> ncgrid = NCGrid(nc_path)

Result Information
""""""""""""""""""

Information, such as result types and time steps, can be obtained using :meth:`NCGrid.data_types()<pytuflow.NCGrid.data_types>`
and :meth:`NCGrid.times()<pytuflow.NCGrid.times>` methods respectively. This information is also possible to get from
the :class:`XMDF<pytuflow.XMDF>` class using the ``netCDF4`` library and does not require QGIS.

.. code-block:: pycon

    >>> ncgrid.data_types()
    ['water level',
     'depth',
     'velocity',
     'z0',
     'max water level',
     'max depth',
     'max velocity',
     'max z0',
     'tmax water level']

    >>> ncgrid.times()
    [0.0, 0.08333333333333333, 0.16666666666666666, ..., 2.9166666666666665, 3.0]

It's possible to filter the return data by whether the result type is ``temporal/static`` and/or ``scalar/vector``.

.. code-block:: pycon

    >>> ncgrid.data_types(filter_by='temporal')
    ['water level', 'depth', 'velocity', 'z0']

    >>> ncgrid.data_types(filter_by='vector')
    ['velocity', 'max velocity']

    >>> ncgrid.data_types(filter_by='static/scalar')
    ['max water level', 'max depth', 'max z0', 'tmax water level']

Time-Series
"""""""""""

The :meth:`NCGrid.timeseries()<pytuflow.NCGrid.timeseries>` method is very similar to the :meth:`TPC.timeseries()<pytuflow.TPC.timeseries>`
method, except that it takes a spatial location (coordinates) instead of an ID. The coordinates can be a
tuple ``(x, y)`` coordinate, a WKT string ``"POINT (x y)"``, a list of the previous two,
or a file path to a GIS point file (e.g. ``.shp``) containing one or more points.

To use a GIS file, the ``GDAL`` Python bindings are required as well as the ``shapely`` Python package. The below examples
use shapefiles, as this is the most common workflow. In the example below, we will use the ``gis\2d_po_EG02_010_P.shp``
file from the TUFLOW example model dataset.

.. code-block:: pycon

    >>> ncgrid.time_series('./gis/2d_po_EG02_010_P.shp', 'water level')
              water level/PO_01  water level/PO_02
    time
    0.000000                NaN          36.500000
    0.083333                NaN          36.483509
    0.166667                NaN          36.457958
    0.250000                NaN          36.441391
    0.333333                NaN          36.431271
    0.416667                NaN          36.426140
    0.500000                NaN          36.423336
    0.583333                NaN          36.421467
    0.666667          40.110428          36.420143
    ...                  ...                   ...
    2.833333          42.804726          38.509300
    2.916667          42.793350          38.429859
    3.000000          42.781895          38.342941

Section
^^^^^^^

The :meth:`NCGrid.section()<pytuflow.NCGrid.section>` extracts a cross-section from the results at a given time,
from a given polyline. The polyline can be a series of coordinates, a WKT string, or a path to a GIS polyline file.

Similar to the time-series method, the ``GDAL`` Python bindings and ``shapely`` package are required to use the GIS file
option. The example below uses the ``gis\2d_po_EG02_010_L.shp`` file from the TUFLOW example model dataset.

.. code-block:: pycon

    >>> ncgrid.section('./gis/2d_po_EG02_010_L.shp', 'water level', 1.)
           offset  water level/PO_01      offset  water level/PO_02
    0    0.000000                NaN    0.000000                NaN
    1    1.327838                NaN    0.432199                NaN
    2    1.327838                NaN    0.432199                NaN
    3    1.491506                NaN    2.957581                NaN
    4    1.491506                NaN    2.957581                NaN
    ..        ...                ...         ...                ...
    291       NaN                NaN  321.155632                NaN
    292       NaN                NaN  321.155632                NaN
    293       NaN                NaN  323.681014                NaN
    294       NaN                NaN  323.681014                NaN
    295       NaN                NaN  325.780984                NaN

Note, that the returned DataFrame does not use a common index, as the section data comes from different polylines.
The printed DataFrame is truncated and does contain valid values within the truncated section. The first PO line ``PO_01``
is shorter than the second PO line ``PO_02``, so the last rows are ``NaN`` for the first PO line.

