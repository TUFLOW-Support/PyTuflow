.. _tcf_load_and_run:

Load and Run a TUFLOW Model
===========================

The below example shows how to load a TCF, make an edit, save it, and then run the model. The example below
uses ``EG00_001.tcf`` from the `TUFLOW example models <https://wiki.tuflow.com/TUFLOW_Example_Models>`_.

Loading a TUFLOW Control File (TCF)
-----------------------------------

Loading an existing TUFLOW model can be done very simply using the :class:`TCF<pytuflow.TCF>` class.

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG00_001.tcf')

Navigating the TCF can best be done using :meth:`TCF.find_input()<pytuflow.TCF.find_input>`. This method will return a list of inputs
that match the given filter. For example, finding all SGS related commands:

.. code-block:: pycon

    >>> tcf.find_input('sgs')
    [<SettingInput> SGS == ON, <SettingInput> SGS Sample Target Distance == 0.5]

The :class:`TCF<pytuflow.TCF>` class will return all inputs within the model for the given filter, e.g. you can
search for ``"2d_zsh"`` commands and it will return commands from the TUFLOW Geometry Control File (TGC). There are
also some convenience methods that will return the other control file instances if you want to work with them directly:

.. code-block:: pycon

    >>> tgc = tcf.tgc()
    >>> tbc = tcf.tbc()
    >>> bc_dbase = tcf.bc_dbase()
    >>> materials = tcf.mat_file()
    >>> tgc.find_input('2d_mat')
    [<GisInput> Read GIS Mat == gis\2d_mat_EG00_001_R.shp]

Updating a TCF
--------------

Let's update the map output format command to include the ``NC`` format, as this will be useful later for querying
the results in Python. The first step is to find the relevant command, and then we can update it by setting the
right-hand side (RHS) of the command to include ``"NC"``.

.. code-block:: pycon

    >>> inp = tcf.find_input('map output format')[0]
    >>> print(inp)
    Map Output Format == XMDF TIF
    >>> inp.rhs = f'{inp.rhs} NC' # Append NC to the existing RHS
    >>> print(inp)
    Map Output Format == XMDF TIF NC

The change can be checked in the broader TCF by using :meth:`TCF.preview()<pytuflow.TCF.preview>` to
print a preview of the control file to the console:

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
    Hardware == GPU										! Comment out if GPU card is not available or replace with "Hardware == CPU"
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

    Map Output Format == XMDF TIF NC                       ! Result file types
    Map Output Data Types == h V d z0					! Specify the output data types
    TIF Map Output Data Types == h						! Specify the output data types for TIF Format
    Map Output Interval == 300  						! Outputs map data every 300 seconds
    TIF Map Output Interval == 0						! Outputs only maximums for grids

Updating control files like this does not make any changes to the control file on disk until
:meth:`TCF.write()<pytuflow.TCF.write>` is called. But we do need to call :meth:`TCF.write()<pytuflow.TCF.write>`
before we can run the updated model. We can overwrite the existing
TCF file if the ``inc`` parameter is set to ``"inplace"``, however in this case, we will save the modified model
to a new file. Since "EG00_002.tcf" is already present in the example models, we will instead save our changes as
"EG00_001a.tcf".

.. code-block:: pycon

    >>> tcf.write(inc='001a')
    <TuflowControlFile> EG00_001a.tcf

Running the TUFLOW Model
-------------------------

To run the model, it is useful to provide a location where all the TUFLOW executables are located. This
only needs to be done once and can be done by registering a TUFLOW binary folder. The folder structure should
match the below structure, where the folder name is the TUFLOW version number and the TUFLOW executables are located within
that folder:

.. code-block:: text

   /path/to/tuflow/binaries
     ├── 2025.0.0
     │   ├── TUFLOW_iSP_w64.exe
     │   ├── TUFLOW_iDP_w64.exe
     ├── 2025.1.0
     │   ├── TUFLOW_iSP_w64.exe
     │   ├── TUFLOW_iDP_w64.exe
     ├── 2025.1.2
     │   ├── TUFLOW_iSP_w64.exe
     │   ├── TUFLOW_iDP_w64.exe

.. code-block:: pycon

    >>> from pytuflow import register_tuflow_binary_folder
    >>> register_tuflow_binary_folder('/path/to/tuflow/binaries')

Now we can run the model using the :meth:`TCF.context()<pytuflow.TCF.context>` method the TUFLOW version name.
The context method is used to pass in what event and scenario combination we want to run.
An empty context is still required even if there are no events or scenarios to run.

.. code-block:: pycon

    >>> tcf_run = tcf.context()
    >>> proc = tcf_run.run('2025.1.2')
    >>> proc.wait() # Wait for the model to finish running

Interrogating the Results
-------------------------

With the ``tcf_run`` instance, we can also get the output folder and result name. With this, we can access the results:

.. code-block:: pycon

    >>> from pytuflow import XMDF
    >>> xmdf_path = tcf_run.output_folder_2d() / f'{tcf_run.result_name()}.xmdf'
    >>> xmdf = XMDF(xmdf_path)

Currently, the XMDF class requires QGIS Python libraries to extract results (e.g. time series). However,
if the ``netCDF4`` package is installed, we can query some of the header information without QGIS:

.. code-block:: pycon

    >>> xmdf.data_types()
    ['bed level',
     'max depth',
     'max vector velocity',
     'max velocity',
     'max water level',
     'max z0',
     'depth',
     'vector velocity',
     'velocity',
     'water level',
     'z0',
     'tmax water level']
    >>> xmdf.times()
    [0.0,
    0.08333333333333333,
    0.16666666666666666,
    0.25,
    0.3333333333333333,
    0.41666666666666663,
    0.5,
    ...
    2.833333333333333,
    2.9166666666666665,
    3.0]

We added the ``NC`` format to the TCF, so that we could easily query the results in Python:

.. code-block:: pycon

    >>> from pytuflow import NCGrid
    >>> ncgrid_path = tcf_run.output_folder_2d() / f'{tcf_run.result_name()}.nc'
    >>> ncgrid = NCGrid(ncgrid_path)
    >>> nc_grid.data_types()
    ['water level',
     'depth',
     'velocity',
     'z0',
     'max water level',
     'max depth',
     'max velocity',
     'max z0',
     'tmax water level']

We can extract a time series of water level results by using a point location, either in the form of a coordinate tuple
``(x, y)`` (or list of coordinates), or a GIS point file. You will need GDAL Python bindings installed to use the latter
approach. For simplicity, we will use a list coordinate tuples that match the location of the features in the
``2d_po_EG02_010_P.shp`` file that is included as part of the example model dataset. If you have GDAL installed, you
can use a file path reference to the ``TUFLOW/model/gis/2d_po_EG02_010_P.shp`` file instead.

Note, ``pnt1`` starts dry and gets wet later in the simulation, so the first time steps are ``NaN`` to indicate that
the cell is dry.

.. code-block:: pycon

    >>> points = [(293259.140, 6178013.725), (293337.612, 6178286.193)]
    >>> df = ncgrid.time_series(points, 'water level')
    >>> df
    time       water level/pnt1   water level/pnt2
    0.000000                NaN          36.500000
    0.083333                NaN          36.483509
    0.166667                NaN          36.457958
    0.250000                NaN          36.441391
    0.333333                NaN          36.431271
