.. _working_with_scenarios:

Working with Scenarios and Events
=================================

Scenarios and events are important components of any given TUFLOW model. They allow many different simulations
to be run from a single model setup (e.g. different storm events, development scenarios, or sensitivity analysis).

The below examples show how pytuflow handles scenarios and events, how to add or modify scenarios and events in a model,
and to run the model for specific / event combinations.

The following example uses models provided in the
`TUFLOW Example Model Dataset <https://wiki.tuflow.com/TUFLOW_Example_Models>`_.

Checking for Scenarios and Events
---------------------------------

Pytuflow deals with scenarios and events by assigning each input a list of :class:`Scope <pyutflow.Scope>` objects that
describe the context in which the input sits within the model. For example, a command that is within an
"If Scenario" block will have a scope list that tells pytuflow that the command is only relevant
if a particular scenario is active.

As an example, we can load the model ``EG16_~s1~_~s2~_002.tcf``, which has two scenario groups.

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG16_~s1~_~s2~_002.tcf')

In this model, the command:

``Read GRID Zpts == grid\DEM_SI_Unit_01.tif``

is always active, and the ``z shape`` command:

``Read GIS Z Shape == gis\2d_zsh_EG07_006_R.shp``

is only active if the scenario ``"D01"``  is active. So we can find those commands and check their scopes:

.. code-block:: pycon

    >>> inp = tcf.find_input('Read GRID Zpts')[0]
    >>> print(inp)
    Read GRID Zpts == grid\DEM_SI_Unit_01.tif
    >>> print(inp.scope)
    [<GlobalScope>]

    >>> inp = tcf.find_input('2d_zsh_EG07_006_R.shp')[0]
    >>> print(inp)
    Read GIS Z Shape == gis\2d_zsh_EG07_006_R.shp
    >>> print(inp.scope)
    [<ScenarioScope> !EXG, <ScenarioScope> D01]

The output tells us that the DEM is always active (it has a "Global Scope"), while the Z Shape command is only active
if the scenario ``"D01"`` is active. The addition of ``!`` at the front of the ``"EXG"`` scenario makes that scope negative,
meaning that the command is not active if the ``"EXG"`` scenario is active. This part is important, as
if the user passes in both ``"EXG"`` and ``"D01"`` scenarios when running the model, the Z Shape command will not be
included in the simulation.

Adding Scenarios to a Model
---------------------------

Scenarios can be added to an existing model, i.e. inputs can be put into a "If Scenario" block, by setting
the scope of a given input. The below example uses ``EG00_001.tcf`` from the
`TUFLOW Example Model Dataset <https://wiki.tuflow.com/TUFLOW_Example_Models>`_. In the below example, we will
put the hardware command inside a scenario called ``"GPU"``.

.. code-block:: pycon

    >>> from pytuflow import Scope
    >>> tcf = TCF('path/to/EG00_001.tcf')
    >>> gpu_inp = tcf.find_input('hardware')[0]
    >>> gpu_inp.scope = [Scope('Scenario', 'GPU')]

Note, that the input scope must be set to a list of scope objects, which is required as inputs can have multiple scopes.

We can view how this has modified the TCF by calling the :meth:`preview()<pytuflow.TCF.preview>` method:

.. code-block:: pycon

    >>> tcf.preview()
    ! TUFLOW CONTROL FILE (.TCF) defines the model simulation parameters and directs input from other data sources

    ! MODEL INITIALISATION
    Tutorial Model == ON                                ! This command allows for this model to be simulated without a TUFLOW licence
    GIS Format == SHP									! Specify SHP as the output format for all GIS files
    SHP Projection == ..\model\gis\projection.prj       ! Sets the GIS projection for the TUFLOW Model
    TIF Projection == ..\model\grid\DEM_SI_Unit_01.tif  ! Sets the GIS projection for the ouput grid files
    !Write Empty GIS Files == ..\model\gis\empty        ! This command is commented out. It is only needed for the project establishment

    ! SOLUTION SCHEME
    Solution Scheme == HPC								! Heavily Parallelised Compute, uses adaptive timestepping
    If Scenario == GPU
        Hardware == GPU										! Comment out if GPU card is not available or replace with "Hardware == CPU"
    End If
    SGS == ON											! Switches on Sub-Grid Sampling
    SGS Sample Target Distance == 0.5					! Sets SGS Sample Target Distance to 0.5m

    ! MODEL INPUTS
    Geometry Control File == ..\model\EG00_001.tgc		! Reference the TUFLOW Geometry Control File
    BC Control File == ..\model\EG00_001.tbc			! Reference the TUFLOW Boundary Conditions Control File
    BC Database == ..\bc_dbase\bc_dbase_EG00_001.csv	! Reference the Boundary Conditions Database
    Read Materials File == ..\model\materials.csv  		! Reference the Materials Definition File
    Set IWL == 36.5										! Define an initial 2D water level at start of simulation

    Timestep == 1
    Start Time == 0
    End Time == 3

    ! OUTPUT FOLDERS
    Log Folder == log		  							! Redirects log output files log folder
    Output Folder == ..\results\EG00\	  				! Specifies the location of the 2D result files
    Write Check Files == ..\check\EG00\		  			! Specifies the location of the 2D check files and prefixes them with the .tcf filename

    Map Output Format == XMDF TIF						! Result file types
    Map Output Data Types == h V d z0					! Specify the output data types
    TIF Map Output Data Types == h						! Specify the output data types for TIF Format
    Map Output Interval == 300  						! Outputs map data every 300 seconds
    TIF Map Output Interval == 0						! Outputs only maximums for grids

