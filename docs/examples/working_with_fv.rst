.. _working_with_fv:

Working with TUFLOW FV
======================

Working with TUFLOW FV control files is very similar to TUFLOW Classic/HPC control files. The main entry point to loading an existing model is via the :class:`~pytuflow.FVC` class, or individual control files can be loaded via the :class:`~pytuflow.FVWQ`, :class:`~pytuflow.FVSed`, and :class:`~pytuflow.FVPTM` classes.

Example, loading a TUFLOW FV model:

.. code-block:: pycon

    >>> from pytuflow import FVC
    >>> fvc = FVC('runs/FLD000_2D_001.fvc')

There are a few TUFLOW FV specifics that apply to the TUFLOW FV control files (listed in the previous paragraph) that are destailed below with examples. Example models/datasets can be found on the `TUFLOW FV Wiki <https://fvwiki.tuflow.com>`_.

Blocks
------

One of the key building blocks of an TUFLOW FV model, and not found within TUFLOW Classic/HPC control files, are "Blocks". An example of common blocks within TUFLOW FV control files are `Material Blocks <https://docs.tuflow.com/fv/manual/2026.0/HD2D-Mate-2.html>`_, `Boundary Condition Blocks <https://docs.tuflow.com/fv/manual/2026.0/HD2D-BC-2.html>`_, and `Output Blocks <https://docs.tuflow.com/fv/manual/2026.0/HD2D-MO-2.html>`_.

PyTUFLOW treats blocks as a subclass of the control file class, rather than scoped input which are how similar input types are treated in Classic control files. Note, this only applies to FV specific blocks and if scenario/event logic, and event definitions (found in the :class:`~pytuflow.TEF`) remain consistent across Classic/FV.

As an example, consider model ``FLD00_2d_001.fvc`` which is the first TUFLOW FV flooding example model. This model has three BC blocks (two inflow boundaries and a downstream boundary). There are several ways we could find the all the ``"BC == .."`` commands (which are the start of the BC Blocks), but the simplest way is to use regex to find these commands exactly:

.. code-block:: pycon

    >>> import re
    >>> from pytuflow import FVC

    >>> fvc = FVC('runs/FLD000_2D_001.fvc')
    >>> bc_inps = fvc.find_input(lhs='^BC$', regex=True, regex_flags=re.IGNORECASE)
    >>> for bc in bc_inps:
    ...     print(bc)
    BC == Q, Upstream, ..\bc_dbase\M01_001.csv
    BC == QN, Downstream, 0.01
    BC == QC, FC04, ..\bc_dbase\M01_001.csv

The inputs listed above are similar to commands like ``Sediment Control File ==`` or in Classic ``Geometry Control File ==``. The input has a reference to any loaded control files, or in this case the input has a reference to the loaded block. Because the blocks inherit from the control file class, it has access to the control file methods e.g. ``find_input`` or ``preview``. Take the first bc block input as an example:

.. code-block:: pycon

    >>> bc = bc_inps[0]
    >>> bc_block = bc.block_control()
    >>> bc_block.preview()
    BC Header == Time_hr,FC01                                                                       ! Columns to read data from for Time (hrs), Flow (m^3/s)
    Sub-Type == 4                                                                                           ! {1} Assign inflows to cells along nodestring, flow weighted according to water depth^1.5

New blocks can easily be added by adding the header command (e.g. ``BC == ...``).  Commands can then be added to the block by getting the :meth:`~pytuflow.BCBlockControlInput.block_control` and adding commands as with normal control files. There is no need to close the block (e.g. ``End BC``), as this will be automatically done by PyTUFLOW when it writes the control file to disk, or preview the control file. In this example the new BC block has been appended at the bottom of the fvc).

