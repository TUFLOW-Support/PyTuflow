.. _working_with_inputs:

Working with Inputs
===================

Inputs are important building blocks of TUFLOW models. They are used a lot in other examples, however are never
explicitly covered. This page aims to go into a bit more detail about how inputs can be used.

The examples on this page use models from the `TUFLOW Example Model Dataset <https://wiki.tuflow.com/TUFLOW_Example_Models>`_.

Input Attributes
----------------

Inputs have a number of attributes that are useful to know about.

1. files
^^^^^^^^

Each input has a :attr:`files<pytuflow.Input.files>` attribute that is a list of all the files that are associated
with the input.

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG00_001.tcf')
    >>> inp = tcf.find_input('Read GRID Zpts')[0]
    >>> for f in inp.files:
    ...     print(f)
    TUFLOW\runs\..\model\grid\DEM_SI_Unit_01.tif

Typically, the number of files associated with an input is one, however there are a few situations where there could
be multiple:

- The input references multiple input files, such as:

  ``Read GIS Z Shape == gis\2d_zsh_L.shp | gis\2d_zsh_P.shp``.

- The input uses a variable which can be resolved to multiple files, such as:

  ``Read GIS Z Shape == gis\2d_zsh_<<~s1~>>_R.shp``

- The GIS layer references a file in the attribute table. A typical example is a ``1d_xs`` input, but this can also be
  the case for a ``1d_nwk`` layer that has a channel using the ``"M"`` (matrix) type, which references a csv fle.

