.. _pytuflow-project:

pytuflow-project
================

The ``pytuflow-project`` command provides tools for creating and managing TUFLOW project skeletons.
It supports both the classic HPC (2D/1D) and TUFLOW FV (finite volume) engines.

.. code-block:: text

    pytuflow-project <subcommand> [options]

Subcommands
-----------

create
^^^^^^

Create a new TUFLOW project skeleton from scratch.

.. code-block:: bash

    pytuflow-project create        \
        --engine {hpc,fv}          \
        --name <NAME>              \
        --output-dir <OUTPUT_DIR>  \
        --crs <CRS>                \
        [options]

**Required arguments:**

.. list-table::
   :widths: 35 75
   :header-rows: 1

   * - Argument
     - Description
   * - ``--engine {hpc,fv}``
     - TUFLOW engine type. Use ``hpc`` for the classic 2D/1D engine or ``fv`` for TUFLOW FV.
   * - ``--name <NAME>``
     - Model name used to label generated files and directories.
   * - ``--output-dir <OUTPUT_DIR>``
     - Directory in which the project skeleton will be created.
   * - ``--crs <CRS>``
     - Coordinate reference system, e.g. ``EPSG:32760``.

**Optional arguments:**

.. list-table::
   :widths: 35 75
   :header-rows: 1

   * - Argument
     - Description
   * - ``--features <FEATURES> ...``
     - One or more optional feature names to include (see :ref:`list-features`).
   * - ``--recipe <RECIPE>``
     - Recipe name, path to a ``.json`` file, or inline JSON string to use as a base (see :ref:`list-recipes`).
   * - ``--defaults <DEFAULTS>``
     - Path to a JSON file or inline JSON string of variable defaults. Overrides bundled defaults; overridden by ``--recipe`` and explicit ``--<var>`` flags.
   * - ``--force`` / ``-f``
     - Overwrite existing files without prompting.
   * - ``--yes`` / ``-y``
     - Same as ``--force``.
   * - ``--no`` / ``-n``
     - Skip any files that already exist.
   * - ``--interactive`` / ``-i``
     - Prompt for each existing file before overwriting.
   * - ``[default overrides]``
     - Override default settings. E.g. ``--gis-format SHP``. (see :ref:`list-defaults`).

**Example 1:**

The following example:
  - Creates a new Classic/HPC model from the "basic_2d" recipe template. 
  - Overrides the SGS sample distance and sets the value to 1m. 
  - Sets the DEM path. The DEM is not copied into the project folder, so the path should be set to where the DEM for the project will be (it is ok if it does not exist). Absolute paths can be provided and will be converted to a relative path in the template control file.

.. code-block:: bash

    pytuflow-project create \
        --engine hpc \
        --name MyFloodModel \
        --output-dir ./projects/my_flood_model \
        --crs "EPSG:32760" \
        --recipe basic_2d \
        --sgs-sample-distance 1 \
        --dem-path grid/dem.tif

**Example 2:**

The following example:
  - Creates a TUFLOW FV model
  - It does not use a recipe template, but instead lists the features that should be added.
  - Overrides spherical setting
  - Features are added by using the feature name (``salinity``, ``temp``, ``3d``)
  - Features are added using a literal json string with specific settings (``outputnc``).

.. code-block:: bash

  pytuflow-project create \
    --engine fv \
    --name MyCoastalModel \
    --output-dir ./projects/my_coastal_model \
    --crs "EPSG:4326" \
    --spherical 1 \
    --features salinity temp 3d '{"name": "outputnc", "output_params": "h v d SAL TEMP"}'

insert
^^^^^^

Insert a feature into an existing TUFLOW project.

.. code-block:: text

    pytuflow-project insert --cf CF --feature FEATURE [options]

**Required arguments:**

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Argument
     - Description
   * - ``--cf CF``
     - Path to the main control file (``*.tcf`` for HPC or ``*.fvc`` for FV).
   * - ``--feature FEATURE``
     - Name of the feature to insert (see :ref:`list-features`).

