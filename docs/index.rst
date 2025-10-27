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

1.0.2
"""""

- Fixed a bug where a ``"timeseries"`` filter would return an empty list when using the ``data_types()`` or ``ids()`` methods on ``GPKG2D`` and ``GPKGRL`` classes.
- Adds a timezone to ``NCGrid`` reference time.
- Adds a timezone to ``NCMesh`` reference time.
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
