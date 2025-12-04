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

- Added Flood Modeller DAT cross-section output class. This is essentially a wrapper around the ``FmCrossSectionDatabaseDriver`` class and allows users to interact with Flood Modeller DAT files in an easier way via the ``Output`` class methods - e.g. ``ids()``, ``data_types()``, ``section()``.
- Significant speed up for loading TPC results from a model that contains a lot of channels (in the order of > 500). For example, a test was run on a model that contained approximately 5,000 pipes, and the load time went from 15 seconds to < 1 second.
- Added ``has_reference_time`` property to all output classes. This property holds whether the loaded output contains an explicit reference time. The ``reference_time`` property will always return a value and as a consequence cannot be used for this purpose.
- Curtain plots will now return a fourth column for vector results that contain the vector projected onto the direction of the input linestring.
- ``direction_of_velocity`` and ``direction_of_unit_flow`` are now recognised as separate scalar datasets. Previously, these would be assumed to be combined with the velocity and unit flow magnitude datasets respectively and then treated as a vector dataset. This change allows the datasets to be treated separately and the available datasets align more closely with what is in the NCGrid format. This also allows users to plot the direction datasets as scalar datasets.

**Bug Fixes**

- ``"water depth"`` data type is now correctly recognised as ``"depth"`` .
- Max data types now correctly return maximum water surface elevation for 2D results for the ``curtain()`` method.
- Fixed a bug where ``"vector"`` was being removed from the data type ``"vector velocity"`` or ``"max vector velocity"`` when making calls to the plotting methods (``time_series()``, ``section()`` etc). Typically only matters for the ``curtain()`` method where the raw vector data can be used rather than the scalar values.
- Changed the ``NCGrid`` return DataFrame column names to be consistent with other output classes. Previously the columns were ``dat_type/name`` and now it is ``name/data_type``.
- ``magnitude_of_velocity`` and are recognised as ``velocity`` (affects ``NCGrid`` outputs).
- Fixed a bug for Quadtree results prior to the TUFLOW ``2026.0.0`` release. There was a bug in TUFLOW (fixed in ``2026.0.0``) where Quadtree hardcoded PO geometry types to "R" (region/polygon) in the ``plot/GIS/PLOT.csv`` file. This resulted in a downstream bug in PyTUFLOW when using any geometry filters in methods such as ``data_types()``. PyTUFLOW has been updated to double check the geometry types on load if encountering "R" geometries so results from TUFLOW versions prior to ``2026.0.0`` can still be used.

1.0.2
"""""

- Fixed a bug where a ``"timeseries"`` filter would return an empty list when using the ``data_types()`` or ``ids()`` methods on ``GPKG2D`` and ``GPKGRL`` classes.
- Added a timezone to the ``NCGrid`` reference time.
- Added a timezone to the ``NCMesh`` reference time.
- Fixed a bug where outputs that had an uneven output times would result in the output time units being interpreted incorrectly e.g. 300 second timestep would be output as 300 hr timestep.
- Fixed a bug when trying to load a TUFLOW cross-section database from a GPKG.
- Fixed a bug for ``NCGrid`` where ``3d`` filters would cause a Python error.
- ``CrossSection`` output class now handles file not found errors more gracefully, such that the output is still loaded even if a cross-section file is missing.
- Fixed a bug for ``CrossSection`` outputs where the cross sections were being reloaded each time the ``section()`` method was called.
- Fixed a bug where ``na`` types for ``CrossSection`` outputs were not returning any results when using the ``section()`` method.
- Fixed a bug for ESTRY GPKG Time Series outputs where the ``"pipes"`` data type was incorrectly outputting a pipe at each channel.
- Fixed a bug with the ``BCTablesCheck`` output class where it would return an empty list if ``filter_by`` was set to ``"timeseries"``.
- Fixed a bug with the ``HydTablesCheck`` output class where it would return an empty list if ``filter_by`` was set to ``"section"``.
- Fixed a bug where if there was a trailing or leading "/" in the ``filter_by`` argument in the ``data_type()``, ``ids()``, and ``times()`` methods, then an empty return was almost guaranteed.
- Fixed a bug in when asking for the ``"wetted perimeter"`` data type in the ``HydTablesCheck.section()`` output class would cause a python exception.
- Added proper format checking for SMS ``.dat`` files.
- Fixed a bug when loading a ``.dat`` file (not from the ``.sup``) where the file path attribute ``fpath`` was being being set incorrectly.
- Fixed a time-series and section plotting for ``.dat`` files which was not working.
- Added the missing format checker for the ``CATCHJson`` class.
- Added ``fpath`` property to ``CATCHJson`` class to be consistent with other output classes.
- Added a timzone to the ``CATCHJson`` reference time.
- Removed ``WARNING  Invalid data type:`` that was triggered incorrectly in ``CATCHJson`` if the data type was not in one of the result files but it was present in another.
- Added timezone information to ``FVBCTide`` output class.

1.0.1
"""""

- Fixed a bug that would incorrectly flag ``1d_nwk`` ``Q`` channel curve references (the reference to the pit database name) as files and then flag the file as missing.
- Fixed a bug for 1D results where if the ``"section/3d"`` filter was passed into the ``data_types()`` or ``ids()`` methods, the return value would incorrectly return populated lists. The return is now an empty list since 1D results do not have any 3D results.

1.0.0
"""""

First full release of PyTUFLOW.



Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
