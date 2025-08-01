Usage
=====

.. _installation:

Installation
------------

To use pytuflow, first install it using pip:

.. code-block:: console

   $ pip install pytuflow

Dependencies
------------

Most dependencies are automatically installed when you install pytuflow. There are a few additional dependencies
that are not automatically installed, but are very useful as they will extend the functionality of pytuflow. These
are:

- **netCDF4**: This is required for reading any netCDF files, for example, the ``NC`` time-series output format, or
  the ``NC`` map output format. It also allows for reading of the ``XMDF`` header information.
- **GDAL**: This is required for reading GIS files, which extends the :class:`GisInput<pytuflow.GisInput>` class and
  allows the the use of GIS files as locations to extract data from map outputs.
- **shapely**: Needed for extracting section data from map output formats.
- **QGIS**: Currently, QGIS is required for extracting data from :class:`XMDF<pytuflow.XMDF>`, :class:`NCMesh<pytuflow.NCMesh>`,
  and :class:`CATCHJson<pytuflow.CATCHJson>` output formats. We hope to remove this dependency in the future,
  but for now, it is required for these particular output formats. It isn't required for using ``pytuflow`` in general.

One of the trickiest libraries to install is GDAL. For Windows, you can download pre-compiled binaries from
here: https://github.com/cgohlke/geospatial-wheels/releases.

For QGIS, there are some broad instructions on how to setup a :ref:`QGIS Python environment<qgis_environment>` in the output examples.

.. _quickstart:

Quickstart
----------

The best place to get started is the :ref:`tcf_load_and_run` example, or to browse through the other
:ref:`examples`.