.. code-block:: pycon

    >>> new_inp = fvc.append_input(r'BC == QC, FC01, ..\bc_dbase\M01_001.csv')
    >>> new_block = new_inp.block_control()
    >>> new_block.append_input('BC Header == Time_hr,FC01')
    >>> fvc.preview()
    ! TUFLOW FV Floodplain Example Model
    ! Base 2D Flood Model
    Tutorial Model == ON                                                                                    ! {OFF} | ON Enable license free tutorial mode

    !______________________________________________________________________________
    ! GIS INTEGRATION
    GIS Format == SHP                                                                                               ! {MIF} | SHP
    SHP Projection == ..\model\gis\projection.prj                                   ! Projection string used for GIS integration

    !______________________________________________________________________________
    ! SIMULATION CONFIGURATION
    Hardware == CPU                                                                                                 ! {CPU} | GPU
    ! Device ID ==                                                                                                  ! {0} NVIDIA Device ID
    Spherical == 0                                                                                                  ! {0} Cartesian | 1 Long/Lat
    Spatial Order == 1,1                                                                                    ! {1} | 2 Horizontal, {1} | 2 Vertical (Vertical ignored for 2d models)
    Units == Metric                                                                                                 ! {Metric} | Imperial | US Customary | English
    Bottom Drag Model == Manning                                                                    ! {Manning} | ks

    !______________________________________________________________________________
    ! TIME AND TIMESTEP COMMANDS
    ! Time Commands
    Time Format == HOURS                                                                                    ! {HOURS} | ISODATE
    Start Time == 0.0                                                                                               ! Simulation start time (hrs)
    End Time == 3.0                                                                                                 ! Simulation end time (hrs)

    ! Timestepping Commands
    CFL == 0.95                                                                                                     ! {1.0} Courant criterion
    Timestep Limits == 0.01,0.3                                                                             ! {0.0} Minimum timestep (s), {0.0} Maximum time step (s)

    !______________________________________________________________________________
    ! MODEL PARAMETERS
    ! Turbulence
    Momentum Mixing Model == Smagorinsky                                                    ! {None} | Constant | Smagorinsky | Wu
    Global Horizontal Eddy Viscosity == 0.4                                                 ! {0.0} Coeffecient
    Global Horizontal Eddy Viscosity Limits == 0.05, 99999.                 ! {0.0} Minimum eddy viscosity (m^2/s), {99999.} Maximum eddy viscosity (m^2/s)

    ! Cell Wet/Dry Depths and Stabilty
    Cell Wet/Dry Depths == 0.001,0.02                                                               ! {0.00001} Dry depth (m), {0.01} wet depth (m)

    !______________________________________________________________________________
    ! GEOMETRY
    Geometry 2D == ..\model\geo\Mesh_001.2dm                                                                               ! Flexible mesh geometry

    ! Topography
    Set Zpts == 90.                                                                                                        ! Overwrite .2dm elevations and set all to 90 m
    Read Grid Zpts == ..\model\geo\dem_m01.asc                                                                             ! Assign Zb elevations with DEM
    Read GIS Z Line == ..\model\gis\2d_zln_M03_Thalweg_001_L.shp  | ..\model\gis\2d_zln_M03_Thalweg_001_P.shp              ! Enforce channel thalweg breakline
    Read GIS Z Line == ..\model\gis\2d_zln_M03_Rd_Crest_001_L.shp  | ..\model\gis\2d_zln_M03_Rd_Crest_001_P.shp            ! Enforce road crest breaklines
    Read GIS Z Line == ..\model\gis\2d_zln_Invert_Correction_001_R.shp                                                     ! Enforce mesh Zb to surveyed culvert invert levels

    !______________________________________________________________________________
    ! MATERIAL PROPERTIES
    Include == Materials_Manning_001.fvc                                                    ! Include file with material specific commands

    !______________________________________________________________________________
    ! INITIAL CONDITIONS

    !______________________________________________________________________________
    ! BOUNDARY CONDITIONS

    ! Boundary Locations
    Read GIS Nodestring == ..\model\gis\2d_ns_Open_BCs_001_L.shp    ! Open boundary locations
    Read GIS SA == ..\model\gis\2d_sa_Inflows_001_P.shp                             ! Cell inflow locations

    ! Boundary Condition Definition
    BC == Q, Upstream, ..\bc_dbase\M01_001.csv                                              ! Upstream inflow
            BC Header == Time_hr,FC01                                                                       ! Columns to read data from for Time (hrs), Flow (m^3/s)
            Sub-Type == 4                                                                                           ! {1} Assign inflows to cells along nodestring, flow weighted according to water depth^1.5
    End BC

    BC == QN, Downstream, 0.01                                                                              ! Automatic rating curve. Water level Slope (rise/run)
    End BC

    BC == QC, FC04, ..\bc_dbase\M01_001.csv                                                 ! Cell inflow
            BC Header == Time_hr,FC04                                                                       ! Columns to read data from for Time (hrs), Flow (m^3/s)
    End BC

    !______________________________________________________________________________
    ! HYDRAULIC STRUCURES
    Include == Structures_001.fvc                                                                   ! Include file containing culvert and weir specific commands

    !______________________________________________________________________________
    ! OUTPUT COMMANDS
    Log Dir == log
    Output Dir == ..\results\                                                                               ! Results output location
    Write Check Files == ..\check                                                                   ! GIS check file output location

    Include == Outputs_001.fvc                                                                              ! Include file containing output type specific commands
    BC == QC, FC01, ..\bc_dbase\M01_001.csv
        BC Header == Time_hr,FC01
    End BC

