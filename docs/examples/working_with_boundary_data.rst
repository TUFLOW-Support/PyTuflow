.. _working_with_boundary_data:

Working With Boundary Data in the bc_dbase.csv
==============================================

The below examples show how to view the bc_dbase.csv file, extract boundary time-series data from it, and
how to make edits.

The following example uses models provided in the
`TUFLOW Example Model Dataset <https://wiki.tuflow.com/TUFLOW_Example_Models>`_.

Extracting Time-Series Boundaries - Simple Example
--------------------------------------------------

The first example shows how to read boundary data from the bc_dbase.csv file from a model that
does not use an event file and does not require any event arguments to run. The entry
point to the model will be via the :class:`TCF<pytuflow.TCF>` class, which is used to load the TUFLOW model.
The model used in this example is ``EG00_001.tcf`` from the TUFLOW example models.

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG00_001.tcf')

We can get the bc_dbase instance from the TCF using the :meth:`TCF.bc_dbase()<pytuflow.TCF.bc_dbase>` method.

.. code-block:: pycon

    >>> bc_dbase = tcf.bc_dbase()

The database content is stored in a pandas DataFrame, and we can view this by accessing the
:attr:`BCDatabase.df<pytuflow.BCDatabase.df>` attribute:

.. code-block:: pycon

    >>> print(bc_dbase.df)
                Source        Column 1     Column 2  Add Col 1  Mult Col 2  Add Col 2  Column 3  Column 4
    Name
    FC01  EG00_001.csv  inflow_time_hr  inflow_FC01        NaN         NaN        NaN       NaN       NaN

This model contains a single inflow (``QT``) boundary called ``"FC01"``. To view the time-series data for this
boundary, we can use the :meth:`BCDatabse.value()<pytuflow.BCDatabase.value>` method, which returns a
pandas DataFrame with the time-series data for the boundary:

.. code-block:: pycon

    >>> fc01 = bc_dbase.value('FC01')
    >>> print(fc01)
        inflow_time_hr  inflow_FC01
    0            0.000         0.00
    1            0.083         0.84
    2            0.167         3.31
    3            0.250         4.60
    4            0.333         7.03
    5            0.417        12.39
    ...           ...           ...
    38           3.167         1.77
    39           3.250         1.60
    40           3.333         1.45

Note, the boundary name that is passed into the :meth:`BCDatabase.value()<pytuflow.BCDatabase.value>` method
is not case-sensitive, so ``"FC01"``, ``"fc01"``, and ``"Fc01"`` will all return the same data.

Extracting Time-Series Boundaries - With Events
-----------------------------------------------

This example shows how to extract boundary data from a model that is using an event file to manage multiple events.
This is a much more common use case, as many real world models will use an event file. This example
uses ``EG16_~e1~_~e2~_005.tcf`` from the TUFLOW example models, which has multiple events defined in the event file.

First, let's load the TCF file, then get the bc_dbase instance and print the DataFrame to see
what boundaries are defined in the model:

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG16_~e1~_~e2~_005.tcf')

    >>> bc_dbase = tcf.bc_dbase()
    >>> print(bc_dbase.df)
                             Source        Column 1     Column 2  Add Col 1  Mult Col 2  Add Col 2  Column 3  Column 4
    Name
    FC01  EG16__event1__event2_.csv  inflow_time_hr  inflow_FC01        NaN         NaN        NaN       NaN       NaN

This database is very similar to the previous, simple example, but it is using ``_event1_`` and ``_event2_`` in the
source file name, which are variables that will be replaced with the event names when the model is run.

What happens if we try and get the time-series data for ``"FC01"``?

.. code-block:: pycon

    >>> fc01 = bc_dbase.value('FC01')
    Traceback (most recent call last):
        ...
    ValueError: Database requires a context to resolve value.

Python raises an exception and we end up with the message "Database requires a context to resolve value."
So the error message is telling us that it was unable to resolve the value because it needs a run context to do so.

If you need to, you can check the available events in the model by using the :meth:`TCF.event_database()<pytuflow.TCF.event_database>` method:

.. code-block:: pycon

    >>> event_db = tcf.event_database()
    >>> print(event_db.df)
    {'Q100': {'_event1_': '100yr'},
     'QPMF': {'_event1_': 'PMFyr'},
     '2hr': {'_event2_': '2hr'},
     '4hr': {'_event2_': '4hr'}}

