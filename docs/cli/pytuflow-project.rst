.. _pytuflow-project:

pytuflow-project
================

.. note::

  This is an experimental feature. This means that the CLI is not considered final and can change in future versions without provision for backward compatibility.

The ``pytuflow-project`` command provides tools for creating and managing TUFLOW project skeletons.
It supports both TUFLOW Classic/HPC and TUFLOW FV.

The templates used by ``pytuflow-project`` are highly customisable and extendable. For more information on how to do this, see the :ref:`pytuflow-project_customisation` section below.

.. code-block:: text

    pytuflow-project <subcommand> [options]

The underpinning API for ``pytuflow-project`` are the following classes:

- :class:`~pytuflow.HPCProject`
- :class:`~pytuflow.FVProject`

Subcommands
-----------

.. _create:

create
^^^^^^

Create a new TUFLOW project skeleton from scratch.

.. code-block:: bash

    pytuflow-project create \
        --engine {hpc,fv} \
        --name <NAME> \
        --output-dir <OUTPUT_DIR> \
        --crs <CRS> \
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
     - Model name used to label generated files.
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
     - One or more optional features to include (see :ref:`list-features`).
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
  - Sets the DEM path. The DEM is not copied into the project folder, so the path should be set to where the DEM for the project will be (it is ok if it does not exist). Absolute paths can be provided and they will be converted to a relative path in the template control file (relative paths will always be copied without modification).

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
  - Overrides the spherical setting
  - It does not use a recipe template, but instead lists the features that should be added.
  - It adds features by using the feature name (``salinity``, ``temp``, ``3d``)
  - It adds the ``outputnc`` feature with local settings using a literal json string.

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

    pytuflow-project insert --cf <CF> --feature <FEATURE> [--engine {hpc,fv}] [options]

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
     - TUFLOW engine type. If not provided, the control file extension will be used to determine the engine (a ``.tcf`` or ``.fvc`` extension is expected).
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

The following example:
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

.. warning::

  Any customisations made by the user could be overriden by this process if ``--force`` is used.

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

``pytuflow-project`` uses a combination of :ref:`template_control_files`, :ref:`Modular Features<features>`, :ref:`variables`, and :ref:`directives`, which are fully customisable and extendable by the user. 
    
When the tool is run for the first time, template files are copied locally to the user's home directory:

- Windows: ``%userprofile%\.tuflow_model_files\project_templates``
- Linux: ``~/.tuflow_model_files/project_templates``

Subsequent calls will use these cached templates, and the user is free to modify and/or extend them. The templates can be re-copied (potentially erasing any modifications made by the user) at any time by running the :ref:`init-templates` subcommand.

The following sections go into details about the various building blocks of the ``pytuflow-project`` utility. Files and subdirectories listed
in the sections assume the root directory are the cache directories listed above.

.. _template_control_files:

Template Control files
^^^^^^^^^^^^^^^^^^^^^^

Template control files are found within the ``hpc`` and ``fv`` subdirectories. The user is free to modify the templates to their preferred setup.

Template control files are made up of standard TUFLOW commands as well as :ref:`directives<directives>` and :ref:`variables<variables>`.

- :ref:`Directives`:  Directives are simple logic blocks that allow commands to be inserted based on certain conditions. E.g. whether a particular feature is present or based on a variable's value. Other directives allow dynamic insertion of command blocks using an ID (see :ref:`features`).
- :ref:`Variables`: Variables are placeholders that allow values to be dynamically assigned at the tool's runtime.

.. _directives:

Directives
^^^^^^^^^^

Directives are simple logic blocks that allow commands to be inserted based on certain conditions. E.g. whether a particular feature is present or based on a variable's value. Other directives allow dynamic insertion of command blocks using an ID.

Directives take the form of ``##<directive>##``. Directives can reside in the template control files and also within command blocks defined in :ref:`features`.

**Logic**

.. code-block:: text

  ##IF [not:]<condition>##
  ...
  ##ENDIF##

Conditions can check if a :ref:`feature<list-features>` exists:

.. code-block:: text

  ##IF feature:quadtree##
  ...
  ##ENDIF##

The feature is assessed against whether it exists in the subcommand (either :ref:`create` or :ref:`insert`) via the ``--features`` argument. It does not look to see if the feature exists within the model in general. E.g. checking against quadtree does not check for a quadtree control file, it must have been passed in via ``--features quadtree``.

Conditions can also be checked against a variable's value (``==`` and ``:`` are synonymous operators for variables):

.. code-block:: text

  ##IF ${gis_format}==GPKG##
  ...
  ##ENDIF##

Other supported operators are ``>`` and ``<``. ``not:`` can be put in front to negate the outcome.

A semicolon ``;`` can be used to check against multiple values:

.. code-block:: text

  ##IF ${gis_format}==GPKG;SHP##
  ...
  ##ENDIF##

**Command insertion**

Commands can be inserted with ``##COMMANDS <command_id>##``. Command blocks within the :ref:`features` set will be searched for the appropriate command block to insert at that location. The command placement rules will be ignored in this case as the directive takes precedence and places the command block at an exact location.

**Iteration**

If a variable is a list of values, then these can be iterated over with the following directive:

