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

- Added Flood Modeller DAT cross-section output class - :class:`DATCrossSections<pytuflow.DATCrossSections>`. This is essentially a wrapper around the :class:`FmCrossSectionDatabaseDriver<pytuflow.FmCrossSectionDatabaseDriver>` class and allows users to interact with Flood Modeller DAT files in an easier way via the ``Output`` class methods - e.g. :meth:`ids()<pytuflow.DATCrossSections.ids>`, :meth:`data_types()<pytuflow.DATCrossSections.data_types>`, :meth:`section()<pytuflow.DATCrossSections.section>`.
- Significant speed up for loading TPC results from a model that contains a lot of channels (in the order of > 500). For example, a test was run on a model that contained approximately 5,000 pipes, and the load time went from 15 seconds to < 1 second.
- Added :attr:`has_reference_time<pytuflow.XMDF.has_reference_time>` property to all output classes. This property holds whether the loaded output contains an explicit reference time. The :attr:`reference_time<pytuflow.XMDF.reference_time>` property will always return a value and as a consequence cannot be used for this purpose.
- Curtain plots will now return a fourth column for vector results that contain the vector projected onto the direction of the input linestring.
- ``direction_of_velocity`` and ``direction_of_unit_flow`` are now recognised as separate scalar datasets. Previously, these would be assumed to be combined with the velocity and unit flow magnitude datasets respectively and then treated as a vector dataset. This change allows the datasets to be treated separately and the available datasets align more closely with what is in the NCGrid format. This also allows users to plot the direction datasets as scalar datasets.
- Calculated offsets in the :meth:`section()<pytuflow.NCMesh.section>` and :meth:`curtain()<pytuflow.NCMesh.curtain>` methods will now return ellipsoid distances if the results are using spherical coordinates.

**Bug Fixes**

- ``"water depth"`` data type is now correctly recognised as ``"depth"`` .
- Max data types now correctly return maximum water surface elevation for 2D results for the :meth:`curtain()<pytuflow.XMDF.curtain>` method.
- Fixed a bug where ``"vector"`` was being removed from the data type ``"vector velocity"`` or ``"max vector velocity"`` when making calls to the plotting methods (:meth:`time_series()<pytuflow.XMDF.time_series>`, :meth:`section()<pytuflow.XMDF.section>` etc). Typically only matters for the :meth:`curtain()<pytuflow.XMDF.curtain>` method where the raw vector data can be used rather than the scalar values.
- Changed the :class:`NCGrid<pytuflow.NCGrid>` return DataFrame column names to be consistent with other output classes. Previously the columns were ``dat_type/name`` and now it is ``name/data_type``.
- ``magnitude_of_velocity`` and are recognised as ``velocity`` (affects :class:`NCGrid<pytuflow.NCGrid>` outputs).
- Fixed a bug for Quadtree results prior to the TUFLOW ``2026.0.0`` release. There was a bug in TUFLOW (fixed in ``2026.0.0``) where Quadtree hardcoded PO geometry types to "R" (region/polygon) in the ``plot/GIS/PLOT.csv`` file. This resulted in a downstream bug in PyTUFLOW when using any geometry filters in methods such as :meth:`data_types()<pytuflow.TPC.data_types>`. PyTUFLOW has been updated to double check the geometry types on load if encountering "R" geometries so results from TUFLOW versions prior to ``2026.0.0`` can still be used.

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
- Fixed a time-series and section plotting for :class:`DAT<pytuflow.DAT>` files which was not working.
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
