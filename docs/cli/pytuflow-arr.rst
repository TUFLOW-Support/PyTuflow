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

- Climate change rainfall is now provided by the datahub and the option to modify the baseline temperature or the delta temperature value is not supported by the new tool. This also means that currently only the 2030, 2050, and 2090 baselines are available.
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
     - ``-``
     - Site (catchment centroid) coordinates, decimal degrees. **Required**, unless catchment_boundary is set (mutually exclusive with it), or unless the top-level response_json key is set (see below), in which case they are not used and may be omitted.
   * - catchment_boundary
     - ``string``
     - ``-``
     - Path to a catchment boundary polygon file to upload to the ARR Data Hub instead of a single lat/lon point - GeoJSON (.geojson/.json), KML (.kml), or Shapefile (.shp - its .shx/.dbf/.prj sibling files alongside it are also uploaded automatically). Mutually exclusive with latitude/longitude. **Required**, unless a lat/lon is provided (this takes precedence), or the top-level response_json key is set (see below), in which case this is not used and may be ommitted.
   * - outlet_latitude / outlet_longitude
     - ``number``
     - ``-``
     - Optional catchment outlet coordinates, decimal degrees. Used by the ARR datahub for jurisdiction guidance.
   * - catchment_area
     - ``number``
     - ``-``
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