TuflowPath
""""""""""

Most files are stored as ``Path`` objects, however GIS files are stored as ``TuflowPath`` objects. The ``TuflowPath`` class is a subclass
of Path that has some additional functionality to handle GPKG file paths (e.g. ``gis\database.gpkg >> layer_name``).

.. code-block:: pycon

    >>> inp = tcf.find_input('2d_bc')[0]
    >>> file = inp.files[0]

    >>> file
    TuflowWindowsPath(TUFLOW\runs\..\model\gis\2d_bc_EG00_001_L.shp)

    >>> print(file.dbpath)
    TUFLOW\runs\..\model\gis\2d_bc_EG00_001_L.shp
    >>> print(file.lyrname)
    2d_bc_EG00_001_L

The example above shows how to access a couple of useful attributes added in the ``TuflowPath`` class. The
:attr:`dbpath<pytuflow.TuflowPath.dbpath>` attribute returns the file path to the GIS database. For shapefiles,
this is the file path to the shapefile, and for GPKG files, this is the file path to the GPKG database.
The :attr:`lyrname<pytuflow.TuflowPath.lyrname>` attribute returns the layer name in the GIS database. This is useful
for GPKGs, as the layer name is not necessarily the same as the GPKG file name.

TuflowPath objects also extend the :meth:`glob()<pytuflow.TuflowPath.glob>` method to allow for globbing of layers in GPKG files.
The below example uses a GPKG created from ``EG07_002.tcf`` using the convert TUFLOW model GIS format tool in QGIS.

.. code-block:: pycon

    >>> from pytuflow import TuflowPath
    >>> gpkg = TuflowPath('/path/to/EG07_002.gpkg')
    >>> for file in gpkg.glob('>> 2d_zsh*'):
    ...     print(file)
    ..\model\gis\EG07_002.gpkg >> 2d_zsh_EG07_002_L
    ..\model\gis\EG07_002.gpkg >> 2d_zsh_EG07_002_P

In the above example, we use ``>>`` to indicate that we are looking for layers within the GPKG file. We use the
pattern ``2d_zsh*`` to match all layers that start with ``2d_zsh``. The result is a list of
``TuflowPath`` objects that represent the layers in the GPKG file.

TuflowPath also has a couple of useful methods for extracting information from the GIS layer. The first example
extracts the GIS attributes from the layer without requiring GDAL to be installed.

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG00_001.tcf')
    >>> gis_2d_bc = tcf.find_input('2d_bc')[0].files[0]
    >>> for attr in gis_2d_bc.gis_attributes():
    ...     print(attr)
    OrderedDict({'Type': 'QT', 'Flags': '', 'Name': 'FC01', 'f': None, 'd': None, 'td': None, 'a': None, 'b': None})
    OrderedDict({'Type': 'HQ', 'Flags': '', 'Name': '', 'f': None, 'd': None, 'td': None, 'a': None, 'b': 0.01})

The second example requires GDAL to be installed, and is a convenience method for opening the GIS layer
with GDAL within a context manager.

.. code-block:: pycon

    >>> with gis_2d_bc.open_gis() as gis:
    ...    print(gis.driver)
    ...    print(gis.ds)
    ...    print(gis.lyr)
    <osgeo.ogr.Driver; proxy of <Swig Object of type 'OGRDriverShadow *' at 0x0000024A5FF8A520> >
    <osgeo.ogr.DataSource; proxy of <Swig Object of type 'OGRDataSourceShadow *' at 0x000001E7CEC19A10> >
    <osgeo.ogr.Layer; proxy of <Swig Object of type 'OGRLayerShadow *' at 0x000001E7CC8A0990> >

2. has_missing_files
^^^^^^^^^^^^^^^^^^^^

Inputs have a :attr:`has_missing_files<pytuflow.Input.has_missing_files>` attribute that indicates whether the input has
any missing files. This attribute can be useful when used with the :meth:`find_input()<pytuflow.TCF.find_input>`
method to filter inputs that have missing files.

First, let's modify the code input to remove the ``_R`` suffix, this causes the file path to be incorrect.

.. code-block:: pycon

    >>> tcf = TCF('path/to/EG00_001.tcf')
    >>> inp = tcf.find_input('2d_code')[0]
    >>> inp.rhs = inp.rhs.replace('_R', '')
    >>> print(inp)
    Read GIS Code == gis\2d_code_EG00_001.shp

Then we can use the ``attrs`` parameter of the :meth:`find_input()<pytuflow.TCF.find_input>` method to filter inputs that have missing files.
The ``attrs`` parameter tells the filter to check the :attr:`has_missing_files<pytuflow.Input.has_missing_files>` attribute of each input.
If the attribute evaluates to ``True``, then the input will be returned.

    >>> for inp in tcf.find_input(attrs='has_missing_files'):
    ...     print(f'Input has missing files: {inp}')
    Read GIS Code == gis\2d_code_EG00_001.shp

More than one attribute can be passed into the ``attrs`` parameter.
For example, if you wanted to return only missing files from GIS inputs:

.. code-block:: pycon

    >>> from pytuflow import const
    >>> for inp in tcf.find_input(attrs=[('has_missing_files',), ('TUFLOW_TYPE', const.INPUT.GIS)]):
    ...     print(inp)
    Read GIS Code == gis\2d_code_EG00_001.shp

In the above example, we import the ``const`` module from ``pytuflow`` which contains constants for TUFLOW types.
We then pass in a list of tuples to the ``attrs`` parameter. Each tuple contains the attribute name and the value to filter on.
The default value for the attribute is ``True``, so we don't need to specify it for the ``has_missing_files`` attribute.

3. lhs, rhs, and value
^^^^^^^^^^^^^^^^^^^^^^

Inputs have a :attr:`lhs<pytuflow.Input.lhs>`, :attr:`rhs<pytuflow.Input.rhs>`, and :attr:`value<pytuflow.Input.value>` attribute.
The :attr:`lhs<pytuflow.Input.lhs>` attribute and the :attr:`rhs<pytuflow.Input.rhs>` attribute are the left-hand
and right-hand sides of the input, respectively. They reflect what the command line would look like in the text editor.
The :attr:`value<pytuflow.Input.value>` attribute is a resolved value (if possible) version of the
:attr:`rhs<pytuflow.Input.rhs>` attribute in an appropriate data type. For example, the returned value will
be an integer if the command is setting the code value (``Set Code == 0``), or a float if the command is setting
the model cell size (``Cell Size == 2.5``), or a Path object if the command is referencing a file.

.. code-block:: pycon

    >>> tcf = TCF('path/to/EG00_001.tcf')
    >>> inp = tcf.find_input('set code')[0]

    >>> inp.lhs
    'Set Code'

    >>> inp.rhs
    '0'

    >>> inp.value
    0

The :attr:`lhs<pytuflow.Input.lhs>` and :attr:`rhs<pytuflow.Input.rhs>` attributes can be edited by the user,
however the :attr:`value<pytuflow.Input.value>` attribute is read-only.

.. code-block:: pycon

    >>> inp = tcf.find_input('cell size')[0]
    >>> inp.value = 2.5
    Traceback (most recent call last):
      ...
    AttributeError: The "value" attribute is read-only, use "rhs" to set the value of the input.

    >>> inp.rhs = '2.5'
    >>> inp.value
    2.5

The :attr:`lhs<pytuflow.Input.lhs>` is also editable, but is restricted to the same input type. For example,
a ``Read GIS`` command must stay as a ``Read GIS`` command, and cannot change to a ``Set Code`` command. The purpose
of editing the :attr:`lhs<pytuflow.Input.lhs>` attribute is to allow easy insertion/editing of additional keywords in the
given command.

.. code-block:: pycon

    >>> inp = ... # assume input is loaded as "Time Output Cutoff Depth == 0.1"
    >>> inp.lhs = 'Time Output Cutoff Hazard'
    >>> print(inp)
    Time Output Cutoff Hazard == 0.1

The above example changes the command, which adds an additional time output to the model, to be based on
hazard instead of depth.

The :attr:`value<pytuflow.Input.value>` attribute will also be resolved if possible. For example, if the rhs
of the command is set to a variable, and the variable has a global scope (i.e. is not scenario or event dependent),
then the :attr:`value<pytuflow.Input.value>` attribute will return the resolved value of the variable.

To show this, let's first insert a new variable into the TCF after the ``sgs sample target distance`` input.

.. code-block:: pycon

    >>> tcf = TCF('path/to/EG00_001.tcf')
    >>> ref_inp = tcf.find_input('sgs sample target distance')[0]
    >>> tcf.insert_input(ref_inp, 'Set Variable CELL_SIZE == 2.5', after=True)

Then, let's change the ``rhs`` of the ``Cell Size`` command to reference the variable we just created.

.. code-block:: pycon

    >>> cell_size = tcf.find_input('cell size')[0]
    >>> print(cell_size)
    'Cell Size == 5.0'

    >>> cell_size.rhs = '<<CELL_SIZE>>'

Finally, we can check the :attr:`value<pytuflow.Input.value>` attribute to see the resolved value of the variable.

.. code-block:: pycon

    >>> print(cell_size.rhs)
    <<CELL_SIZE>>
    >>> print(cell_size.value)
    2.5

As you can see in the above example, the :attr:`rhs<pytuflow.Input.rhs>` attribute returns the variable name,
and the :attr:`value<pytuflow.Input.value>` attribute returns the resolved value of the variable.
