.. _pytuflow-arr:

pytuflow-arr
============

The ``pytuflow-arr`` tool converts `Australian Rainfall and Runoff <http://arr.ga.gov.au/home>`_ rainfall and loss data from the `ARR Data Hub <https://data.arr-software.org/about>`_ into TUFLOW model input files (``Event_File.tef``, ``bc_dbase.csv``, ``rf_inflow/*.csv``,
``soils.tsoilf`` / ``*.trd``).

This tool is a clean rewrite of the ``ARR to TUFLOW`` script from the QGIS TUFLOW plugin for the **2026 v1** ARR datahub major update. Consequently, it does not support legacy versions of the datahub. It provides many options for backward compatibility, however not every legacy option is supported and many of the defaults are new for the 2026 v1 ARR datahub update.

Key Differences to the Legacy QGIS Plugin Tool
----------------------------------------------

- Defaults have changed where appropriate for the 2026 v1 update. For example, the "current" 2030 rainfall is default. Other regional/jurisdication specifics such as using the new NSW storm losses (as opposed the the probability neutral losses) is now also the default.
- The datahub API now supports uploading catchment files. Previously, this was not possible and the catchment centroid was used. Now the catchment will be uploaded directly if a GIS file is provided.

.. warning::

    It is the users responsibility to use a valid catchment. There could be circumstances where the polygon is rejected by the datahub e.g. if there are too many vertices.

- The tool does not scrape the BOM website and relies on rainfall depths provided on the datahub. Currently, frequent rainfall depths are not provided and as such, frequent events are not yet supported.
- Preburst rainfall extrapolation is done by a new method of holding the preburst ratio constant. Previous methods of extrapolating prebursts < 60 minutes are still supported however the new method is the default. Previously, preburst depths for events outside the AEP range were not extrapolated and the initial loss was set to zero. The new extrapolation method is used instead and it is not possible to use the legacy method.

.. note::

    Preburst depths now go down to 30 minutes, therefore extrapolation only applies for durations < 30 minutes (not 60 minutes like the legacy datahub)

- Climate change rainfall is now provided by the datahub and the option to modify the baseline temperature or the delta temperature value is not supported by the new tool.
- By default, the tool will now automaticall switch to using a complete storm if the preburst rainfall depth is greater than the storm initial loss (for those specific events), however this can also be turned off.
- The "Use event independent continuing loss" option has been removed as some regions use AEP specific losses.
- The "data" folder has been renamed "working data" and the outputs have been changed. Among other changes, plots are no longer included and the tool uses the ``json`` format when downloading data. The ``json`` format is more code friendly to parse (unfortunately less human readable than the text format).

Usage
-----

.. code-block:: bash

    pytuflow-arr config1.json [config2.json ...]

Each JSON config file describes a single site/catchment. When multiple config files are
given, they are processed in order and their TUFLOW outputs are **appended** into a
single set of output files (one ``Event_File.tef``, ``bc_dbase.csv``, etc, covering all
sites) rather than overwritten by each subsequent config - equivalent to the legacy
script's multi-catchment batching.

Only the ``site`` section may differ between the config files - every other setting
(``events``, ``losses``, ``climate_change``, ``temporal_patterns``, ``output``, etc) is taken from
the *first* config file regardless of what any later file contains. Every file after the
first must still include a `site` section, but any other top-level key it contains is
ignored (with a warning) rather than being merged in or validated against the first
file's settings - this keeps the override rule simple and unambiguous. The site name for each config should be unique, otherwise subsequent configs will overwrite previous config's outputs.

Add ``-v`` / ``--verbose`` for debug-level logging.

JSON Config File
----------------

Every section below is optional unless stated otherwise - omitted sections use the
documented defaults. Unknown keys (at any level) raise a validation error rather than
being silently ignored, to catch typos early.

The json example below shows all the available keys and is not necessarily valid (e.g. long/lat and catchment boundary keys are mutually exclusive).

.. code-block:: json

    {
        "site": {
            "name": "Site1",
            "latitude": -33.9347,
            "longitude": 150.8372,
            "catchment_boundary": "path/to/geojson",
            "catchment_area": 11.4,
            "outlet_latitude": -33.9347,
            "outlet_longitude": "150.8372"
        },
        "response_json": "path/to/previously/saved/datahub.json",
        "ifd": {
            "baseline_year": 2030
        },
        "events": {
            "aep": ["50%", "20%", "10%", "5%", "2%", "1%"],
            "duration": [60, 120, 180, 360, 720, 1440],
            "output_notation": "aep"
        },
        "temporal_patterns": {
            "point_tp_csv": "path/to/previously/saved/point_tp_inc.csv",
            "areal_tp_csv": "path/to/previously/saved/areal_tp_inc.csv",
            "additional_tp": [],
            "all_point_tp": false,
            "add_areal_tp": 0
        },
        "climate_change": {
            "enabled": false,
            "scenarios": [
                {"baseline_year": 2050, "ssp": "SSP3"},
                {"baseline_year": 2090, "ssp": "SSP3"}
            ]
        },
        "preburst": {
            "percentile": "recommended",
            "pattern_method": "recommended",
            "pattern_duration": 2,
            "pattern_tp": "TP01",
            "duration_proportional": true,
            "pattern_duration_max": 6
        },
        "losses": {
            "method": "recommended",
            "extrapolation_method": "constant_preburst_ratio",
            "mar": 600,
            "static_loss": 10,
            "tuflow_loss_method": "infiltration",
            "user_initial_loss": 10,
            "user_continuing_loss": 2.5,
            "urban_initial_loss": 0,
            "urban_continuing_loss": 1,
            "climate_change_method": "storm"
        },
        "arf": {
            "ignore_limits_for_frequent": false,
            "min_arf": 0.2
        },
        "complete_storm": false,
        "output": {
            "path": "C:\\path\\to\\output",
            "format": "csv",
            "verbose": false
        }
    }

Parameter descriptions
^^^^^^^^^^^^^^^^^^^^^^

**site (required)**

.. list-table::
   :widths: 15 10 10 65
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - name
     - ``string``
     - ``-``
     - Site/catchment identifier - used as a prefix for output file names (e.g. <name>_RF_...) and as the TUFLOW IL_<name>/CL_<name> loss variable suffix. **Required**.
   * - latitude / longitude
     - ``number``
     - ``null``
     - Site (catchment centroid) coordinates, decimal degrees. **Required**, unless catchment_boundary is set (mutually exclusive with it), or unless the top-level response_json key is set (see below), in which case they are not used and may be omitted.
   * - catchment_boundary
     - ``string``
     - ``null``
     - Path to a catchment boundary polygon file to upload to the ARR Data Hub instead of a single lat/lon point - GeoJSON (.geojson/.json), KML (.kml), or Shapefile (.shp - its .shx/.dbf/.prj sibling files alongside it are also uploaded automatically). Mutually exclusive with latitude/longitude. **Required**, unless a lat/lon is provided (this takes precedence), or the top-level response_json key is set (see below), in which case this is not used and may be ommitted.
   * - outlet_latitude / outlet_longitude
     - ``number``
     - ``null``
     - Optional catchment outlet coordinates, decimal degrees. Used by the ARR datahub for jurisdiction guidance.
   * - catchment_area
     - ``number``
     - ``null``
     - Catchment area in km\ :sup:`2`. Catchment area is not extracted from the polygon geometry and it must be provided if it is to be considered.

**events (required)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - aep
     - ``list[string | number]``
     - ``[]``
     - AEP/ARI magnitude labels to assemble events for. For example, "1%" or "1 in 100". If a number is provided, it is assumed to be "% AEP". **Requried**.
   * - duration
     - ``list[number]``
     - ``[]``
     - Storm durations in minutes. E.g. ``[60, 120, 360]``. **Required**.
   * - output_notation
     - ``string``
     - ``"aep"``
     - "aep" (default) or "ari" - controls the name of the events in the output.

**response_json (top-level, optional)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - response_json
     - ``string``
     - ``null``
     - Path to a previously saved ARR datahub response json file (e.g. a prior run's ``working_data/<site>_ARR_response.json`` output). Useful if needing to re-run the tool again on a previous response (this ensures the same processing output if the datahub has had subsequent updates - as long as the pytuflow version is the same as run previously).

**ifd (optional)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - baseline_year
     - ``int``
     - ``2030``
     - The IFD baseline year to use. For example, ``1990`` will provide similar rainfall IFD curves as the previous tool when extracting data from the BOM (with the exception of catchments that might use other datasets like LIMB rainfall data). The options will depend on the catchment.

**temporal_patterns (optional)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - point_tp_csv
     - ``string``
     - ``null``
     - Path to a previously saved or downloaded point temporal pattern CSV to use instead of downloading the data from the datahub. The file must be in the same format as the ``*_Increments.csv`` file from the datahub.
   * - areal_tp_csv
     - ``string``
     - ``null``
     - Same as the ``point_tp_csv`` above but for areal temporal patterns.
   * - additional_tp
     - ``list[str]``
     - ``[]``
     - Names of ARR temporal pattern regions to include. Regions listed here are in addition to the automatically determined region from catchment location. The list can also be paths to previously saved temporal pattern increments (both point and areal should be provided). Regions include: ``rangelands``, ``rangelands west``, ``wet tropics``, ``monsoonal north``, ``central slopes``, ``murray basin``, ``east coast north``, ``east coast south``, ``southern slopes mainland``, ``southern slopes tasmania``, ``east flatlands``, ``west flatlands``.
