.. _working_with_cross_sections:

Working with Cross-Sections
===========================

Cross-sections get some special treatment in pytuflow as the contents of the GIS file or cross-section database
(e.g. Flood Modeller) are loaded into a database. This is done as querying the cross-section data
programmatically is often very useful, especially if pytuflow is being used in a software that uses a UI (like a QGIS plugin),
or script that generates figures that require cross-section data.

Viewing TUFLOW Cross-Sections
-----------------------------

The below example uses ``EG14_001.tcf`` from the `TUFLOW Example Model Dataset <https://wiki.tuflow.com/TUFLOW_Example_Models>`_
to demonstrate how to view the TUFLOW cross-section data in pytuflow. Note, despite being referenced in a GIS
layer, GDAL python bindings are not required to load TUFLOW cross-sections.

The first step is to load the TUFLOW model via the :class:`TCF<pytuflow.TCF>` class:

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG14_001.tcf')

Next, we need to find the cross-section input. The cross-section input we want to view is in the GIS file
``gis\1d_xs_EG14_001_L.shp``. We can find this input using the :meth:`TCF.find_input()<pytuflow.TCF.find_input>` method:

.. code-block:: pycon

    >>> xs_inp = tcf.find_input('1d_xs_EG14_001_L')[0]
    >>> print(xs_inp)
    <GisInput> Read GIS Table Links == gis\1d_xs_EG14_001_L.shp

The database can be accessed via the :attr:`GisInput.cf<pytuflow.GisInput.cf>` attribute. The ``cf`` attribute
is a list of all the control files or databases that are loaded from the input. Another example of this is the
``Geometry Control File`` input, which would have a list of all the geometry control files loaded from the input.

.. code-block:: pycon

    >>> xs_db = xs_inp.cf[0]
    >>> print(xs_db)
    <CrossSectionDatabase> 1d_xs_EG14_001_L.shp

In this case, only one database instance will be loaded. Multiple instances of the database can be loaded if
the file path uses a variable (e.g. ``1d_xs_<<~s1~>>_001_L``), which could be resolved into mulitiple file paths.

The cross-section database is lazy loaded (i.e. only loaded when it is first accessed), so the initial call to
this database will take longer than subsequent calls. Like other database class in pytuflow, the cross-section
database is stored in a DataFrame, which can be accessed via the
:attr:`CrossSectionDatabase.df<pytuflow.CrossSectionDatabase.df>` attribute:

.. code-block:: pycon

    >>> print(xs_db.df)
                                                  Source Type Flags Column_1 Column_2 Column_3 Column_4 Column_5 Column_6
    ID
    ..\csv\1d_xs_M14_C99.csv    ..\csv\1d_xs_M14_C99.csv   XZ
    ..\csv\1d_xs_M14_C100.csv  ..\csv\1d_xs_M14_C100.csv   XZ
    ..\csv\1d_xs_M14_C101.csv  ..\csv\1d_xs_M14_C101.csv   XZ
    ..\csv\1d_xs_M14_C102.csv  ..\csv\1d_xs_M14_C102.csv   XZ
    ..\csv\1d_xs_M14_C103.csv  ..\csv\1d_xs_M14_C103.csv   XZ

The cross-section ID in this case is the file path to the CSV file, however, TUFLOW allows multiple cross-sections
to be stored in a single CSV file. TUFLOW uses columns names to determine where the data is in the CSV file for
this situation. Similarly, pytuflow will use the file path + the column name as the ID.
This ensures a unique ID for each cross-section.

Again, similar to other pytuflow database classes, the :meth:`CrossSectionDatabase.value()<pytuflow.CrossSectionDatabase.value>`
method can be used to get the cross-section data for a given ID.