Include Files
-------------

Include files are treated as separate control files that are of the same type as the calling control file. This is different to how PyTUFLOW treats TUFLOW Classic read files. Include files (FV) and Read files (Classic) differ in one significant way: relative paths.

- Relative paths in TUFLOW FV include files are relative to the include file. 
- Relative paths in TUFLOW Classic read files are relative to the calling control file.

As an example, all the include files in the FVC can be found using :meth:`~pytuflow.FVC.find_input` and the include file(s) are loaded into the input's :attr:`~pytuflow.ControlFileInput.cf` attribute (this how all inputs link to their respective control files). This attribute is a list as it is possible to use variables in the file name which could be expanded to more than one valid control file.

.. code-block:: pycon

    >>> include_files = fvc.find_input('include')
    >>> for inp in include_files:
    ...     print(inp)
    Include == Materials_Manning_001.fvc
    Include == Structures_001.fvc
    Include == Outputs_001.fvc

    >>> output_include = include_files[-1]
    >>> output_fvc = output_include.cf[0]
    >>> output_fvc.preview()
    ! Output Data Type Definition

    !______________________________________________________________________________
    ! Flow cross section locations - In addition to boundary and structure nodestrings
    Read GIS Nodestring == ..\model\gis\2d_ns_Flux_Monitoring_001_L.shp

    !______________________________________________________________________________
    ! Output Format and Parameters
    Output == netcdf                                                                                                ! TUFLOW FV NetCDF map output format
        Output Parameters == h,v,d,zb                                                                       ! Water level, velocity, depth, bed elevation
        Output Interval == 300.                                                                             ! Ouptut interval (s) 5 minutes
    End Output

    Output == flux                                                                                                  ! Timeseries of net flow across each nodestring
            Output Interval == 300.                                                                         ! Ouptut interval (s) 5 minutes
    End Output

    Output == structflux                                                                                    ! Timeseries of net flow through structures (culverts, weirs, bridges)
            Output Interval == 300.                                                                         ! Ouptut interval (s) 5 minutes
    End Output

    Output == mass                                                                                                  ! Timeseries of total mass in model
            Output Interval == 300.                                                                         ! Ouptut interval (s) 5 minutes
    End Output

    Output == points                                                        ! Time series output at points
        Read GIS PO == ..\model\gis\3d_po_Monitoring_001_P.shp              ! Location of points
        Output Parameters == h, v, d                                                                ! Water level, velocity, depth
        Output Interval == 300.                                                                             ! Ouptut interval (s) 5 minutes
    End Output

The simplest way to create a new include file is to instantiate an empty version of the relevant class, populate it with commands, and separately add the include command into the FVC (or whichever control file will reference the include file).

As an example, we will add a new include file containing new output commands which will be referenced in the FVC control file. The first step is to create the include file, set the file path, and set the parent.

.. code-block:: pycon

    >>> new_output_fvc = FVC()
    >>> new_output_fvc.fpath = 'runs/new_outputs.fvc'
    >>> new_output_fvc.parent = fvc
    
