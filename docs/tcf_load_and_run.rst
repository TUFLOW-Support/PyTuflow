.. _tcf_load_and_run:

Load and Run a TCF
==================

The below example shows how to load a TCF, make an edit, save it, and then run the model. The example below
uses ``EG00_001.tcf`` from the `TUFLOW example models <https://wiki.tuflow.com/TUFLOW_Example_Models>`_.

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG00_001.tcf')

To find a given input within the model, the :meth:`pytuflow.TCF.find_input` can be used to return a list of inputs
that match the given filter. For example, finding all SGS related commands:

.. code-block:: pycon

    >>> tcf.find_input('sgs')
    [<SettingInput> SGS == ON, <SettingInput> SGS Sample Target Distance == 0.5]

Updating the SGS Sample Target Distance to 1.0:

.. code-block:: pycon

    >>> inp = tcf.find_input('sgs sample target distance')[0]
    >>> inp.rhs = 1.0
    >>> print(inp)
    SGS Sample Target Distance == 1.0

The change can be checked by printing a preview of the control file to the console:

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
    SGS Sample Target Distance == 1.0                   ! Sets SGS Sample Target Distance to 0.5m
    ...

This update will need to be written to disk before running the model. The new model can overwrite the existing
TCF file if the ``inc`` parameter is set to ``"inplace"``. In this case, we will save the modified model
to a new file. "EG00_002.tcf" is already present in the example models, so we will save our changes as
"EG00_001a.tcf".

.. code-block:: pycon

    >>> tcf.write(inc='001a')
    <TuflowControlFile> EG00_001a.tcf

To run the model, it is useful to provide a location where the all the TUFLOW executables are located. This
only needs to be done once and can be done by registering a TUFLOW binary folder. The folder structure should
look like this:

.. code-block:: text

   /path/to/tuflow/binaries
     ├── 2025.0.0
     │   ├── TUFLOW_iSP_w64.exe
     ├── 2025.1.0
     │   ├── TUFLOW_iSP_w64.exe
     ├── 2025.1.2
     │   ├── TUFLOW_iSP_w64.exe

.. code-block:: pycon

    >>> from pytuflow import register_tuflow_binary_folder
    >>> register_tuflow_binary_folder('/path/to/tuflow/binaries')

Now we can run the model using the TCF's context method and the TUFLOW version name. The context method
is used to pass in what event and scenario combination to run. An empty context is still required even if there
are no events or scenarios to run.

.. code-block:: pycon

    >>> tcf_run = tcf.context()
    >>> proc = tcf_run.run('2025.1.2')
    >>> proc.wait() # Wait for the model to finish running

With the ``tcf_run``, we can also get the output folder and result name. With this, we can access the results:

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