We can see that the "IF Scenario" and "End If" commands are automatically added to the TCF when
the scope is set to a scenario. Another thing to note, is that the indentation of the command is automatically set to the
correct level. This means that the user does not need to worry about any leading whitespace or indentation
when adding new commands to the control file.

.. _running_scenarios_in_a_model:

Running Scenarios in a Model
----------------------------

Let's save the modified model and run it with the ``"GPU"`` scenario active. First, let's rename the TCF file to
include a scenario slot ``~s1~``. In the previous example (:ref:`tcf_load_and_run`) we used the ``inc`` parameter in
the :meth:`TCF.write()<pytuflow.TCF.write>` method to modify the TCF file name. Unfortunately, the ``inc`` parameter
does not support complex renaming, and is designed only as a convenience method for incrementing the version number of the
model. So we will instead rename the TCF file path manually, then write the TCF in-place.

.. code-block:: pycon

    >>> tcf.fpath = tcf.fpath.with_name('EG00_~s1~_001.tcf')
    >>> tcf.write(inc='inplace')
    <TuflowControlFile> EG00_~s1~_001.tcf

Once the TCF file has been written to disk, we can run the model with the ``"GPU"`` scenario active. First of all, make
sure you have registered the TUFLOW binary folder as described in the previous example (:ref:`setting_up_tuflow_binary_folder`).
Then we can tell pytuflow which scenario to run by passing the scenario name as a parameter to the run context method:

.. code-block:: pycon

    >>> tcf_run = tcf.context('-s1 GPU')
    >>> proc = tcf_run.run('2025.1.2')
    >>> proc.wait()  # Wait for the model to finish running


Build State and Run State
-------------------------

It is worth quickly describing how ``pytuflow`` handles TUFLOW's capability to run different
scenarios and events. Pytuflow is made up of three main building blocks:

1. **Control Files** - e.g. TCF, TBC, TGC, etc.
2. **Databases** - e.g. bc_dbase, materials file, soils file, etc
3. **Inputs** - e.g. the individual commands within a control file, such as ``Solution Scheme == HPC``

Each of these building block classes has a "build state" and a "run state". The build state is when the model
is being constructed and modified. The model appears as it would do in a text editor where the user can see
the different scenarios and events. The run state is when the model has been resolved down into a single
simulation event, which is how TUFLOW sees the model when it is run.

The key differences between the build state and run state are:

- The build state can be edited and modified, while the run state is a resolved version of the model and is not editable.
- The run state has more information about the model for a given event, and all the inputs are resolved. This means
  that some properties of the model, such as the output name, can be accessed from the run state but not from the build state.

The run state can be created by calling the :meth:`context()<pytuflow.TCF.context>` method from a build state object. Each build state object
has this method, and it will return a run state object that is specific to a given set of scenarios and events. Quite often
the same methods will be available for both the build state and run state instances. An example of this is the
:meth:`find_input()<pytuflow.TCF.find_input>` method. You can call this method to find all ``2d_zsh`` inputs in the
model

.. code-block:: pycon

    >>> tcf.find_input('2d_zsh')

Or, if you want to check what inputs are active in a given scenario, you can first create a run context:

.. code-block:: pycon

    >>> tcf.context('-s DEV01').find_input('2d_zsh')

.. _adding_else_if_else_pause_commands:

Adding "Else If", "Else", and "Pause" Commands
----------------------------------------------

More complex flow control commands can be added by adding "Else If" and "Else" blocks to the model. Following
on with the above model, we can add an explicit scenario for using ``"CPU"`` hardware, and a "Pause" command
that will catch situations where neither the ``"GPU"`` nor ``"CPU"`` scenarios are active:

.. code-block:: pycon

    >>> cpu_inp = tcf.insert_input(gpu_inp, 'Hardware == CPU', after=True)
    >>> cpu_inp.scope = [Scope('Scenario', '!GPU'), Scope('Scenario', 'CPU')]

    >>> pause_inp = tcf.insert_input(cpu_inp, 'Pause == No hardware scenario specified', after=True)
    >>> pause_inp.scope = [Scope('Scenario', '!GPU'), Scope('Scenario', '!CPU')]

In the above example, we:

1. Create a new input for the CPU hardware option after the ``Hardware == GPU`` command
   using the :meth:`insert_input()<pytuflow.TCF.insert_input>` method. This method returns the new input instance, which
   we can use to set the input's scope.
2. We set the scope for the new input to not be active when the ``"GPU"`` scenario is active
   (by negating the scenario with ``!``) and when the ``"CPU"`` scenario is active.
3. We add a new pause command after the new ``Hardware == CPU`` command using the same
   :meth:`insert_input()<pytuflow.TCF.insert_input` method.
4. We set the scope for the pause command to be active when neither the ``"GPU"`` nor the ``"CPU"`` scenarios are active,

The negative scenario scopes are important here and are required to trigger "Else If" and "Else" blocks.
Note, the order of the scope in the list is also important.

We can preview our changes to the TCF by calling the :meth:`preview()<pytuflow.TCF.preview>` method:

.. code-block:: pycon

    >>> tcf.preview()
    ! TUFLOW CONTROL FILE (.TCF) defines the model simulation parameters and directs input from other data sources

    ! MODEL INITIALISATION
    Tutorial Model == ON                                ! This command allows for this model to be simulated without a TUFLOW licence
    GIS Format == SHP									! Specify SHP as the output format for all GIS files
    SHP Projection == ..\model\gis\projection.prj       ! Sets the GIS projection for the TUFLOW Model
    TIF Projection == ..\model\grid\DEM_SI_Unit_01.tif  ! Sets the GIS projection for the ouput grid files
    !Write Empty GIS Files == ..\model\gis\empty        ! This command is commented out. It is only needed for the project establishment

    ! SOLUTION SCHEME
    Solution Scheme == HPC								! Heavily Parallelised Compute, uses adaptive timestepping
    If Scenario == GPU
        Hardware == GPU										! Comment out if GPU card is not available or replace with "Hardware == CPU"
    Else If Scenario == CPU
        Hardware == CPU
    Else
        Pause == No hardware scenario specified
    End If
    SGS == ON											! Switches on Sub-Grid Sampling
    SGS Sample Target Distance == 0.5					! Sets SGS Sample Target Distance to 0.5m

    ! MODEL INPUTS
    Geometry Control File == ..\model\EG00_001.tgc		! Reference the TUFLOW Geometry Control File
    BC Control File == ..\model\EG00_001.tbc			! Reference the TUFLOW Boundary Conditions Control File
    BC Database == ..\bc_dbase\bc_dbase_EG00_001.csv	! Reference the Boundary Conditions Database
    Read Materials File == ..\model\materials.csv  		! Reference the Materials Definition File
    Set IWL == 36.5										! Define an initial 2D water level at start of simulation

    Timestep == 1
    Start Time == 0
    End Time == 3

    ! OUTPUT FOLDERS
    Log Folder == log		  							! Redirects log output files log folder
    Output Folder == ..\results\EG00\	  				! Specifies the location of the 2D result files
    Write Check Files == ..\check\EG00\		  			! Specifies the location of the 2D check files and prefixes them with the .tcf filename

    Map Output Format == XMDF TIF						! Result file types
    Map Output Data Types == h V d z0					! Specify the output data types
    TIF Map Output Data Types == h						! Specify the output data types for TIF Format
    Map Output Interval == 300  						! Outputs map data every 300 seconds
    TIF Map Output Interval == 0						! Outputs only maximums for grids

It's also possible to create a scope variable and to call the :meth:`Scope.as_neg()<pytuflow.Scope.as_neg>` method to
accomplish the same thing:

.. code-block:: pycon

    >>> gpu_scope = Scope('Scenario', 'GPU')
    >>> cpu_scope = Scope('Scenario', 'CPU')

    >>> gpu_scenario = [gpu_scope]
    >>> cpu_scenario = [gpu_scope.as_neg(), cpu_scope]
    >>> no_hardware_scenario = [gpu_scope.as_neg(), cpu_scope.as_neg()]

    >>> no_hardware_scenario
    [<ScenarioScope> !GPU, <ScenarioScope> !CPU]

Finally, it's worth checking what happens when we try and run the model without any scenarios active. First, we have
to write the changes to disk, in this instance we can let the file name auto increment to run ``002``. We can
do this by passing in ``"auto"`` to the ``inc`` parameter, or not passing in any argument as ``"auto"`` is
the default. Then after  tcf has been written we can try and create the run context:

.. code-block:: pycon

    >>> tcf.write()
    <TuflowControlFile> EG00_~s1~_002.tcf

    >>> tcf_run = tcf.context()
    Traceback (most recent call last):
      ...
    ValueError: Pause command encountered: No hardware scenario specified

In the above example, an exception is raised when we try and create the run context. This is because the
pause command is active in the chosen scenario (or lack thereof). The pause message is printed as part of the
exception message.

Note, the run context will look for default scenarios (e.g. ``"Model Scenarios == GPU"``) if no scenarios arguments are
passed in.

