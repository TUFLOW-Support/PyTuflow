Pytuflow Cookbook
=================

The below are a series of examples to demonstrate how to use the :code:`pytuflow` package. For basic usage, see the
:ref:`quickstart` guide.

TUFLOW Model Files
------------------

The below are examples of using the TUFLOW Model Files module (tmf) to read, write, and run TUFLOW models.

Reading and Querying a TUFLOW Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The below examples show off a simple case of viewing all the inputs (i.e. commands) in a TUFLOW model and in individual
control files.

The example below uses the example model :code:`EG00_001`
from the `TUFLOW example model dataset <https://wiki.tuflow.com/TUFLOW_Example_Models#Multiple_Domain_Model_Design>`_.

.. code-block:: python

   from pytuflow.tmf import TCF


   tcf = TCF('path/to/EG00_001.tcf')

   # convenience methods to get other control files
   tgc = tcf.tgc()
   tbc - tcf.tbc()
   ecf = tcf.ecf()
   bc_dbase = tcf.bc_dbase()
   mat = tcf.mat()
   # ... etc

Inputs can be accessed using the :meth:`get_inputs() <pytuflow.tmf.TCF.get_inputs>` method. This method returns a list of
:class:`Input <pytuflow.tmf.Input>` objects. By default the :meth:`get_inputs() <pytuflow.tmf.TCF.get_inputs>` method
is recursive by default, meaning that it will also return inputs from any control files that are read in from the TCF.

.. code-block:: python

   >>> for inp in tcf.get_inputs():
   ...    inp
   <SettingInput> GIS Format == GPKG
   <FileInput> SHP Projection == ..\model\gis\projection.prj
   <FileInput> TIF Projection == ..\model\grid\DEM_SI_Unit_01.tif
   <SettingInput> Solution Scheme == HPC
   <SettingInput> Hardware == GPU
   <ControlFileInput> Geometry Control File == ..\model\EG00_001.tgc
   <GisInput> Read GIS Location == gis\2d_loc_EG00_001_L.shp
   <SettingInput> Cell Size == 5.0
   <SettingInput> Grid Size (X,Y) == (850.0, 1000.0)
   <SettingInput> Set Code == 0
   <GisInput> Read GIS Code == gis\2d_code_EG00_001_R.shp
   <SettingInput> Set Zpts == 100.0
   <GridInput> Read GRID Zpts == grid\DEM_SI_Unit_01.tif
   <SettingInput> Set Mat == 1
   <GisInput> Read GIS Mat == gis\2d_mat_EG00_001_R.shp
   <ControlFileInput> BC Control File == ..\model\EG00_001.tbc
   <GisInput> Read GIS BC == gis\2d_bc_EG00_001_L.shp
   <DatabaseInput> BC Database == ..\bc_dbase\bc_dbase_EG00_001.csv
   <DatabaseInput> Read Materials File == ..\model\materials.csv
   <SettingInput> Set IWL == 36.5
   <SettingInput> Timestep == 1.0
   <SettingInput> Timestep Maximum == 2.5
   <SettingInput> Start Time == 0.0
   <SettingInput> End Time == 3.0
   <SettingInput> Log Folder == log
   <SettingInput> Output Folder == ..\results\EG00\
   <SettingInput> Write Check Files == ..\check\EG00\
   <SettingInput> Map Output Format == XMDF TIF
   <SettingInput> Map Output Data Types == d h V
   <SettingInput> Map Output Interval == 300.0
   <SettingInput> TIF Map Output Interval == 0.0

Recursion can be turned off by setting the :code:`recursive` argument to :code:`False`.

.. code-block:: python

   >>> for inp in tcf.get_inputs(recursive=False):
   ...     inp
   <SettingInput> GIS Format == GPKG
   <FileInput> SHP Projection == ..\model\gis\projection.prj
   <FileInput> TIF Projection == ..\model\grid\DEM_SI_Unit_01.tif
   <SettingInput> Solution Scheme == HPC
   <SettingInput> Hardware == GPU
   <ControlFileInput> Geometry Control File == ..\model\EG00_001.tgc
   <ControlFileInput> BC Control File == ..\model\EG00_001.tbc
   <DatabaseInput> BC Database == ..\bc_dbase\bc_dbase_EG00_001.csv
   <DatabaseInput> Read Materials File == ..\model\materials.csv
   <SettingInput> Set IWL == 36.5
   <SettingInput> Timestep == 1.0
   <SettingInput> Timestep Maximum == 2.5
   <SettingInput> Start Time == 0.0
   <SettingInput> End Time == 3.0
   <SettingInput> Log Folder == log
   <SettingInput> Output Folder == ..\results\EG00\
   <SettingInput> Write Check Files == ..\check\EG00\
   <SettingInput> Map Output Format == XMDF TIF
   <SettingInput> Map Output Data Types == d h V
   <SettingInput> Map Output Interval == 300.0
   <SettingInput> TIF Map Output Interval == 0.0

The same method can be used to get the inputs from other control files. In these cases, the :code:`recursive` argument
doesn't make much difference since no control files are read in from anything other than the :code:`TCF`.

.. note::

   :code:`TRD` files are included in whatever control file they are referenced in and recursion make
   no difference when retrieving them.

.. code-block:: python

   >>> for inp in tcf.tgc().get_inputs():
   ...     inp
   <GisInput> Read GIS Location == gis\2d_loc_EG00_001_L.shp
   <SettingInput> Cell Size == 5.0
   <SettingInput> Grid Size (X,Y) == (850.0, 1000.0)
   <SettingInput> Set Code == 0
   <GisInput> Read GIS Code == gis\2d_code_EG00_001_R.shp
   <SettingInput> Set Zpts == 100.0
   <GridInput> Read GRID Zpts == grid\DEM_SI_Unit_01.tif
   <SettingInput> Set Mat == 1
   <GisInput> Read GIS Mat == gis\2d_mat_EG00_001_R.shp

To find specific inputs, the :meth:`find_input() <pytuflow.tmf.TCF.find_input>` method can be used. This method returns
a list of inputs found in the TCF (recursive by default) that match the search parameters.

The simplest method is to pass in a string and that string will be matched against the entire input string
(left-hand side and right-hand side of the command). The search is case insensitive.

.. code-block:: python

   >>> for inp in tcf.find_input('read grid zpts'):
   ...     inp
   <GridInput> Read GRID Zpts == grid\DEM_SI_Unit_01.tif

The search string can be specific to a given side of the input by using the :code:`command` or :code:`value` arguments
for the left-hand side and right-hand side of the command respectively.