.. code-block:: text

  ##ITER:${var_name}##
  ...
  ##ENDITER##

**Blocks**

TUFLOW FV uses blocks within its control file, and these blocks can contain nested blocks, and so on. It can sometimes be required to tell pytuflow about these blocks with a directive. This is typically not required within template files, but can be needed for feature commands when adding nested blocks. See either the ``ptmmat`` or ``sedmat`` features as an example use case.

.. code-block:: text

  Mobility model == velocity
  ##STARTBLOCK##
  ...
  ##ENDBLOCK##  

.. _variables:

Variables
^^^^^^^^^

Variables are placeholders that allow values to be dynamically assigned at the tool's runtime.

Variables are always in the form of ``${var_name}``. They can be used in any control file command or in file names.

See :ref:`defaults` for more information on how to modify/extend the available variables.

.. _features:

Features
^^^^^^^^

Feature settings can be found in:

- ``features/hpc``
- ``features/fv``

The ``json`` files can be modified by the user to be setup to their preference. New features can also be added by creating new files in the appropriate location and they will automatically become available via the CLI.

Feature ``json`` settings are made up of template files that will be copied into the model, and command blocks that will be inserted into a given control file. :ref:`template_control_files` are stored within the cache directory. Any new template files added by the user should also be placed there.

A brief overview of the settings within the ``json`` files are described below:

**General**

.. list-table::
  :widths: 35 75
  :header-rows: 1

  * - Variable
    - Description
  * - name
    - Name of the feature. Should match the file name and be unique.
  * - display_name
    - A prettier version of the name.
  * - sort_order
    - The order to add features if multiple features are being added.
  * - template_files
    - List of template files to copy into the model (see below)
  * - command_blocks
    - List of command blocks to insert into the model (see below)

**Template files**

.. list-table::
  :widths: 35 75
  :header-rows: 1

  * - Variable
    - Description
  * - template_key
    - The location of the template file (relative to the relevant cache folder) to copy
  * - output_subdir
    - Where to copy the template file relative to the model's root directory
  * - target_name
    - Optional setting if the copied template file should have a different name to the original file.

**Command blocks**

.. list-table::
  :widths: 35 75
  :header-rows: 1

  * - Variable
    - Description
  * - id
    - Unique ID that can be used by directives to find the command
  * - target_cf
    - The control file to target when inserting the commands
  * - placement_rule
    - How to place the command into the control file. If omitted, then the command will be appended to the end of the control file. The rules are defined in ``rules.json`` and each rule lists commands to insert the command block either before or after
  * - allow_multiple
    - If set to ``true``, the command can be inserted multiple times. If set to ``false`` (default), then the command will not be inserted again if it already exists within the control file (by default checks against the left-hand side of the command)
  * - existence_check
    - If included, will override what PyTUFLOW looks for when checking for the given command's existence. If included, it will be the existence check for the entire command block, which can consist of multiple commands. If omitted, each command in the command block is checked. It's possible to use regex by bracketing the command with a forward slash ``/``. Flags can be added after the trailing slash, e.g. ``/<regex>/i`` to ignore case.
  * - target_previous_block
    - FV specific option. It will insert the commands as subcommands to the previously inserted command block. This is required if the previous command is the start of an FV block (e.g. ``Output == netcdf``) and the current commands belong beneath that block.
  * - by_directive_only
    - If set to ``true``, this command block will not be inserted unless by a :ref:`directive<directives>`. Default is ``false``.
  * - commands
    - A list of commands to insert. :ref:`directives` are accepted.

.. _recipes:

Recipes
^^^^^^^

Recipes are predefined combinations of feature sets and variable defaults.

PyTUFLOW comes bundled with default recipes which can be modified by the user, or the user can create new recipes. To create a new recipe, the user should add a new ``json`` file within the appropriate directory and it will automatically become avaiable via the CLI.

Recipes can be found within the following subdirectories:

- ``recipes/hpc``
- ``recipes/fv``

The ``json`` file settings are briefly described below:

.. list-table::
  :widths: 35 75
  :header-rows: 1

  * - Variable
    - Description
  * - display_name
    - A prettier version of the recipe file name
  * - description
    - A high level description of what the recipe contains
  * - variables
    - A dictionary of variables which override the defaults. Default overrides passed in via the CLI will take precedence
  * - features
    - A list of features included in the recipe. The features can be added in the same method as they are added in the CLI :ref:`create` subcommand (by just the name or by a json string). Variables defined via a json string will take precedence over variables defined in the "variables" section (above),     however will still be overridden by variable overrides in the CLI.

.. _defaults:

Defaults
^^^^^^^^

Defaults are default variable values that are used if the user has not overridden them via the CLI. The default values are saved in:

- ``defaults.json``
- ``hpc_defaults.json``
- ``fv_defaults.json``

Engine specific defaults (e.g. ``hpc_defaults.json``) will take precedence if there are any conflicts with the shared defaults (``defaults.json``).

The user is free to update the defaults to their preferred settings. The defaults can also be extended by the user. Any new defaults added by the user will automatically become overridable via the CLI as an optional argument in the :ref:`create` and :ref:`insert` subcommands.