We will populate the new output file with a flux output block. This is just a demonstration and this isn't a complete setup for this output type.

.. code-block:: pycon

    >>> new_output_fvc.append_input('Output == Flux')

Finally, we will add the include file into the FVC control file and then append the new include control file into the :attr:`~pytuflow.ControlFileInput.cf` list. Adding the already instantiated include file to the ``cf`` list is important, otherwise a new file will automatically be created when it writes to disk rather than use the include file we have already created.

.. note::

    Adding the "Include" command like this, pointing to a file that does not exist, will cause an error to be logged stating that the file does not exist. We can ignore this error in this instance since it isn't supposed to exist yet. It will be written to disk the next time we call the ``write`` method.

.. code-block:: pycon

    >>> inp = fvc.append_input('Include == new_outputs.fvc')
    >>> inp.cf.append(new_output_fvc)

Boundary and Material Databases
-------------------------------

Boundary and material databases can be generated using the :meth:`~pytuflow.FVC.bc_dbase` and :meth:`~pytuflow.FVC.mat_file` methods respectively. These methods are the same as in the :class:`~pytuflow.TCF` class, however in this case the databases are generated by collating ``BC`` and ``Mat`` blocks and PyTUFLOW creates virtual databases, rather than loading a database from disk.

.. code-block:: pycon

    >> mat = fvc.mat_file()
    >> mat.df
            Bottom Roughness Horiz Visc Horiz Visc Limits Bed Elev Limits Spatial Reconstr
    ID
    DEFAULT                         0.4   (0.05, 99999.0)
    1                   0.04
    2                   0.02
    3                    0.1
    4                   0.03
    10                  0.08

    >>> bc_dbase = fvc.bc_dbase()
    >>> bc_dbase.df
               Type                   Source Column 1 Column 2 BC Scale BC Offset Default Value
    Name
    Upstream      Q  ..\bc_dbase\M01_001.csv  Time_hr     FC01      1.0       0.0           NaN
    Downstream   QN                                       0.01
    FC04         QC  ..\bc_dbase\M01_001.csv  Time_hr     FC04      1.0       0.0           NaN
    FC01         QC  ..\bc_dbase\M01_001.csv  Time_hr     FC01      1.0       0.0           NaN

Boundary values can be extracted by using the :meth:`~pytuflow.BCDatabase.value` method:

.. code-block:: pycon

    >>> bc_dbase.value('Upstream')
              FC01
    Time_hr
    0.00      0.00
    0.08      0.84
    0.17      3.31
    0.25      4.60
    0.33      7.03
    ...        ...
    2.92      2.89
    3.00      2.18
    3.08      1.96
    3.17      1.77
    3.25      1.60
    3.33      0.00

Running a TUFLOW FV Model
-------------------------

To run an TUFLOW FV model, the first thing to do is to install TUFLOW FV via the ``.deb``, ``.rpm``, or ``.msi`` installers. PyTUFLOW will automatically find TUFLOW FV binaries installed this way.

Alternatively, binaries or directories containing one or more portable TUFLOW FV versions can be manually registered. For example, registering a directory such as ``C:\TUFLOWFV\releases`` where portable versions are unpacked:

.. code-block:: pycon

    >>> from pytuflow import tuflowfv_binaries
    >>> tuflowfv_binaries.register_tuflowfv_binary_folder(r'C:\TUFLOWFV\releases')

It's possible to check the available TUFLOW FV versions from installed versions and registered directories:

.. code-block:: pycon

    >>> for version, path in tuflowfv_binaries.items():
    ...     print(version)
    ... 2026.0.1 /opt/tuflow/tuflowfv-2026.0/bin/tuflowfv-2026.0

Running a TUFLOW FV model is done by using a run context (to resolve scenarios and events) and using the :meth:`~pytuflow.FVCRunState.run` method.

.. code-block:: pycon

    >>> from pytuflow import FVC
    >>> fvc = FVC('runs/FLD000_2D_001.fvc')
    >>> proc = fvc.context().run('2026.0.1')