.. code-block:: python

   >>> for inp in tcf.find_input(command='code'):
   ...     inp
   <SettingInput> Set Code == 0
   <GisInput> Read GIS Code == gis\2d_code_EG00_001_R.shp
   >>> for inp in tcf.find_input(value='001'):
   ...     inp
   <ControlFileInput> Geometry Control File == ..\model\EG00_001.tgc
   <GisInput> Read GIS Location == gis\2d_loc_EG00_001_L.shp
   <GisInput> Read GIS Code == gis\2d_code_EG00_001_R.shp
   <GisInput> Read GIS Mat == gis\2d_mat_EG00_001_R.shp
   <ControlFileInput> BC Control File == ..\model\EG00_001.tbc
   <GisInput> Read GIS BC == gis\2d_bc_EG00_001_L.shp
   <DatabaseInput> BC Database == ..\bc_dbase\bc_dbase_EG00_001.csv

The comments of an input can also be searched by setting the :code:`comments` argument to :code:`True`. This will search the comment
of an input and also include inputs that are purely comment lines in the control file. This allows for finding inputs that have been commented out
(and this can be uncommented as shown in :ref:`Update an Input <updating_an_input>`). Searching comments can also be useful if key
searchable strings have been added to the comments.

.. code-block:: python

   >>> for inp in tcf.find_input('Sub-Grid Sampling', comments=True):
   ...     inp
   <SettingInput> SGS == ON

The search can also use regular expressions by setting the :code:`regex` argument to :code:`True`. If regex is used,
the search string must be a valid regex string and regex flags can be passed in using the :code:`regex_flags` argument.
When using regex, the :code:`command` and :code:`value` arguments can still be used to search specific sides of the input.

Example, finding all inputs that have :code:`1d_` or :code:`2d_` in the right-hand side of the command.

.. code-block:: python

   >>> import re
   >>> for inp in tcf.find_input(value=r'[12]d_', regex=True, regex_flags=re.IGNORECASE):
   ...     inp
   <GisInput> Read GIS Location == gis\2d_loc_EG00_001_L.shp
   <GisInput> Read GIS Code == gis\2d_code_EG00_001_R.shp
   <GisInput> Read GIS Mat == gis\2d_mat_EG00_001_R.shp
   <GisInput> Read GIS BC == gis\2d_bc_EG00_001_L.shp

Inputs have various properties such as associated files, GIS geometry types, scope, and whether any files are missing.
The available properties are dependent on the input type. E.g. a :class:`FileInput <pytuflow.tmf.FileInput>` will have
a :code:`files` property but a :class:`SettingInput <pytuflow.tmf.SettingInput>` will not.

It's possible to use search the inputs and filter by their properties using the :code:`tags` argument. The :code:`tags`
argument is a list of tuples with a :code:`key` and :code:`value` pair. The :code:`key` is the property name and the
:code:`value` is the value to compare against.

Example, using the :code:`tags` argument, we can find all inputs that are missing files (i.e. the file does not exist).
In this case, nothing is printed as all files exist.

.. code-block:: python

   >>> for inp in tcf.find_input(tags=[('missing_files', True)]):
   ...     inp

For basic filtering, the :code:`tags` argument can be simplified:

.. code-block:: python

   >>> for inp in tcf.find_input(tags='missing_files'):
   ...     inp

When just the tag :code:`key` is passed in, the value is assumed to be :code:`True`. If just one tag is passed in, it
does not require to be in a list. If multiple tags are passed in, then it must be provided in a list of tuples.

Another example of using tags is to find all GIS inputs that use (only) a line geometry type. In this example, the
:code:`geoms` property is used, which is a list of geometry types found in the GIS file(s). The geometry types
are recorded as their OGR type e.g. line = ogr.wkbLineString (which is an enumerator which equals 2). The geometries are
found by opening the GIS file(s) and reading the geometry types so GDAL is required to be present for this property
to be populated.

For the following examples, we'll switch to using :code:`EG07_001.tcf` from the example model dataset.

.. code-block:: python

   >>> tcf = TCF('path/to/EG07_001.tcf')
   >>> for inp in tcf.find_input(tags=('geoms', [2])):
   ...     inp
   <GisInput> Read GIS Location == gis\2d_loc_EG00_001_L.shp
   <GisInput> Read GIS BC == gis\2d_bc_EG00_001_L.shp

The above example is limited to GIS inputs that only have line geometries. But it's possible for certain inputs
to contain a combination of geometry types. We can expand the :code:`tags` value to use a callable function rather
than exact value. The callable function should take one input (the property value) and return a boolean. In this case
the callable will take a list argument, so we can check whether the value 2 is in the list.

.. code-block:: python

   >>> for inp in tcf.find_input(tags=('geoms', lambda x: 2 in x)):
   ...     inp
   <GisInput> Read GIS Location == gis\2d_loc_EG00_001_L.shp
   <GisInput> Read GIS Z Shape == gis\2d_zsh_EG00_Rd_Crest_001_L.shp | gis\2d_zsh_EG00_Rd_Crest_001_P.shp
   <GisInput> Read GIS BC == gis\2d_bc_EG00_001_L.shp

A callable function can also be passed in via the :code:`callback` argument. This is useful when wanting to apply
more complex logic to the filtering, or calling methods that are not directly available as a property. A simple
example is to query an inputs scope which can be done via the :meth:`scope() <pytuflow.tmf.Input.scope>` method.
For more information on scope checking, see the section below :ref:`Check Input Scope <checking_scope>`.

Using the following example model: :code:`EG16_~s1~_~s2~_002.tcf`, we can find all inputs that are used within a
:code:`If Scenario == D01` block. As discussed later in the :ref:`Check Input Scope <checking_scope>` section, this isn't a perfect
way of finding inputs for a given scenario due to the way :code:`Else If/Else` logic works and a more robust method
is to use :meth:`context() <pytuflow.tmf.TCF.context>` and check the available inputs. However this is just a
demonstration on the :code:`callback` argument.

.. code-block:: python

   >>> from pytuflow.tmf import Scope
   >>> tcf = TCF('path/to/EG16_~s1~_~s2~_002.tcf')
   >>> for inp in tcf.find_input(callback=lambda x: Scope('scenario', 'D01') in x.scope()):
   ...     inp
   <GisInput> Read GIS Z Shape == gis\2d_zsh_EG07_006_R.shp

To view the inputs in a given scenario/event, use the :meth:`context() <pytuflow.tmf.TCF.context>` method to
resolve the inputs first.

Continuing on from the previous example using :code:`EG16_~s1~_~s2~_002.tcf`, there are two scenario
groups:

* :code:`s1` could be :code:`2.5m` or :code:`5m`
* :code:`s2` could be :code:`EXG`, :code:`D01` or :code:`D02`

Starting with :code:`-s1 5m -s2 D01`:

.. code-block:: python

   >>> tcf = TCF(r'path/to/EG16_~s1~_~s2~_002.tcf')
   >>> for inp in tcf.context('-s1 5m -s2 D01').tgc().get_inputs():
   ...     inp
   <GisInputContext> Read GIS Location == gis\2d_loc_EG00_001_L.shp
   <SettingInputContext> Grid Size (X,Y) == 850, 1000
   <SettingInputContext> Cell Size == 5.0
   <SettingInputContext> Set Code == 0
   <GisInputContext> Read GIS Code == gis\2d_code_EG00_001_R.shp
   <SettingInputContext> Set Zpts == 100.0
   <GridInputContext> Read GRID Zpts == grid\DEM_SI_Unit_01.tif
   <GisInputContext> Read GIS Z Shape == gis\2d_zsh_EG00_Rd_Crest_001_L.shp | gis\2d_zsh_EG00_Rd_Crest_001_P.shp
   <SettingInputContext> Set Mat == 1
   <GisInputContext> Read GIS Mat == gis\2d_mat_EG00_001_R.shp
   <GisInputContext> Read GIS Z Shape == gis\2d_zsh_EG07_006_R.shp

The output above shows that the :code:`Cell Size` input is resolved to :code:`Cell Size == 5.0`. And the last input
has been resolved to :code:`Read GIS Z Shape == gis\\2d_zsh_EG07_006_R.shp`.

Trying now with :code:`-s1 2.5m -s2 D02`:

.. code-block:: python

   >>> for inp in tcf.context('-s1 2.5m -s2 D02').tgc().get_inputs():
   ...     inp
   <GisInputContext> Read GIS Location == gis\2d_loc_EG00_001_L.shp
   <SettingInputContext> Grid Size (X,Y) == 850, 1000
   <SettingInputContext> Cell Size == 2.5
   <SettingInputContext> Set Code == 0
   <GisInputContext> Read GIS Code == gis\2d_code_EG00_001_R.shp
   <SettingInputContext> Set Zpts == 100.0
   <GridInputContext> Read GRID Zpts == grid\DEM_SI_Unit_01.tif
   <GisInputContext> Read GIS Z Shape == gis\2d_zsh_EG00_Rd_Crest_001_L.shp | gis\2d_zsh_EG00_Rd_Crest_001_P.shp
   <SettingInputContext> Set Mat == 1
   <GisInputContext> Read GIS Mat == gis\2d_mat_EG00_001_R.shp
   <GisInputContext> Create TIN Zpts == gis\2d_ztin_EG07_010_R.shp | gis\2d_ztin_EG07_011_L.shp | gis\2d_ztin_EG07_011_P.shp

This time :code:`Cell Size` input is resolved to :code:`Cell Size == 2.5`. And the last input has been resolved to
:code:`Read GIS Z Shape == gis\\2d_ztin_EG07_010_R.shp | gis\\2d_ztin_EG07_011_L.shp | gis\\2d_ztin_EG07_011_P.shp`.

.. note::

   It's possible to call the :meth:`context() <pytuflow.tmf.TCF.context>` method on the :class:`TGC <pytuflow.tmf.TGC>`
   class to resolve inputs in the TGC file
   e.g. :code:`tcf.tgc().context('-s1 5m -s2 D01').get_inputs()`
   however this could skip important steps that are required to resolve
   the scope that need to be obtained from the TCF (e.g. event definitions found in the TEF and any other variables set from
   the TCF using :code:`Set Variable ==`).

Each input has a unique ID which can be used to track the input through the model using
the :meth:`input() <pytuflow.tmf.TCF.input>` method.

Continuing from the previous example using :code:`EG16_~s1~_~s2~_002.tcf`, we can check if an input is present in
different scenario combinations. In this case, we expect that the :code:`Create TIN Zpts` input is only present in
when scenario :code:`D02` is active.

.. code-block:: python

   >>> inp = tcf.find_input('create tin zpts')[0]
   >>> print(inp.uuid)
   5ee25899-76f4-4909-8b5d-14060260e28e
   >>> tcf_run = tcf.context('-s1 5m -s2 D02')
   >>> inp_run = tcf_run.input(inp.uuid)
   >>> print(inp_run)
   Create TIN Zpts == gis\2d_ztin_EG07_010_R.shp | gis\2d_ztin_EG07_011_L.shp | gis\2d_ztin_EG07_011_P.shp
   >>> tcf_run = tcf.context('-s1 5m -s2 D01')
   >>> inp_run = tcf_run.input(inp.uuid)
   None

Copy TUFLOW Input Files
~~~~~~~~~~~~~~~~~~~~~~~

The below example shows off how to copy all the files from a model into a given location. There are already methods
of doing this without requiring custom coding (e.g. using the package model functionality that TUFLOW provides).
The purpose of this example is to showcase the process and can be expanded on with more complex logic for custom tasks.

.. code-block:: python

   from pytuflow.tmf import TCF
   from shutil import copy, copyfile
   from pathlib import Path


   DEST = Path('path/to/destination/folder')

   tcf = TCF('path/to/model.tcf')
   root = tcf.path.parents[1]  # assumes standard directory structure e.g. 'TUFLOW/runs/EG00_001.tcf'

   copied_files = []  # record copied files so don't copy the same file twice

   # copy the TCF itself
   relpath = tcf.path.relative_to(root)
   dest = DEST / relpath
   if not dest.parent.exists():
       dest.parent.mkdir(parents=True)
   _ = copyfile(tcf.path, dest)
   copied_files.append(dest)

   for file in tcf.get_files():
       # get_files() will expand any wildcards/variables
       # found in any input references
       # e.g. Read GIS Code == 2d_code_<<~s1~>>_R.shp
       # will find all files that match the pattern
       # likewise, in the bc_dbase, event variables are expanded
       # if a TEF is found.

       # The return from get_files() are TuflowPath objects
       # which is an extension of the Path class to handle GPKG inputs
       # GIS files returned from this method are always
       # shown as 'db >> lyr' regardless of GIS format
       # To get the file without the 'lyr' part we can use the 'dbpath' property
       fpath = file.dbpath

       # replicate folder structure
       relpath = fpath.relative_to(root)
       dest = DEST / relpath
       if not dest.parent.exists():
           dest.parent.mkdir(parents=True)

       # check if the file has already been copied
       if dest in copied_files:
           continue
       copied_files.append(dest)

       if not fpath.exists():
           print('File does not exist:', fpath)  # log this
           continue

       if fpath.suffix.upper() == '.SHP':
           # make sure to copy all associated files with a shapefile
           for assoc_file in fpath.parent.glob(f'{fpath.stem}.*'):
               _ = copy(assoc_file, dest.parent)
       else:
           _ = copyfile(fpath, dest)