.. code-block:: pycon

    >>> xs_db.value(r'..\csv\1d_xs_M14_C99.csv')
               X        Z
    0    0.00000  38.4567
    1    1.16450  38.2227
    2    6.74383  37.4142
    3    6.74534  37.4140
    4    7.58031  36.8805
    5    7.58061  36.8803
    6    8.83271  35.9894
    7    8.83344  35.9889
    8   10.99330  36.0249
    9   10.99470  36.0249
    10  11.40040  36.0340
    ...    ...        ...
    26  42.39770  37.6635
    27  43.05550  37.6766
    28  44.40290  37.7324

Viewing Flood Modeller Cross-Sections
-------------------------------------

Flood Modeller cross-sections are also supported in pytuflow. If you are using the the command: ``XS Database ==``, then
you can use a similar approach to the above example to obtain the cross-section database. However, if you are
linking Flood Modeller with TUFLOW, then the ``.dat`` file won't be present in the TUFLOW model. You can
load the Flood Modeller ``.dat`` file manually to access the cross-section data (see example below).

There are alternative methods to load the Flood Modeller cross-section data, for instance, using the
`Flood Modeller API <https://api.floodmodeller.com/api/>`_. However, if you have a script that needs to handle both
TUFLOW cross-sections and Flood Modeller cross-sections, then you may find using pytuflow preferable as it provides
a consistent interface for accessing the cross-section data.

The TUFLOW Example Model Dataset does not contain a Flood Modeller cross-section or linked example. However, TUFLOW
does have a `Flood Modeller tutorial model <https://wiki.tuflow.com/Flood_Modeller_Tutorial_Model>`_
that can be used to demonstrate this functionality. The below example uses ``FMT_M01_001.dat`` from the completed
tutorial model.

.. code-block:: pycon

    >>> from pytuflow import CrossSectionDatabase
    >>> xs_db = CrossSectionDatabase('path/to/FMT_M01_001.dat')

The above step loads the cross-section database from the Flood Modeller ``.dat`` file into a :class:`CrossSectionDatabase<pytuflow.CrossSectionDatabase>`.
The database instance is the same as the TUFLOW cross-section database, however the DataFrame will have different columns, but can
be accessed in the same way:

.. code-block:: pycon

    >>> print(xs_db.df)
                                Name   Type
    ID
    RIVER_SECTION_FC01.40    FC01.40  RIVER
    RIVER_SECTION_FC01.39    FC01.39  RIVER
    RIVER_SECTION_FC01.38    FC01.38  RIVER
    RIVER_SECTION_FC01.37    FC01.37  RIVER
    RIVER_SECTION_FC01.36    FC01.36  RIVER
    RIVER_SECTION_FC01.35    FC01.35  RIVER
    ...                        ...      ...
    RIVER_SECTION_FC02.02    FC02.02  RIVER
    RIVER_SECTION_FC02.01    FC02.01  RIVER
    RIVER_SECTION_FC02.01d  FC02.01d  RIVER

The cross-section data can be accessed via the :meth:`CrossSectionDatabase.value()<pytuflow.CrossSectionDatabase.value>` method.
The key for the cross-section data can either by the ``ID`` or the ``Name`` value of the cross-section. Names within Flood Modeller are
not always unique for the whole model, however are unique within the context of river sections, so it is safe to use it
this way:

.. code-block:: pycon

    >>> xs_db.value('RIVER_SECTION_FC01.40')
             x       y     n  rel_path_len  chan_marker  easting  northing  deactivation_marker  sp_marker path_marker
    0    0.000  56.244  0.09           1.0          NaN      0.0       0.0                  NaN        NaN
    1    3.223  55.707  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
    2    3.621  55.656  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
    3    3.628  55.656  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
    4    4.714  55.555  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
    5    7.523  55.284  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
    6    8.544  55.219  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
    7   11.506  54.266  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
    ...                                ...          ...      ...       ...                  ...        ...        ...
    50  43.466  52.803  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
    51  43.476  52.803  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
    52  44.660  52.820  0.09           0.0          NaN      0.0       0.0                  NaN        NaN