**Optional arguments:**

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Argument
     - Description
   * - ``--engine {hpc,fv}``
     - TUFLOW engine type (default: ``hpc``).
   * - ``--defaults DEFAULTS``
     - Path to a JSON file or inline JSON string of variable defaults.
   * - ``--force`` / ``-f``, ``--yes`` / ``-y``, ``--no`` / ``-n``, ``--interactive`` / ``-i``
     - File conflict resolution (same as ``create``).
   * - ``--iter``, ``--gis-format``, ``--grid-format``, ``--hardware``, ``--units``, ``--iwl``, ``--event-name``, ``--event-text``, ``--start-time``, ``--end-time``, ``--timestep``, ``--dem-path``, ``--po-path``
     - Variable overrides (same as ``create``).

**Example:**

.. code-block:: bash

    pytuflow-project insert \
        --engine hpc \
        --cf ./projects/my_flood_model/runs/MyFloodModel.tcf \
        --feature estry

.. _init-templates:

init-templates
^^^^^^^^^^^^^^

Initialise (or refresh) the local user template cache.
Run this once after installation, or again with ``--force`` to reset to bundled defaults.

.. code-block:: text

    pytuflow-project init-templates [--engine {hpc,fv}] [--force]

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Argument
     - Description
   * - ``--engine {hpc,fv}``
     - Initialise templates for a specific engine only. Omit to initialise both.
   * - ``--force`` / ``-f``
     - Overwrite the existing template cache.

.. _list-features:

list-features
^^^^^^^^^^^^^

List the features available for a given engine.

.. code-block:: text

    pytuflow-project list-features [--engine {hpc,fv}]

**HPC features:**

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Name
     - Description
   * - ``ad``
     - AD (Advection-Diffusion)
   * - ``estry``
     - Estry (1D Drainage)
   * - ``events``
     - Events (Event File)
   * - ``po``
     - Plot Output (PO)
   * - ``quadtree``
     - Quadtree (Variable Resolution)
   * - ``rf``
     - RF (Gridded Rainfall)
   * - ``rl``
     - Reporting Location (RL)
   * - ``sgs``
     - Sub-grid Sampling (SGS)
   * - ``soils``
     - Soils (Infiltration)
   * - ``swmm``
     - SWMM (EPA-SWMM)
   * - ``toc``
     - TOC (Operational Controls)
   * - ``tutorial``
     - Tutorial Model

**FV features (selection):**

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Name
     - Description
   * - ``3d``
     - 3D
   * - ``ad``
     - Advection Dispersion
   * - ``events``
     - Events (Event File)
   * - ``ptm``
     - Particle Tracking
   * - ``salinity``
     - Salinity
   * - ``stm``
     - Sediment Transport
   * - ``temp``
     - Temperature
   * - ``wqm``
     - Water Quality
   * - ``tutorial``
     - Tutorial Model

Run ``pytuflow-project list-features --engine fv`` for the full FV feature list.

.. _list-recipes:

list-recipes
^^^^^^^^^^^^

List the built-in recipes for a given engine.
A recipe is a predefined combination of features and variable defaults.

.. code-block:: text

    pytuflow-project list-recipes [--engine {hpc,fv}]

**HPC recipes:**

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Name
     - Description
   * - ``basic_2d``
     - Basic 2D Model — Basic 2D HPC model with SGS, events, and PO.
   * - ``quadtree``
     - Quadtree 2D Model — 2D HPC model with quadtree, SGS, events, and PO.
   * - ``tutorial``
     - Tutorial model — Minimal 2D HPC model with SGS.

**FV recipes:**

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Name
     - Description
   * - ``2d_hd``
     - 2D Hydrodynamic Model — Standard 2D flood model with NetCDF HD output.
   * - ``2d_sed``
     - 2D Sediment Transport Model — 2D sediment transport model.
   * - ``3d_ad``
     - 3D Advection Dispersion Model — 3D advection dispersion model with salinity and temperature.
   * - ``3d_ptm``
     - 3D Particle Tracking Model — 3D particle tracking model.
   * - ``3d_wqm``
     - 3D Water Quality Model — 3D water quality model.

.. _list-defaults:

list-defaults
^^^^^^^^^^^^^

Text