It can be useful to copy specific files from a model, which can be done by filtering the inputs and using
:meth:`find_input() <pytuflow.tmf.TCF.find_input>` rather than :meth:`get_files() <pytuflow.tmf.TCF.get_files>`.

A specific scenario/event combination can also be copied using the :meth:`context() <pytuflow.tmf.TCF.context>` method
to resolve the inputs first e.g. :code:`for file in tcf.context('-s1 5m -s2 D01').get_files():...`.


.. _checking_scope:

Check Input Scope
~~~~~~~~~~~~~~~~~

This example shows how to inspect and check input scope. Scope is assigned to an input depending on where it is
in the control file. For example, inputs within an :code:`If Scenario/Event` block will have a :code:`Scenario` or
:code:`Event` scope. Other example scopes include :code:`OneDim` if the input is within a :code:`Start 1D Domain` block,
:code:`EventVariable` if the input is within a :code:`Define Event` block, and :code:`Global` if the input is not
within any specific block.

.. code-block:: python

   from pytuflow.tmf import TCF, Scope, Context


   # consider the following inputs in a control file
   # Set Zpts == 100
   # If Scenario == DEV
   #     Read Grid Zpts == DEV.tif
   # Else
   #     Read Grid Zpts == EXG.tif
   # EndIf

    tcf = TCF('path/to/model.tcf')
    for inp in tcf.get_inputs():
         print(inp, '; Scope:', inp.scope())
    # >>> Set Zpts == 100; Scope: [<GlobalScope>]
    # >>> Read Grid Zpts == DEV.tif; Scope: [<ScenarioScope> DEV]
    # >>> Read Grid Zpts == EXG.tif; Scope: [<ScenarioScope> ELSE]

    # by default, any inputs within an ELSE block will be given an 'Else' scope
    # this can be changed to show more detailed information i.e. what is required to reach the ELSE block
    # e.g. the Scope names will be shown with an exclamation mark (!) at the front to denote that the input
    # isn't a given scenario(s) to reach the ELSE block
    for inp in tcf.get_inputs():
        print(inp, '; Scope:', inp.scope(else_=False))
    # >>> Set Zpts == 100; Scope: [<GlobalScope>]
    # >>> Read Grid Zpts == DEV.tif; Scope: [<ScenarioScope> DEV]
    # >>> Read Grid Zpts == EXG.tif; Scope: [<ScenarioScope> !DEV]

    # This is also true for 'Else If' blocks. To see the full details, the else_ parameter must be set to False

    # to check an input's scope you can use the native '==' operator
    inp = tcf.find_input('Read Grid Zpts == DEV.tif')[0]
    scope = inp.scope()[0]
    print(scope)
    # >>> <ScenarioScope> DEV
    print(scope == Scope('Scenario', 'DEV'))
    # >>> True
    print(scope == Scope('Scenario'))
    # >>> True
    print(scope == Scope('Scenario', 'EXG'))
    # >>> False
    print(scope == Scope('Global'))
    # >>> False

    # The returned ScopeList object from input.scope() can also be used to check for scope
    print(Scope('Scenario', 'DEV') in inp.scope())
    # >>> True
    # This is true even if the input has multiple scenario options
    # e.g.
    # If Scenario == D01 | D02
    #    Read Grid Zpts == DEV.tif
    # End if
    print(inp.scope())
    # >>> [<ScenarioScope> D01 | D02]
    print(Scope('Scenario', 'D01') in inp.scope())
    # >>> True
    # It will also return True in nested IF statements
    # e.g.
    # If Scenario == D01 | D02
    #     If Scenario == D03
    #         Read Grid Zpts == DEV.tif
    #     End If
    # End If
    print(inp.scope())
    # >>> [<ScenarioScope> D01 | D02, <ScenarioScope> D03]
    print(Scope('Scenario', 'D03'), inp.scope())
    # >>> True
    print(Scope('Scenario', 'D02'), inp.scope())
    # >>> True

    # Be careful when using the above method to check scope as the return does not necessarily indicate whether
    # a given input will be included in a given model run. To assess this properly, a context object should be used.
    # This can be done by passing in the context to the TCF with the context() method, or individually to an input
    # by initialising the Context class manually
    ctx = Context(['-s1 D02 -s2 D03'])
    print(ctx.in_context_by_scope(inp.scope(else_=False)))
    # >>> True
    ctx = Context(['-s1 D01 -s2 D02'])
    print(ctx.in_context_by_scope(inp.scope(else_=False)))
    # >>> False


Run a TUFLOW Model
~~~~~~~~~~~~~~~~~~

The below example demonstrates how to how to use the :meth:`run() <pytuflow.tmf.TCFRunState.run>` method
a TUFLOW model using the :code:`pytuflow` package.