The event database is effectively just a dictionary. The keys are the event names, and the values are the
event variables and their corresponding values.

So to get the time-series data for ``"FC01"``, we can use the :meth:`TCF.context()<pytuflow.TCF.context>`
method and pass in event arguments so that the database can resolve the values:

.. code-block:: pycon

    >>> bc_dbase = tcf.context('-e1 Q100 -e2 2hr').bc_dbase()
    >>> fc01 = bc_dbase.value('FC01')
    >>> print(fc01)
        inflow_time_hr  inflow_FC01
    0            0.000         0.00
    1            0.083         0.84
    2            0.167         3.31
    3            0.250         4.60
    4            0.333         7.03
    5            0.417        12.39
    ...           ...           ...
    38           3.167         1.77
    39           3.250         1.60
    40           3.333         1.45

Another way to do the same thing is to use the :meth:`BCDatabase.context()<pytuflow.BCDatabase.context>` method.
Consider the following example using ``EG16_~s1~_~s2~_~e1~_~e2~_006.tcf`` which also includes scenarios:

.. code-block:: pycon

    >>> tcf = TCF('path/to/EG16_~s1~_~s2~_~e1~_~e2~_006.tcf')
    >>> bc_dbase = tcf.context('-e1 Q100 -e2 2hr').bc_dbase()
    Traceback (most recent call last):
        ...
    ValueError: Pause command encountered: Not Valid Cell Size - See TCF

We now get a new error message, which is telling us that the model is hitting a pause command. This is because we
aren't passing any scenario arguments to the run context. So, in this case, it might be easier just to pass
in the event arguments to the :meth:`BCDatabase.context()<pytuflow.BCDatabase.context>` method without worrying
about scenarios, since in this case the scenarios are not relevant to the boundary data:

.. code-block:: pycon

    >>> fc01 = tcf.bc_dbase().context('-e1 Q100 -e2 2hr').value('FC01')
    >>> print(fc01)
        inflow_time_hr  inflow_FC01
    0            0.000         0.00
    1            0.083         0.84
    2            0.167         3.31
    3            0.250         4.60
    4            0.333         7.03
    5            0.417        12.39
    ...           ...           ...
    38           3.167         1.77
    39           3.250         1.60
    40           3.333         1.45

Using the :meth:`BCDatabase.context()<pytuflow.BCDatabase.context>` will also be quicker than using the
:meth:`TCF.context()<pytuflow.TCF.context>` method, as it will only resolve the bc_dbase. Calling it from
the TCF class, the context will be passed on to all it's children (other control files and databases). Although it's
not necessarily slow, it will be slower than resolving only the boundary database.

Editing the Boundary Database
-----------------------------

Editing the boundary database is done by modifying the pandas DataFrame that is stored in the
:attr:`BCDatabase.df<pytuflow.BCDatabase.df>` attribute. For example, we can add a new boundary that might be
a constant downstream water level boundary with the name ``dns_bndry`` and a value of ``0.5m``. We will add this
to ``EG16_~e1~_~e2~_005.tcf``:

.. code-block:: pycon

    >>> import pandas as pd
    >>> tcf = TCF('path/to/EG16_~e1~_~e2~_005.tcf')
    >>> bc_dbase = tcf.bc_dbase()

    >>> val_col_name = bc_dbase.df.columns[2]
    >>> dns_bndry = pd.DataFrame({val_col_name: [0.5]}, index=['dns_bndry'])
    >>> bc_dbase.df = pd.concat([bc_dbase.df, dns_bndry], axis=0)

    >>> print(bc_dbase.df)
                                  Source        Column 1     Column 2  Add Col 1  Mult Col 2  Add Col 2  Column 3  Column 4
    FC01       EG16__event1__event2_.csv  inflow_time_hr  inflow_FC01        NaN         NaN        NaN       NaN       NaN
    dns_bndry                        NaN             NaN          0.5        NaN         NaN        NaN       NaN       NaN

We can then write the modified files to disk using the :meth:`TCF.write()<pytuflow.TCF.write>` method. We will
save the new file as ``005a``:

.. code-block:: pycon

    >>> tcf.write(inc='005a')
    <TuflowControlFile> EG16_~e1~_~e2~_005a.tcf

