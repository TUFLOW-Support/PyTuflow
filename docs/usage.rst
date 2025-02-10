Usage
=====

.. _installation:

Installation
------------

To use pytuflow, first install it using pip:

.. code-block:: console

   $ pip install pytuflow

Dependencies
------------

Most dependencies are automatically installed when you install pytuflow. The only exception to this is the
GDAL Python bindings, which are required to be installed manually. GDAL isn't necessarily required for all
the functionality of pytuflow, however it is required for certain features.

For Windows, you can download pre-compiled binaries from here: https://github.com/cgohlke/geospatial-wheels/releases.

.. _quickstart:

Quickstart
----------

For more detailed examples, see the :doc:`cookbook` page.

1. Load an existing model via a TCF file:

   .. code-block:: python

      from pytuflow import TCF

      tcf = TCF('path/to/tcf_file.tcf')

2. Run the model:

   .. note::

      Control file classes have two states:

      * :code:`Build state`
      * :code:`Run state`

      The :code:`build state` is how control files are initially loaded and contain information on all inputs i.e. they
      will include a given input even if that input is only used in certain scenarios. The :code:`run state` is how the
      model looks to TUFLOW when you run a model i.e. all the inputs are resolved down to the chosen :code:`events`
      and :code:`scenarios`.

      To convert a :code:`build state` object to a :code:`run state` object, the given :code:`events`
      and :code:`scenarios` are passed using the :code:`context()` method. The :code:`context()` must be called
      prior to running the model, even if no :code:`events` and :code:`scenarios` are passed in.

   .. code-block:: python

      # pass in command line arguments to context() just as you would in a batch file
      # context() is required to be called even if no arguments are needed
      # proc is a subprocess.Popen object
      proc = tcf.context('-s EXG -e 1AEP').run('path/to/TUFLOW_iSP_w64.exe')

3. For easy access to different TUFLOW versions, a folder containing a number of executables can be registered.
   Each TUFLOW version needs to sit within its own subdirectory (the binaries should sit directly within
   these subdirectories) and the directory names should be the same as the
   TUFLOW version name. This only needs to be done once.

   .. code-block:: python

      from pytuflow.util.tf import register_tuflow_binary_folder

      register_tuflow_binary_folder('path/to/tuflow_binaries')

      # run the model with a specific version that exists in the registered folder
      proc = tcf.context('-s EXG -e 1AEP').run('2023-03-AF')

4. Once the model is finished, the time series results can be loaded via the :code:`TPC` class. The tpc file can be obtained
   using the :code:`tpc()` method from the :code:`TCF` class after :code:`context` has been given.

   .. code-block:: python

      from pytuflow import TPC

      fpath = tcf.context('-s EXG -e 1AEP').tpc()
      res = TPC(fpath)

      # extract time series data into a Pandas DataFrame
      df = res.time_series('FC01.1_R', 'q')

5. The model can queried to check for given inputs.

   .. code-block:: python

      # find_input() looks for the given text in the whole command or in given parts of the command (left-hand side / right-hand side)
      # the return is a list of found inputs in order they appear in the control files (an empty list means nothing was found)
      inps = tcf.find_input('Read GIS Z Shape')

6. Depending on the input type, the input will have certain properties to describe the input which can be helpful

   .. code-block:: python

      # get the input object
      inp = inps[0]

      # GIS input - layer count - how many layers are referenced in the input
      layer_count = inp.layer_count

      # GIS input - geometries - a list of different geometry types referenced in the input
      geoms = inp.geoms

      # File Input - check if any of the referenced files don't exist
      missing_files = inp.missing_files

7. Databases can be viewed as a Pandas DataFrame

   .. code-block:: python

      # get the loadedbc_dbase class
      bc_dbase = tcf.bc_dbase()

      # get the bc_dbase as a DataFrame object
      df = bc_dbase.db()

For more examples, see the :doc:`cookbook` page.
