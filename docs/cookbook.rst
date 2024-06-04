Pytuflow Cookbook
=================

The below are a series of examples to demonstrate how to use the :code:`pytuflow` package. For basic usage, see the
:ref:`quickstart` guide.

TUFLOW Model Files
------------------

The below are examples of using the TUFLOW Model Files module (tmf) to read, write, and run TUFLOW model files.

Read a TUFLOW Control File
~~~~~~~~~~~~~~~~~~~~~~~~~~

This example shows off a simple case of viewing all the inputs (i.e. commands) in a TUFLOW model and in individual
control files.

.. code-block:: python

   from pytuflow.tmf import TCF


   tcf = TCF('path/to/model.tcf')

   # convenience methods to get other control files
   tgc = tcf.tgc()
   tbc - tcf.tbc()
   ecf = tcf.ecf()
   bc_dbase = tcf.bc_dbase()
   mat = tcf.mat()

   # see all inputs
   for inp in tcf.get_inputs():  # by default, get_inputs() is recursive and will step into other control files
       print(inp)

   # see inputs only the the TCF
   for inp in tcf.get_inputs(recursive=False):
       print(inp)

   # see all TGC inputs
   # recursive doesn't make much difference here since no control files are read in from the TGC
   # Note: TRD files will be included in whatever control file they are referenced in and
   #       recursive makes no difference when retrieving them
   for inp in tgc.get_inputs():
       print(inp)

   # to view the inputs in a given scenario/event, use the context() method to resolve the inputs first
   for inp in tcf.context('-s EXG -e 1AEP').get_inputs():
       print(inp)

   # each input is given a unique ID and can be tracked using this ID
   inp = tcf.find_input('Read GIS Network == network.shp')[0]
   print(inp.uuid)
   # >>> UUID('5ee25899-76f4-4909-8b5d-14060260e28e')
   tcf_run = tcf.context('-s EXG -e 1AEP')
   inp_run = tcf_run.input(inp.uuid)
   print(inp_run)
   # >>> Read GIS Network == network.shp

   # check if input is in context
   if not inp_run:  # no input was found with that UUID
       print(f'"{inp}" is not in run context using scenarios -s EXG -e 1AEP')


Copy TUFLOW Input Files
~~~~~~~~~~~~~~~~~~~~~~~

The example below shows various ways to copy model input files to a new location.

.. code-block:: python

   from shutil import copy
   from pytuflow.tmf import TCF


   DEST_FOLDER = 'path/to/destination'

   tcf = TCF('path/to/model.tcf')

   # copy all files to a new location - this snippet will not maintain the model directory structure
   copied_files = []
   for file in tcf.get_files():  # this method is recursive by default
       # The file variable is a TuflowPath object which is an extension of the Path class to handle GPKG inputs
       # GIS files returned from this method are always shown as 'db >> lyr' regardless of GIS format
       # To get the file without the 'lyr' part we can use the dbpath property
       fpath = file.dbpath

       if fpath in copied_files:  # don't copy files twice
           continue
       copied_files.append(fpath)

       if not fpath.exists():
           print('File does not exist:', fpath)  # log this

       if fpath.suffix.upper() == '.SHP':
           # make sure to copy all associated files with a shapefile
           for assoc_file in fpath.parent.glob(f'{fpath.stem}.*'):
               copy(assoc_file, DEST_FOLDER)
       else:
           copy(fpath, DEST_FOLDER)


   # copy files of a specific input type
   copied_files = []
   for inp in tcf.find_input(command='read gis network'):  # find all inputs that have 'read gis network' on the left-hand side of the command
       for file in inp.files:  # loop through files associated with the input
           fpath = file.dbpath
           if fpath in copied_files:
               continue
           copied_files.append(fpath)

           if not fpath.exists():
               print('File does not exist:', fpath)

           if fpath.suffix.upper() == '.SHP':
               for assoc_file in fpath.parent.glob(f'{fpath.stem}.*'):
                   copy(assoc_file, DEST_FOLDER)
           else:
               copy(fpath, DEST_FOLDER)


   # the above routines could also be used for a specific scenario/event combination by using context()
   copied_files = []
   for file in tcf.context('-s EXG -e 1AEP').get_files():
       ...




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

The below are examples of interacting with :class:`time series results <pytuflow.results.TimeSeriesResults>`.
This includes:

* :class:`TPC <pytuflow.results.TPC>`
* :class:`GPKG Time Series <pytuflow.results.GPKG_TS>`
* :class:`INFO <pytuflow.results.INFO>`
* :class:`Flood Modeller <pytuflow.results.FM_TS>`

.. code-block:: python

   from pytuflow.results import TPC


   # to load a TPC result file
   res = TPC('path/to/model.tpc')

   # the tpc file path can also be obtained from the TCF class
   from pytuflow.tmf import TCF
   tcf = TCF('path/to/model.tcf')
   tpc = tcf.context().tpc()  # file path
   res = TPC(tpc)

   # GPKG time series results (written by TUFLOW-SWMM simulations)
   from pytuflow.results import GPKG_TS
   res = GPKG_TS('path/to/model.gpkg')

   # Flood modeller results requires results (.ZZN or .CSV) and
   # preferably as well as the DAT file
   from pytuflow.results import FM_TS
   res = FM_TS('path/to/model.zzn')
   # providing a dat file will provide node connectivity - allows for long plotting
   res = FM_TS('path/to/model.csv', dat='path/to/model.dat')

   # providing a GXY is optional provides GIS coordinate information
   res = FM_TS('path/to/model.csv', dat='path/to/model.dat', gxy='path/to/model.gxy')



Plot Time Series Results
~~~~~~~~~~~~~~~~~~~~~~~~


Plot Long Profile Results
~~~~~~~~~~~~~~~~~~~~~~~~~