**output (required)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - path
     - ``string``
     - ``-``
     - Output directory for the tool. **Required**.
   * - format
     - ``string``
     - ``"csv"``
     - Rainfall hyetograph file format: "csv" or "ts1" (TUFLOW's native ts1 format).
   * - verbose
     - ``bool``
     - ``false``
     - If true, also writes intermediate "working data" files (areal design IFD table, ARF table, burst initial loss table, extrapolated short-duration losses CSV, and raw point/areal temporal pattern increment CSVs) to a working_data subfolder - see :ref:`working_data` section below.

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
     - ``-``
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
     - ``-``
     - Path to a previously saved or downloaded point temporal pattern CSV to use instead of downloading the data from the datahub. The file must be in the same format as the ``*_Increments.csv`` file from the datahub.
   * - areal_tp_csv
     - ``string``
     - ``-``
     - Same as the ``point_tp_csv`` above but for areal temporal patterns.
   * - additional_tp
     - ``list[str]``
     - ``[]``
     - Names of ARR temporal pattern regions to include. Regions listed here are in addition to the automatically determined region from catchment location. The list can also be paths to previously saved temporal pattern increments (both point and areal should be provided). Regions include: ``rangelands``, ``rangelands west``, ``wet tropics``, ``monsoonal north``, ``central slopes``, ``murray basin``, ``east coast north``, ``east coast south``, ``southern slopes mainland``, ``southern slopes tasmania``, ``east flatlands``, ``west flatlands``.

**climate_change (optional)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - enabled
     - ``bool``
     - ``false``
     - If ``true``, an additional event is assembled for each scenario in scenarios, alongside the base (no climate-change) event.
   * - scenarios
     - ``list[object]``
     - ``[]``
     - List of {"baseline_year": ..., "ssp": ...} objects. Required (non-empty) if enabled is ``true``.

Each scenario object:

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - baseline_year
     - ``int``
     - ``-``
     - Allowed values: ``2030``, ``2050``, ``2090``
   * - ssp
     - ``int``
     - ``-``
     - Allowed values: ``SSP1``, ``SSP2``, ``SSP3``, ``SSP5``

**preburst (optional)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - percentile
     - ``string``
     - ``"recommended"``
     - Preburst ratio percentile to use to derive the preburst depth: one of "10%", "25%", "50%", "75%", "90%", or "recommended". The "recommended" value falls back to "50%" for regions that don't explicitly have a datahub recommended table.
   * - pattern_method
     - ``string``
     - ``"recommended"``
     - Preburst pattern method: "recommended", "constant", "temporal_pattern", or "none" (see :ref:`complete_storm_assembly` below).
   * - pattern_duration
     - ``number``
     - ``2``
     - Preburst duration in hours (or a proportion of the storm duration, if ``duration_proportional`` is true). Used by the "constant"/"temporal_pattern" pattern methods directly, and as the fallback method for the "recommended" option (see :ref:`complete_storm_assembly` below).
   * - pattern_tp
     - ``string``
     - ``"TP01"``
     - Which existing point temporal pattern to shape the preburst rainfall with. ``"design_burst"`` will match preburst pattern to the same number as the design burst e.g. TP01 design burst will use TP01 for preburst, TP03 will use TP03 etc. Used when the pattern_method is set to "temporal_pattern" (or the "recommended" option fallsback to "temporal_pattern").
   * - duration_proportional
     - ``bool``
     - ``true``
     - If ``true``, pattern_duration is treated as a proportion of the storm duration rather than an absolute number of hours.
   * - pattern_duration_max
     - ``number`` | ``null``
     - ``6``
     - Caps the computed preburst duration (hours) when duration_proportional is true - without this, a proportional pattern_duration (e.g. the default of 2x the storm duration) would produce an unrealistically long preburst period for long storm durations (e.g. a 72 hour storm would otherwise get a 144 hour preburst). Has no effect when duration_proportional is false (an absolute pattern_duration is always used as given, uncapped). Set to ``null`` to disable capping entirely.

**losses (optional)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - method
     - ``string``
     - ``"recommended"``
     - Options are: ``recommended`` or ``probability_neutral``. The ``recommended`` method uses the new AEP dependent losses table for NSW catchments, otherwise uses the standard storm losses. ``probability_neutral`` is provided as a legacy method and only available as for NSW catchments. The methods differ on how they handle missing data. The ``recommended`` approach derives losses from the preburst ratio. For interior missing duration values it interpolates preburst ratios in log-linear space. For missing exterior values, it extrapolates values using the extrapolation_method. The ``probability_neutral`` losses are not preburst derived, so interior missing duration cells are derived using a plain linear interpolation. Exterior missing values hold the nearest edge column value constant.
   * - extrapolation_method
     - ``string``
     - ``"constant_preburst_ratio"``
     - How to extrapolate the burst initial loss for durations shorter than the datahub's shortest provided duration. The options are: ``constant_preburst_ratio``, ``interpolate``, ``log_interpolate``, ``interpolate_preburst``, ``log_interpolate_preburst``, ``rahman``, ``hill``, ``constant``, ``static``. See :ref:`loss_extrapolation` section below.
   * - mar
     - ``number``
     - ``-``
     - Mean annual rainfall (mm). Required when using the ``hill`` extrapolation_method.
   * - static_loss
     - ``number``
     - ``-``
     - User defined burst initial loss value for durations shorter than provided by the datahub. Required for the ``static`` extrapolation_method.
   * - tuflow_loss_method
     - ``string``
     - ``"infiltration"``
     - The options are ``infiltration`` and ``excess``. "infiltration" writes a ``soils.tsoilf`` with a ILCL entry; "excess" writes a ``materials.csv`` file.
   * - user_initial_loss
     - ``number``
     - ``-``
     - Overrides the storm initial loss value with a value provided by the user. If the user is also using probability neutral losses, the burst initial loss is calculated as ``burst_il = user_initial_loss * pn_burst_il / datahub_storm_initial_loss`` (where the datahub storm initial loss is the old flat storm loss).
   * - user_continuing_loss
     - ``number``
     - ``-``
     - Overrides the storm continuing loss value with a value provided by the user.
   * - urban_initial_loss / urban_continuing_loss
     - ``number``
     - ``-``
     - Adds a fixed loss value for urban areas to the output TUFLOW files.
   * - climate_change_method
     - ``string``
     - ``"storm"``
     - How the datahub's initial loss climate change factor is applied to the initial loss. The options are ``storm`` and ``burst``. The ``storm`` method scales the storm initial loss and subtracts the climate change adjusted preburst rainfall (by using climate change rainfall the and the preburst ratio). The ``burst`` option scales the burst initial loss.

**arf (optional)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - min_arf
     - ``number``
     - ``0``
     - Minimum allowed ARF value (0-1); calculated ARF values are clamped to this floor.

**complete_storm (top-level, optional)**

.. list-table::
   :widths: 15 10 10 65 
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - complete_storm
     - ``bool``
     - ``false``
     - If true, every requested event is assembled as a complete storm (preburst period prepended ahead of the design burst), using the preburst section's settings.

.. _loss_extrapolation:

Loss extrapolation
------------------

The available loss extrapolation methods are detailed below. The default method is new to this tool, the other methods are provided as legacy methods. Extrapolation beyond the AEP range is always done using ``constant_preburst_ratio`` and the legacy methods only effect duration extrapolation (for short durations).

- ``constant_preburst_ratio`` - holds the preburst ratio constant from the nearest table row/column edge.
- ``interpolate`` - interpolates the losses using the assumption that at zero minute duration, the initial loss is zero.
- ``log_interpolate`` - same as the ``interpolate`` option but uses a log scale for duration (uses a boundary value of zero for zero minutes).
- ``interpolate_preburst`` - interpolates the preburst depths using the assumption that at zero minute duration, the preburst depth is zero.
- ``log_interpolate_preburst`` - same as ``interpolate_preburst`` option but uses a log scale for duration (uses a boudary value of zero for zero minutes).
- ``rahman`` - uses an equation determined by a study conducted by Rahman et al 2002.
- ``hill`` - uses an equation dtermined by a study conducted by Hill et al 1996:1998. This requires the user to provide a mean anuual rainfall value (the ``mar`` parameter value).
- ``constant`` - holds the burst initial loss constant from the nearest table row edge. This matches the method named "Use 60 min loss" in the legacy QGIS tool.
- ``static`` - user defined value that will be used for all the extrapolated values. The method requires setting the ``static_loss`` parameter.

.. _complete_storm_assembly:

Complete storm assembly
-----------------------

something

.. _working_data:

Working data
------------

something
