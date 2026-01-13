.. pytuflow documentation master file, created by
   sphinx-quickstart on Fri May 17 17:29:22 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to PyTUFLOW's documentation!
====================================

.. image:: assets/TUFLOW_light.png
   :width: 400px
   :class: only-light theme-image

.. image:: assets/TUFLOW_light.png
   :width: 400px
   :class: only-dark theme-image

**PyTUFLOW** is a library that acts as an API for your TUFLOW model. It allows easy interaction with the model results,
contains a number of useful utilities for building TUFLOW models, and contains some useful parsers for files within the
TUFLOW eco-system.

Check out the :doc:`usage` section for further information, including how to :ref:`install <installation>` the project.

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   usage
   api
   examples


Changelog
---------

1.1
"""

Release date: XX XXX 2026

Removed QGIS Dependency Requirement
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

QGIS is no longer required for extracting data from mesh outputs. Prior to ``v1.1``, PyTUFLOW required a QGIS environment to be able to extract data from mesh outputs (e.g. :meth:`XMDF.time_series()<pytuflow.XMDF.time_series>`, :meth:`XMDF.section()<pytuflow.XMDF.section>` etc). In place of QGIS, PyTUFLOW will use `PyVista <https://docs.pyvista.org>`_ for mesh geometry operations and either ``NetCDF4`` or ``h5py`` for extracting the dataset values (``h5py`` is typically a little faster, so it is recommended to install both libraries and PyTUFLOW will use ``h5py`` if it is available).

To install PyVista and h5py:

.. code-block:: bash

    pip install pyvista

.. code-block:: bash

    pip install h5py

This change comes with speed improvements for loading mesh outputs as well as significant speed improvements when extracting data along a linestring (e.g. for :meth:`XMDF.section()<pytuflow.XMDF.section>` and :meth:`XMDF.curtain()<pytuflow.XMDF.curtain>` methods). See the :ref:`Optimised Mesh Outputs<v1.1_optimisations>` section for more detials.

.. _v1.1_optimisations:

Optimised Mesh Outputs
^^^^^^^^^^^^^^^^^^^^^^

New mesh drivers have been added for handling mesh outputs with, or without QGIS. The new drivers are split into two categories which can then be split into either QGIS and non-QGIS drivers (nominally called "Python drivers", although the QGIS drivers use Python bindings, the non-QGIS drivers are just more Python friendly):

1. Drivers for handling mesh geometry (e.g. the ``.2dm``)
2. Drivers for handling mesh results (e.g. the ``.xmdf``)

The geometry and result drivers can be mixed and matched with the exception of the QGIS result driver which requires the QGIS geometry driver. The benefit of mixing the drivers is that Python result drivers don't require the geometry to be loaded for non-spatial related operations (e.g. querying the result types), which makes it faster to initialise the output class and the geometry is only loaded if, and when, it is required.

The best drivers will be chosen automatically based on the available libraries in your Python environment, but it is also possible to specify which drivers to use when initialising the output class. It is recommended to use the Python drivers where possible for speed improvements and to reduce the complexity of the Python environment.

The tables below summarise benchmarking results for the different drivers. The table is for comparison purposes only and the actual times will depend on the model size, computer hardware, and Python environment.

`Note`, "New QGIS Drivers" in the last table refers to optimisations made to the Python code in PyTUFLOW for using QGIS and does not refer to any changes in QGIS itself.

.. csv-table:: Benchmarking dataset and extraction information
  :file: assets/tables/v1.1_benchmarking_specs.csv
  :header-rows: 1

.. csv-table:: Load times (XMDF) - including loading mesh geometry and generating spatial indexing (seconds)
  :file: assets/tables/v1.1_benchmarking_loading.csv
  :header-rows: 1

.. csv-table:: Single data point extraction (seconds)
  :file: assets/tables/v1.1_benchmarking_data_point.csv
  :header-rows: 1

.. csv-table:: Time-series extraction (seconds)
  :file: assets/tables/v1.1_benchmarking_time_series.csv
  :header-rows: 1

.. csv-table:: Section extraction (seconds)
  :file: assets/tables/v1.1_benchmarking_section.csv
  :header-rows: 1

\* Did not finish within 30 minutes.

Minor New Features
^^^^^^^^^^^^^^^^^^

- Added Flood Modeller DAT cross-section output class - :class:`DATCrossSections<pytuflow.DATCrossSections>`. This is essentially a wrapper around the :class:`FmCrossSectionDatabaseDriver<pytuflow.FmCrossSectionDatabaseDriver>` class and allows users to interact with Flood Modeller DAT files in an easier way via the ``Output`` class methods - e.g. :meth:`ids()<pytuflow.DATCrossSections.ids>`, :meth:`data_types()<pytuflow.DATCrossSections.data_types>`, :meth:`section()<pytuflow.DATCrossSections.section>`.
- Significant speed up for loading TPC results from a model that contains a lot of channels (in the order of > 500). For example, a test was run on a model that contained approximately 5,000 pipes, and the load time went from 15 seconds to < 1 second.
- Added :attr:`has_reference_time<pytuflow.XMDF.has_reference_time>` property to all output classes. This property holds whether the loaded output contains an explicit reference time. The :attr:`reference_time<pytuflow.XMDF.reference_time>` property will always return a value and as a consequence cannot be used for this purpose.
- Curtain plots will now return a fourth column for vector results that contain the vector projected onto the direction of the input linestring.
- ``direction_of_velocity`` and ``direction_of_unit_flow`` are now recognised as separate scalar datasets. Previously, these would be assumed to be combined with the velocity and unit flow magnitude datasets respectively and then treated as a vector dataset. This change allows the datasets to be treated separately and the available datasets align more closely with what is in the NCGrid format. This also allows users to plot the direction datasets as scalar datasets.
- Calculated offsets in the :meth:`section()<pytuflow.NCMesh.section>` and :meth:`curtain()<pytuflow.NCMesh.curtain>` methods will now return ellipsoid distances if the results are using spherical coordinates.
- Added :meth:`Mesh.data_point()<pytuflow.XMDF.data_point>` method for extracting a single data point at a given time and location for mesh outputs.

Bug Fixes
^^^^^^^^^

- ``"water depth"`` data type is now correctly recognised as ``"depth"`` .
- Max data types now correctly return maximum water surface elevation for 2D results for the :meth:`curtain()<pytuflow.XMDF.curtain>` method.
- Fixed a bug where ``"vector"`` was being removed from the data type ``"vector velocity"`` or ``"max vector velocity"`` when making calls to the plotting methods (:meth:`time_series()<pytuflow.XMDF.time_series>`, :meth:`section()<pytuflow.XMDF.section>` etc). Typically only matters for the :meth:`curtain()<pytuflow.XMDF.curtain>` method where the raw vector data can be used rather than the scalar values.
- Changed the :class:`NCGrid<pytuflow.NCGrid>` return DataFrame column names to be consistent with other output classes. Previously the columns were ``dat_type/name`` and now it is ``name/data_type``.
- ``magnitude_of_velocity`` and are recognised as ``velocity`` (affects :class:`NCGrid<pytuflow.NCGrid>` outputs).
- Fixed a bug for Quadtree results prior to the TUFLOW ``2026.0.0`` release. There was a bug in TUFLOW (fixed in ``2026.0.0``) where Quadtree hardcoded PO geometry types to "R" (region/polygon) in the ``plot/GIS/PLOT.csv`` file. This resulted in a downstream bug in PyTUFLOW when using any geometry filters in methods such as :meth:`data_types()<pytuflow.TPC.data_types>`. PyTUFLOW has been updated to double check the geometry types on load if encountering "R" geometries so results from TUFLOW versions prior to ``2026.0.0`` can still be used.
- Fixed a bug for :class:`GPKG2D<pytuflow.GPKG2D>` and :class:`GPKGRL<pytuflow.GPKGRL>` classes where using a ``"polygon"`` filter in either the :meth:`data_types()<pytuflow.GPKG2D.data_types>` or :meth:`ids()<pytuflow.GPKG2D.ids>` methods would return an empty list even if there were PO or RL polygons in the results.
- Fixed a bug for :meth:`section()<pytuflow.XMDF.section>` and :meth:`curtain()<pytuflow.XMDF.curtain>` methods for Quadtree results when the line intersected transition zones which could cause additional points to be added to the resulting DataFrame with ``NaN`` values.

1.0.3
"""""

