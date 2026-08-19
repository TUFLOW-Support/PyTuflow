.. _pytuflow-project:

pytuflow-project
================

The ``pytuflow-project`` command provides tools for creating and managing TUFLOW project skeletons.
It supports both TUFLOW Classic/HPC and TUFLOW FV.

The templates used by ``pytuflow-project`` are highly customisable and extendable. For more information on how to do this, see the :ref:`pytuflow-project_customisation` section below.

.. code-block:: text

    pytuflow-project <subcommand> [options]

Subcommands
-----------

.. _create:

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
     - TUFLOW engine type. Use ``hpc`` for Classic/HPC models or ``fv`` for TUFLOW FV models.
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
  - Creates a new Classic/HPC model from the "basic_2d" recipe template (see :ref:`pytuflow-project_customisation` for more details on how to view recipe settings). 
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

.. _insert:

insert
^^^^^^

Insert a feature into an existing TUFLOW project.

.. code-block:: text

    pytuflow-project insert --cf <CF> --feature <FEATURE> [options]

**Required arguments:**

.. list-table::
   :widths: 35 75
   :header-rows: 1

   * - Argument
     - Description
   * - ``--cf <CF>``
     - Path to the main control file (``*.tcf`` for Classic/HPC or ``*.fvc`` for FV).
   * - ``--feature <FEATURE>``
     - Name of the feature to insert (see :ref:`list-features`).

**Optional arguments:**

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Argument
     - Description
   * - ``--engine {hpc,fv}``
     - TUFLOW engine type. If not provided, the control file extension will be used to determine the engine.
   * - ``--defaults DEFAULTS``
     - Path to a JSON file or inline JSON string of variable defaults.
   * - ``--force`` / ``-f``
     - Overwrite existing files without prompting.
   * - ``--yes`` / ``-y``
     - Same as ``--force``.
   * - ``--no`` / ``-n``
     - Skip any files that already exist.
   * - ``--interactive`` / ``-i``
     - Prompt for each existing file before overwriting.
   * - ``[default overrides]``
     - Override default settings. (see :ref:`list-defaults`).

**Example:**

The below example:
  - Inserts ESTRY as a feature into an existing TUFLOW Classic/HPC model
  - Sets the time series output interval to be every 2 minutes. If the relevant command already exists, it will have no effect.

.. code-block:: bash

    pytuflow-project insert \
        --cf ./projects/my_flood_model/runs/MyFloodModel.tcf \
        --feature estry \
        --time-series-output-interval 120

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

.. code-block:: bash

    pytuflow-project list-features --engine {hpc,fv}

.. _list-recipes:

list-recipes
^^^^^^^^^^^^

List the built-in recipes for a given engine.
A recipe is a predefined combination of features and variable defaults.

.. code-block:: bash

    pytuflow-project list-recipes --engine {hpc,fv}

.. _list-defaults:

list-defaults
^^^^^^^^^^^^^

List the defaults for a given engine. The defaults also serve as a list of optional arguments that can be passed into the :ref:`create` and :ref:`insert` subcommands.

.. code-block:: bash

    pytuflow-project list-defaults --engine {hpc,fv}

.. _pytuflow-project_customisation:

Customisation
-------------

Text