.. code-block:: python

   from pytuflow.tmf import TCF


   tcf = TCF('path/to/model.tcf')

   # context() method must be called before running the model. The arguments passed into context() are the
   # scenario/event arguments that would be passed via a batch file. If there are no scenario/event arguments, then
   # context() must still be called with no arguments.
   proc = tcf.context().run('path/to/TUFLOW_iSP_w64.exe')

   # or to run with some scenarios
   proc = tcf.context('-s1 HPC -s2 GPU').run('path/to/TUFLOW_iSP_w64.exe')

   # the return from the run() method is a subprocess.Popen object which can be used to monitor the process
   # e.g. to check or wait for the run to finish
   if proc.poll() is None:
       # still running
       continue
   # wait for the run to finish
   proc.wait()

   # precision can be changed using the prec argument
   proc = tcf.context().run('path/to/TUFLOW_iSP_w64.exe', prec='dp')  # single precision is default

   # additional TUFLOW run arguments can be passed using add_tf_flags
   proc = tcf.context().run('path/to/TUFLOW_iSP_w64.exe', add_tf_flags=['-t', '-x'])

   # additional subprocess.Popen arguments can be passed in via the run() method as keyword arguments
   proc = tcf.context().run('path/to/TUFLOW_iSP_w64.exe', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

   # TUFLOW executables can be registered either by registering the executable path directly or by registering
   # a folder containing many different TUFLOW releases.
   # e.g. register a specific version
   from pytuflow.utils.tf import register_tuflow_binary, register_tuflow_binary_folder
   register_tuflow_binary('2023-03-AF', 'path/to/2023-03-AF/TUFLOW_iSP_w64.exe')

   # now to run this version, then the version name can be passed inplace of the executable path
   proc = tcf.context().run('2023-03-AF')

   # a even more useful method is to register a folder containing multiple TUFLOW releases
   # e.g. consider the following folder structure

   # TUFLOW_releases/
   #   |
   #   |-- 2018-03-AE/
   #   |     |
   #   |     |-- TUFLOW_iSP_w64.exe
   #   |
   #   |-- 2020-10-AF/
   #   |     |
   #   |     |-- TUFLOW_iSP_w64.exe
   #   |
   #   |-- 2023-03-AF/
   #   |     |
   #   |     |-- TUFLOW_iSP_w64.exe

   # the 'TUFLOW_releases' folder can be registered and the subdirectories will be scanned for TUFLOW executables.
   # The folder names will be used as the TUFLOW release version name.

   register_tuflow_binary_folder('path/to/TUFLOW_releases')
   proc = tcf.context().run('2020-10-AF')

   # the available TUFLOW versions is updated each time a TUFLOW executable is requested, so new versions can
   # be added to the registered folders without needing to re-register the folder.
   # for this reason it is therefore not recommended to register a network location as
   # this may be a very slow process to update.


Test a TUFLOW Model
~~~~~~~~~~~~~~~~~~~

The below shows an example of how to test a TUFLOW model using the :code:`pytuflow` package. The same ability
to register TUFLOW executables can be used when running the :meth:`run_test() <pytuflow.tmf.TCFRunState.run_test>` method.

.. code-block:: python

   from pytuflow.tmf import TCF


   tcf = TCF('path/to/model.tcf')
   out, err = tcf.context().run_test('2023-03-AF')

   # the return from the run_test() method is a tuple containing stdout and stderr
   # returned from the the subprocess.Popen object.
   # Because the stdout and stderr is piped to the subprocess.Popen object
   # the run_test() method will not produce any console object.

   # to view any errors
   if err:
       for line in err.split('\r\n'):
           print(line

   # to view the output
   for line in out.split('\r\n'):
       print(line)

.. _updating_an_input:

Update an Input
~~~~~~~~~~~~~~~

The below are examples on how to edit an :doc:`input <inp>` in TUFLOW and save the changes.

.. code-block:: python

   from pytuflow.tmf import TCF


   tcf = TCF('path/to/model.tcf')
   inp = tcf.find_input('solution scheme')[0]
   print(inp)
   # >>> Solution Scheme == Classic

   # change the input value (right-hand side of the command)
   inp.update_value('HPC')
   print(inp)
   # >>> Solution Scheme == HPC

   # The change has not been saved. You can check this be querying the 'dirty' attribute
   print(inp.dirty)
   # >>> True
   print(tcf.dirty)
   # >>> True

   # the changes can be saved via the tcf.write() method
   # the 'inc' argument will determine where the new tcf
   # is written to. The options are:
   # - 'inplace' will overwrite the original tcf
   # - 'auto' (default) will save into a new TCF with an auto incremented tcf number
   # - '[user-suffix]' will save into a new TCF with a user suffix e.g. '001' (should be a string)
   tcf.write('inplace')  # save over the original tcf
   print(inp.dirty)
   # >>> False
   print(tcf.dirty)
   # >>> False

   # the input can also have the left-hand side updated using 'update_command()'
   inp = tcf.find_input('gpu solver')[0]
   print(inp)
   # >>> GPU Solver == ON
   # This is an old command that invokes the old GPU Solver
   # this should be updated to 'Solution Scheme == HPC'
   inp.update_command('Solution Scheme')
   inp.update_value('HPC')
   print(inp)
   # >>> Solution Scheme == HPC

   # The entire input can also be updated by setting the underlying 'Command' object.
   # users should be careful when using this as certain settings may be lost
   # if not done properly and can't be reversed using the undo() or reset() methods.
   from pytuflow.tmf import Command
   # get the original input settings - this settings object may contain
   # contextual information which is important to retain
   settings = inp.raw_command_obj().settings
   cmd = Command('Solution Scheme == Classic', settings)
   inp.set_raw_command_obj(cmd)
   print(inp)
   # >>> Solution Scheme == Classic

   # it is also possible to comment out or uncomment commands
   # e.g. to comment out a given input
   inp = tcf.find_input('hardware')[0]
   print(inp)
   # >>> Hardware == GPU
   inp = tcf.comment_out(inp)
   print(inp)
   # >>> ! Hardware == GPU
   # in reverse, to find a commented out command, comments parameter must be set to True
   inp = tcf.find_input('hardware', comments=True)[0]
   print(inp)
   # >>> ! Hardware == GPU
   inp = tcf.uncomment(inp)
   print(inp)
   # >>> Hardware == GPU


Add a New Input
~~~~~~~~~~~~~~~

The below are examples of how to add a new :doc:`input <inp>` to a TUFLOW control file.

.. code-block:: python

   from pytuflow.tmf import TCF


   tcf = TCF('path/to/model.tcf')

   # to add a new input to the end of the control file
   inp = tcf.append_input('Model Scenarios == DEV | 5m')
   print(inp)
   # >>> Model Scenarios == DEV | 5m

   # to add a new input next to an existing input
   inp = tcf.find_input('solution scheme')[0]
   new_inp = tcf.insert_input(inp, 'Hardware == GPU', after=True)

   # GIS inputs can simply reference the GIS file path (relative or absolute path)
   # and the command will be auto generated
   inp = tcf.find_input('set code')[0]
   new_inp = tcf.insert_input(inp, 'path/to/2d_code_R.shp', after=True)
   print(new_inp)
   # >>> Read GIS Code == gis\2d_code_R.shp

   # in this case, the input will be inserted after the 'set code' input
   # in the TGC (even though the method is being called from the TCF)
   # because this is where the reference input is located.
   # append_input() will always add to the control file being called from
   # since there is no reference input.
   # Reference GPKG layers should be done in a similar way as they
   # are done in TUFLOW "database.gpkg >> lyrname" and the command
   # reference will simplify it accordingly. They can also be added
   # by just using they layer name, however it is then up to the user
   # to ensure a spatial database command is present.

   # A list of GIS inputs can also be used
   inp = tcf.find_input('read grid zpts')[0]
   new_inp = tcf.insert_input(inp, ['path/to/2d_zsh_rd_L.shp', 'path/to/2d_zsh_rd_P.shp'], after=True)
   print(new_inp)
   # >>> Read GIS Z Shape == gis\2d_zsh_rd_L.shp | gis\2d_zsh_rd_P.shp

   # An input can be added inside a 'If Scenario' block by giving the input
   # a scope. e.g.
   inp = tcf.find_input('read grid zpts')[0]
   new_inp = tcf.insert_input(inp, 'path/to/2d_zsh_DEV_R.shp', after=True)
   new_inp.set_scope([('Scenario', 'DEV')])

   # the required argument for set_scope() is a list of tuples
   # the second item in the tuple can use a pipe symbol '|'
   # in the same way that TUFLOW uses it to denote multiple options
   # e.g. ('Scenario', 'DEV | EXG')
   # passing in multiple tuples will add nested IF statements

   # when this new input is written to file (or cf.preview() called to print to the console)
   # it will be placed inside the 'If Scenario == DEV' block
   tcf.tgc().preview()


Querying a Database
~~~~~~~~~~~~~~~~~~~

The below are examples of how to query a :class:`database <pytuflow.tmf.Database>` in a TUFLOW control file. For example
getting the boundary time series from a :class:`bc_dbase <pytuflow.tmf.BCDatabase>`

.. code-block:: python

   from pytuflow.tmf import TCF


   tcf = TCF('path/to/model.tcf')
   bc_dbase = tcf.bc_dbase()
   df = bc_dbase.db()  # database.db() returns the Pandas DataFrame

   # if there are no event variables
   bndry = bc_dbase.value('FC01')

   # most likely there will be event variables in the bc_dbase
   # multiple combinations of events can be obtained
   events = {'e1' ['Q100'], 'e2': ['2hr']}
   bndries = bc_dbase.value('FC01', event_db=tcf.event_database(), event_groups=events)

   # if event groups are passed in, then the event_db argument must also be provided
   # the return in this case will be a dictionary containing all event combinations
   # the key is the event name (space delimited event name combinations)
   q100_2hr = bndries['Q100 2hr']

   # alternatively, the inputs can be resolved using context() first
   bc_dbase = tcf.context('-e1 Q100 -e2 2hr').bc_dbase()
   q100_2hr = bc_dbase.value('FC01')


Editing a Database
~~~~~~~~~~~~~~~~~~

Databases are not currently supported for editing. The process of editing them should be done manually via Pandas.

Load Time Series Results
------------------------

The below are examples of loading results with :class:`time series results <pytuflow.results.TimeSeriesResults>`.
This includes:

* :class:`TPC <pytuflow.results.TPC>`
* :class:`GPKG Time Series <pytuflow.results.GPKG_TS>`
* :class:`INFO <pytuflow.results.INFO>`
* :class:`Flood Modeller <pytuflow.results.FM_TS>`

.. code-block:: python

   # to load a TPC result file
   from pytuflow.results import TPC
   res = TPC('path/to/results.tpc')

   # the tpc file path can also be obtained from the TCF class
   from pytuflow.tmf import TCF
   tcf = TCF('path/to/model.tcf')
   tpc = tcf.context().tpc()  # returns file path
   res = TPC(tpc)

   # GPKG time series results (written by TUFLOW-SWMM simulations)
   from pytuflow.results import GPKG_TS
   res = GPKG_TS('path/to/results_TS.gpkg')

   # Flood modeller results requires results (.ZZN or .CSV) and
   # preferably as well as the DAT file
   from pytuflow.results import FM_TS
   res = FM_TS('path/to/model.zzn')
   # providing a dat file will provide node connectivity - allows for long plotting
   res = FM_TS('path/to/exported_model_results.csv', dat='path/to/model.dat')

   # providing a GXY is optional and provides GIS coordinate information
   res = FM_TS('path/to/model.zzn', dat='path/to/model.dat', gxy='path/to/model.gxy')



Plot Time Series Results
~~~~~~~~~~~~~~~~~~~~~~~~

The below are examples of extracting time series results for a given channel/node(s) and result type(s).
The examples below use the :class:`TPC <pytuflow.results.TPC>` class, but the same methods can also be used
for the other result formats.

This example is using example model :code:`EG14_001 - 1D river (1d_nwk), 2D floodplain` from the
`TUFLOW example model dataset <https://wiki.tuflow.com/TUFLOW_Example_Models#Multiple_Domain_Model_Design>`_.

.. code-block:: python

   from pytuflow.results import TPC
   import matplotlib.pyplot as plt


   res = TPC('path/to/results/plot/EG14_001.tpc')
   df = res.time_series('FC01.34', 'Flow')
   print(df.head())
   # Type        Channel
   # Result Type    Flow
   # ID          FC01.34
   # Time (h)
   # 0.000000        0.0
   # 0.016667        0.0
   # 0.033333        0.0
   # 0.050000        0.0
   # 0.066667        0.0

   # Note that the returned pandas DataFrame uses a multi-index column name:
   # Type / Result Type / ID

   # the simplest way to plot the dataframe is to use the built-in plot method
   df.plot()
   plt.show()

   # it's possible to drop column levels to make the DataFrame and plot more readable
   # to drop the 'Channel' level
   df.columns = df.columns.droplevel('Type')
   df.plot()
   plt.show()

   # or to drop the 'Result Type' level as well
   df.columns = df.columns.droplevel(['Type', 'Result Type'])
   df.plot()
   plt.show()

   # the time_series() method is not case sensitive and in a lot of cases
   # short hand versions of the result type is supported
   df = res.time_series('fc01.34', 'q')

   # multiple channels can be queried at once
   df = res.time_series(['FC01.34', 'FC01.33'], 'v')
   print(df.head())
   # Type        Channel
   # Result Type    Flow
   # ID          FC01.34 FC01.33
   # Time (h)
   # 0.000000        0.0     0.0
   # 0.016667        0.0     0.0
   # 0.033333        0.0     0.0
   # 0.050000        0.0     0.0
   # 0.066667        0.0     0.0

   # likewise, multiple result types can be queried at once
   df = res.time_series(['FC01.34', 'FC01.33'], ['v', 'q'])
   print(df.head())
   # Type        Channel
   # Result Type    Flow         Velocity
   # ID          FC01.34 FC01.33  FC01.34 FC01.33
   # Time (h)
   # 0.000000        0.0     0.0      0.0     0.0
   # 0.016667        0.0     0.0      0.0     0.0
   # 0.033333        0.0     0.0      0.0     0.0
   # 0.050000        0.0     0.0      0.0     0.0
   # 0.066667        0.0     0.0      0.0     0.0

   # it's possible to get results across different 'Types'
   # e.g. get the flow in a channel and a level in a node
   df = res.time_series(['FC01.33', 'FC01.33.1'], ['q', 'h'])
   print(df.head())
   # Type        Channel        Node
   # Result Type    Flow Water Level
   # ID          FC01.33   FC01.33.1
   # Time (h)
   # 0.000000        0.0     43.6368
   # 0.016667        0.0     43.6368
   # 0.033333        0.0     43.6368
   # 0.050000        0.0     43.6368
   # 0.066667        0.0     43.6368

   # sometimes the same ID is used across domains
   # e.g.
   # a channel called 'test' and a PO line called 'test'
   df = res.time_series('test', 'q')
   print(df.head())
   # Type        Channel   PO
   # Result Type    Flow Flow
   # ID             test test
   # Time (h)
   # 0.000000        0.0  0.0
   # 0.016667        0.0  0.0
   # 0.033333        0.0  0.0
   # 0.050000        0.0  0.0
   # 0.066667        0.0  0.0

   # it's possible to query a specific instance of 'test' by using the 'domain' argument
   # domain can be '1d', '2d', or '0d' (0d is for reporting locations)
   df = res.time_series('test', 'q', domain='1d')
   print(df.head())
   # Type        Channel
   # Result Type    Flow
   # ID             test
   # Time (h)
   # 0.000000        0.0
   # 0.016667        0.0
   # 0.033333        0.0
   # 0.050000        0.0
   # 0.066667        0.0

   # it's also possible to get all result types and/or all elements
   # by passing in None to the respective arguments
   df = res.time_series('test', None)  # all results for elements with ID 'test'
   print(df.head())
   # Type        Channel                           PO
   # Result Type    Flow Velocity Channel Regime Flow
   # ID             test     test           test test
   # Time (h)
   # 0.000000        0.0      0.0              E  0.0
   # 0.016667        0.0      0.0              E  0.0
   # 0.033333        0.0      0.0              E  0.0
   # 0.050000        0.0      0.0              E  0.0
   # 0.066667        0.0      0.0              E  0.0

   df = res.time_series(None, 'q')  # all flow results
   print(df.head())
   # Type        Channel                                      ...                                                 PO
   # Result Type    Flow                                      ...                                               Flow
   # ID              ds1  ds2  ds3  ds4  ds5 ds_weir FC01.01  ... FC02.04 FC02.05 FC02.06 FC_weir1 RD_weir test test
   # Time (h)                                                 ...
   # 0.000000        0.0  0.0  0.0  0.0  0.0     0.0     0.0  ...     0.0     0.0     0.0      0.0     0.0  0.0  0.0
   # 0.016667        0.0  0.0  0.0  0.0  0.0     0.0     0.0  ...     0.0     0.0     0.0      0.0     0.0  0.0  0.0
   # 0.033333        0.0  0.0  0.0  0.0  0.0     0.0     0.0  ...     0.0     0.0     0.0      0.0     0.0  0.0  0.0
   # 0.050000        0.0  0.0  0.0  0.0  0.0     0.0     0.0  ...     0.0     0.0     0.0      0.0     0.0  0.0  0.0
   # 0.066667        0.0  0.0  0.0  0.0  0.0     0.0     0.0  ...     0.0     0.0     0.0      0.0     0.0  0.0  0.0

   df = res.time_series(None, None)  # everything
   print(df.head())
   # Type        Channel                              ...        Node                                           PO
   # Result Type    Flow                              ... Node Regime                                         Flow
   # ID              ds1  ds2  ds3  ds4  ds5 ds_weir  ...   FC02.02.1 FC02.03.1 FC02.04.1 FC02.05.1 FC02.06.1 test
   # Time (h)                                         ...
   # 0.000000        0.0  0.0  0.0  0.0  0.0     0.0  ...           E         E         E         E         E  0.0
   # 0.016667        0.0  0.0  0.0  0.0  0.0     0.0  ...           E         E         E         E         E  0.0
   # 0.033333        0.0  0.0  0.0  0.0  0.0     0.0  ...           E         E         E         E         E  0.0
   # 0.050000        0.0  0.0  0.0  0.0  0.0     0.0  ...           E         E         E         E         E  0.0
   # 0.066667        0.0  0.0  0.0  0.0  0.0     0.0  ...           E         E         E         E         E  0.0


Plot Long Profile Results
~~~~~~~~~~~~~~~~~~~~~~~~~

The below are examples of plotting long profiles from the results.
The examples below use the :class:`TPC <pytuflow.results.TPC>` class, but the same methods can also be used
for the other result formats.

This example is using example model :code:`EG15_001 - 1D pipe network (1d_nwk), 2D floodplain, 2d sa rf inflow (mm) to 1D pits`
from the `TUFLOW example model dataset <https://wiki.tuflow.com/TUFLOW_Example_Models#Multiple_Domain_Model_Design>`_.

.. code-block:: python

   from pytuflow.results import TPC
   import matplotlib.pyplot as plt
   import pandas as pd


   res = TPC('path/to/results/plot/EG15_001.tpc')
   df = res.long_plot('pipe1', 'h', 1.0)  # starting at pipe1, plot water level at timestep 1.0 hrs
   print(df.head())
   #           Channel   Node  Offset  Water Level
   # Branch ID
   # 0           Pipe1   Pit2     0.0      42.5029
   # 0           Pipe1   Pit3    24.7      42.4952
   # 0           Pipe4   Pit3    24.7      42.4952
   # 0           Pipe4  Pit15    94.2      42.3310
   # 0           Pipe6  Pit15    94.2      42.3310

   # long_plot() returns a pandas DataFrame indexes by Branch ID
   # a branch is a path from the start point to the end point
   # if the channel splits in the downstream direction, then
   # multiple branches will be returned which can contain duplicate
   # channels as other branches.

   # the branches use a zero indexing
   # to get the number of branches
   nbranch = df.index.nunique()
   print(nbranch)
   # >>> 1

   # to focus on a single branch (if multiple branches)
   df = df.loc[0]  # get branch 0 (the first branch)

   # plot the water level at time 1.0
   df.plot(x='Offset', y='Water Level')
   plt.show()

   # another example plotting static results
   df = res.long_plot('pipe1', ['bed level', 'water level max'], -1)  # -1 to denote that static data does not require a timestep
   print(df.head())
   #           Channel   Node  Offset  Bed Level  Water Level Max  Water Level TMax
   # Branch ID
   # 0           Pipe1   Pit2     0.0     41.968          42.5066            0.9198
   # 0           Pipe1   Pit3    24.7     41.849          42.4988            0.9461
   # 0           Pipe4   Pit3    24.7     41.849          42.4988            0.9461
   # 0           Pipe4  Pit15    94.2     41.474          42.3356            0.9509
   # 0           Pipe6  Pit15    94.2     41.474          42.3356            0.9509

   df.plot(x='Offset', y=['Bed Level', 'Water Level Max'])
   plt.show()

   # add pipes
   df = res.long_plot('pipe1', ['bed level', 'pipes', 'water level max'], -1)
   print(df.head())
   #           Channel    Node  Offset  Bed Level  Pipe Obvert  Water Level Max  Water Level TMax
   # Branch ID
   # 0           Pipe1    Pit2     0.0     41.968       42.868          42.5066            0.9198
   # 0           Pipe1    Pit3    24.7     41.849       42.749          42.4988            0.9461
   # 0           Pipe4    Pit3    24.7     41.849       42.749          42.4988            0.9461
   # 0           Pipe4   Pit15    94.2     41.474       42.374          42.3356            0.9509
   # 0           Pipe6   Pit15    94.2     41.474       42.374          42.3356            0.9509
   # 0           Pipe6   Pit14   124.9     41.369       42.269          42.2036            0.9526
   # 0          Pipe15   Pit14   124.9     41.369       42.269          42.2036            0.9526
   # 0          Pipe15   Pit13   135.7     40.500       41.400          41.5868            0.8879
   # 0          Pipe16   Pit13   135.7     40.500       41.400          41.5868            0.8879
   # 0          Pipe16  Node20   208.7     40.050       40.950          40.5982            1.2944

   # to plot the pipes, we'll use the Polygon class from matplotlib
   # this requires a list of (x,y) coordinates to plot the pipe.
   # pytuflow offers a utility to do this conversion from bed level and
   # pipe obverts to a DataFrame containing the pipe coordinates
   from matplotlib.patches import Polygon
   from pytuflow.util.plot_util import long_plot_pipes

   ax = df.plot(x= 'Offset', y=['Bed Level', 'Water Level Max'])
   for pipeid, pipe in long_plot_pipes(df).items():
       ax.add_patch(Polygon(pipe.to_numpy(), facecolor='0.9', edgecolor='0.5', label=pipeid))
   plt.ylim(39.5, 43.5)  # polygons don't affect the auto axis limits so this is required
   plt.show()

   # multiple pipes can be passed in to specify the reach to plot
   df = res.long_plot(['pipe4', 'pipe16'], ['bed level', 'pipes', 'water level max'], -1)
   ax = df.plot(x= 'Offset', y=['Bed Level', 'Water Level Max'])
   for pipeid, pipe in long_plot_pipes(df).items():
        ax.add_patch(Polygon(pipe.to_numpy(), facecolor='0.9', edgecolor='0.5', label=pipeid))
   plt.ylim(39.5, 43.5)  # polygons don't affect the auto axis limits so this is required
   plt.show()

   # and to plot multiple branches
   # pipe16 is downstream of both pipe4 and pipe10
   df = res.long_plot(['pipe10', 'pipe4', 'pipe16'], ['bed level', 'pipes', 'h max'], -1)
   print(df)
   #           Channel    Node  Offset  Bed Level  Pipe Obvert  Water Level Max  Water Level TMax
   # Branch ID
   # 0          Pipe10    Pit7     0.0     41.655       42.555          43.1141            0.8924
   # 0          Pipe10    Pit9    58.4     41.308       42.208          42.9768            0.9083
   # 0          Pipe11    Pit9    58.4     41.308       42.208          42.9768            0.9083
   # 0          Pipe11   Pit10    91.1     41.266       42.166          42.8009            0.9147
   # 0          Pipe13   Pit10    91.1     41.266       42.166          42.8009            0.9147
   # 0          Pipe13   Pit11   112.4     41.160       42.060          42.4539            0.9272
   # 0          Pipe14   Pit11   112.4     41.160       42.060          42.4539            0.9272
   # 0          Pipe14   Pit13   157.4     40.500       41.400          41.5868            0.8879
   # 0          Pipe16   Pit13   157.4     40.500       41.400          41.5868            0.8879
   # 0          Pipe16  Node20   230.4     40.050       40.950          40.5982            1.2944
   # 1           Pipe4    Pit3     0.0     41.849       42.749          42.4988            0.9461
   # 1           Pipe4   Pit15    69.5     41.474       42.374          42.3356            0.9509
   # 1           Pipe6   Pit15    69.5     41.474       42.374          42.3356            0.9509
   # 1           Pipe6   Pit14   100.2     41.369       42.269          42.2036            0.9526
   # 1          Pipe15   Pit14   100.2     41.369       42.269          42.2036            0.9526
   # 1          Pipe15   Pit13   111.0     40.500       41.400          41.5868            0.8879
   # 1          Pipe16   Pit13   111.0     40.500       41.400          41.5868            0.8879
   # 1          Pipe16  Node20   184.0     40.050       40.950          40.5982            1.2944

   ax = None
   end = df['Offset'].max()
   for bid in df.index.unique():
       dfb = df.loc[bid]
       # alter offsets so that the last offsets for each branch aligns
       dif = end - dfb['Offset'].max()
       dfb.loc[:,'Offset'] = dfb['Offset'] + dif
       # plot
       ax = dfb.plot(x='Offset', y=['Bed Level', 'Water Level Max'], ax=ax)
       # pipes
       for pipeid, pipe in long_plot_pipes(dfb).items():
           ax.add_patch(Polygon(pipe.to_numpy(), facecolor='0.9', edgecolor='0.5', label=pipeid))
   plt.show()

   # An example of adding pits to the plot
   df = res.long_plot('pipe1', ['bed level', 'pipes', 'pits'], -1)
   print(df.head())
   #           Channel   Node  Offset  Bed Level  Pipe Obvert  Pit Ground Elevation
   # Branch ID
   # 0           Pipe1   Pit2     0.0     41.968       42.868                43.266
   # 0           Pipe1   Pit3    24.7     41.849       42.749                   NaN
   # 0           Pipe4   Pit3    24.7     41.849       42.749                   NaN
   # 0           Pipe4  Pit15    94.2     41.474       42.374                   NaN
   # 0           Pipe6  Pit15    94.2     41.474       42.374                43.019

   ax = None
   ax = df.plot(x='Offset', y='Bed Level', ax=ax)
   ax = df.plot(x='Offset', y='Pit Ground Elevation', ax=ax, linestyle='none', marker='o')
   for pipeid, pipe in long_plot_pipes(df).items():
        ax.add_patch(Polygon(pipe.to_numpy(), facecolor='0.9', edgecolor='0.5', label=pipeid))
   plt.show()

   # If you want to add labels to the plot
   df = res.long_plot('pipe1', ['bed level', 'pipes', 'pits'], -1)
   ax = None
   ax = df.plot(x='Offset', y='Bed Level', ax=ax, legend=False)
   ax = df.plot(x='Offset', y='Pit Ground Elevation', ax=ax, linestyle='none', marker='o', legend=False)

   # label pits
   pits = df[['Node', 'Offset', 'Pit Ground Elevation']].dropna(how='any')
   for _, pit in pits.iterrows():
       ax.annotate(pit['Node'], xy=pit[['Offset', 'Pit Ground Elevation']].to_numpy(), xytext=(7, 7), textcoords='offset pixels')

   for pipeid, pipe in long_plot_pipes(df).items():
       ax.add_patch(Polygon(pipe, facecolor='0.9', edgecolor='0.5', label=pipeid))

       # label pipe
       x = pipe['x'].mean()
       y = pipe['y'].iloc[:2].mean()
       ax.annotate(pipeid, xy=(x, y), xytext=(0, -50), textcoords='offset pixels',
                   horizontalalignment='center', arrowprops=dict(arrowstyle='->'))

   plt.ylim(39.5, 44)
   plt.show()