Release date: 13 Jan 2026

- Fixed a bug when reading a TCF file and the command ``Write Check Files ==`` was used and the file path did not have a trailing slash. Previously, this could cause a Python error.


1.0.2
"""""

Release date: 16 Dec 2025

- Fixed a bug where a ``"timeseries"`` filter would return an empty list when using the :meth:`data_types()<pytuflow.GPKG2D.data_types>` or :meth:`ids()<pytuflow.GPKG2D.ids>` methods on :class:`GPKG2D<pytuflow.GPKG2D>` and :class:`GPKGRL<pytuflow.GPKGRL>` classes.
- Added a timezone to the :class:`NCGrid<pytuflow.NCGrid>` reference time.
- Added a timezone to the :class:`NCMesh<pytuflow.NCMesh>` reference time.
- Fixed a bug where outputs that had an uneven output times would result in the output time units being interpreted incorrectly e.g. a 300 second timestep would be output as a 300 hr timestep.
- Fixed a bug when trying to load a TUFLOW cross-section database from a GPKG.
- Fixed a bug for :class:`NCGrid<pytuflow.NCGrid>` where ``"3d"`` filters would cause a Python error.
- :class:`CrossSections<pytuflow.CrossSections>` output class now handles file not found errors more gracefully, such that the output is still loaded even if a cross-section file is missing.
- Fixed a bug for :class:`CrossSections<pytuflow.CrossSections>` outputs where the cross sections were being reloaded each time the :meth:`section()<pytuflow.CrossSections.section>` method was called.
- Fixed a bug where ``"na"`` types for :class:`CrossSections<pytuflow.CrossSections>` outputs were not returning any results when using the :meth:`section()<pytuflow.CrossSections.section>` method.
- Fixed a bug for ESTRY GPKG Time Series outputs where the ``"pipes"`` data type was incorrectly outputting a pipe at each channel.
- Fixed a bug with the :class:`BCTablesCheck<pytuflow.BCTablesCheck>` output class where it would return an empty list if ``filter_by`` was set to ``"timeseries"``.
- Fixed a bug with the :class:`HydTablesCheck<pytuflow.HydTablesCheck>` output class where it would return an empty list if ``filter_by`` was set to ``"section"``.
- Fixed a bug where if there was a trailing or leading "/" in the ``filter_by`` argument in the :meth:`data_types()<pytuflow.TPC.data_types>` :meth:`ids()<pytuflow.TPC.ids>`, and :meth:`times()<pytuflow.TPC.times>` methods, then an empty return was almost guaranteed.
- Fixed a bug in when asking for the ``"wetted perimeter"`` data type in the :meth:`HydTablesCheck.section()<pytuflow.HydTablesCheck.section>` output class would cause a python exception.
- Added proper format checking for SMS :class:`DAT<pytuflow.DAT>` files.
- Fixed a bug when loading a :class:`DAT<pytuflow.DAT>` file (not from the ``.sup``) where the file path attribute :attr:`fpath<pytuflow.DAT.fpath>` was being being set incorrectly.
- Fixed time-series and section plotting for :class:`DAT<pytuflow.DAT>` files which was not working.
- Added the missing format checker for the :class:`CATCHJson<pytuflow.CATCHJson>` class.
- Added :attr:`fpath<pytuflow.CATCHJson.fpath>` property to :class:`CATCHJson<pytuflow.CATCHJson>` class to be consistent with other output classes.
- Added a timezone to the :class:`CATCHJson<pytuflow.CATCHJson>` :attr:`reference_time<pytuflow.CATCHJson.reference_time>`.
- Removed ``WARNING  Invalid data type:`` that was triggered incorrectly in :class:`CATCHJson<pytuflow.CATCHJson>` if the data type was not in one of the result files but it was present in another.
- Added timezone information to :class:`FVBCTide<pytuflow.FVBCTide>` output class.
- Fixed a bug where ``UK Hazard Formula ==`` commands were seen as files and were then flagged as having missing files.
- Fixed a bug where ``MI Projection == Coord ...`` commands were seen as files and were then flagged as having missing files.
- Fixed a bug with :meth:`GPKG1D.section()<pytuflow.GPKG1D.section>` method when connecting two pipes and the ``"pits"`` data type was requested for ESTRY GPKG 1D outputs.
- Fixed generic Python warnings that were being triggered in various places in the code, in particular warning regarding ``return`` statements in ``finally`` blocks.

1.0.1
"""""

Release date: 10 Oct 2025

- Fixed a bug that would incorrectly flag ``1d_nwk`` ``Q`` channel curve references (the reference to the pit database name) as files and then flag the file as missing.
- Fixed a bug for 1D results where if the ``"section/3d"`` filter was passed into the :meth:`data_types()<pytuflow.TPC.data_types>` or :meth:`ids()<pytuflow.TPC.ids>` methods, the return value would incorrectly return populated lists. The return is now an empty list since 1D results do not have any 3D results.

1.0.0
"""""

Release date: 6 Oct 2025

First full release of PyTUFLOW.


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
