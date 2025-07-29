.. _extracting_material_and_soil_data:

Extracting Material and Soil Data
=================================

Material and soil data are stored in a database class, similar to the bc_dbase class, and can be worked with
in a similar way to the previous example (:ref:`working_with_boundary_data`).

Viewing the Material File
-------------------------

In this example, we will look at how to view the material file using ``EG00_001.tcf`` from the
`TUFLOW Example Model Dataset <https://wiki.tuflow.com/TUFLOW_Example_Models>`_.

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG00_001.tcf')

    >>> mat = tcf.mat_file()
    >>> print(mat.df)
                 Manning's n  Rainfall Losses  Land Use Hazard ID
    Material ID
    1                  0.060              NaN                 NaN
    2                  0.022              NaN                 NaN
    3                  0.400              NaN                 NaN
    4                  0.030              NaN                 NaN
    10                 0.080              NaN                 NaN
    11                 0.040              NaN                 NaN

In the above example, we first get an instance of the material file using the
:meth:`TCF.mat_file()<pytuflow.TCF.mat_file>` method. The material file is stored in a
:class:`MatDatabase<pytuflow.MatDatabase>` instance, which is similar to the
:class:`BCDatabase<pytuflow.BCDatabase>` class, and stores the database content in a pandas DataFrame which
can be accessed via the :attr:`MatDatabase.df<pytuflow.MatDatabase.df>` attribute.

The value for a given material ID can be accessed using the :meth:`MatDatabase.value()<pytuflow.MatDatabase.value>` method:

.. code-block:: pycon

    >>> mat.value(1)
    0.06

In this case, the method isn't doing anything special, as the same result could be achieved by using the DataFrame:

.. code-block:: pycon

    >>> mat.df.loc[1, "Manning's n"]
    np.float64(0.06)

However, the :meth:`MatDatabase.value()<pytuflow.MatDatabase.value>` method becomes useful in more complex cases,
such as when the given material is using a depth-varying manning's `n` value. Consider the following example using
``EG07_012.tcf`` from the TUFLOW example models:

.. code-block:: pycon

    >>> tcf = TCF('path/to/EG07_012.tcf')
    >>> mat = tcf.mat_file()
    >>> print(mat.df)
               Manning's n Rainfall Losses  Landuse Hazard ID  Description
    ID
    1    0.03,0.1,0.1,0.06             0,0                NaN          NaN
    2                 0.02             0,0                NaN          NaN
    3    0.03,0.02,0.1,0.4             0,0                NaN          NaN
    4                 0.03             0,0                NaN          NaN
    10  0.03,0.01,0.1,0.08             0,0                NaN          NaN
    11   0.03,0.1,0.1,0.04             0,0                NaN          NaN

The manning's `n` value for some of the materials is a list of values signifying a depth-varying value. When
this value is extracted using the :meth:`MatDatabase.value()<pytuflow.MatDatabase.value>` method, it will return a
this in a more readable format within a DataFrame:

.. code-block:: pycon

    >>> mat.value(1)
       Depth  Manning's n
    0   0.03         0.10
    1   0.10         0.06

This is also true if the depth varying values are stored in a different CSV file and referenced in the material file.
The :meth:`MatDatabase.value()<pytuflow.MatDatabase.value>` method will automatically read the CSV file and
return the values in a DataFrame format.

Viewing the Soil File
---------------------

The soil file is very similar to the material file. Let's have a look at ``EG05_006.tcf`` from the TUFLOW
example models:

.. code-block:: pycon

    >>> tcf = TCF('path/to/EG05_006.tcf')
    >>> soil = tcf.soils_file()
    >>> print(soil.df)
            Method           Column 1 Column 2
    Soil ID
    1           GA             "CLAY"
    2           GA       "SILTY CLAY"
    3           GA       "SANDY CLAY"
    4           GA        "CLAY LOAM"
    5           GA  "SILTY CLAY LOAM"
    6           GA  "SANDY CLAY LOAM"
    7           GA        "SILT LOAM"
    8           GA             "LOAM"
    9           GA       "SANDY LOAM"
    10          GA       "LOAMY SAND"
    11          GA             "SAND"
    12        NONE                NaN      NaN

Similar to the material file and bc_dbase, the soil file is stored as as database class, and the data can
be accessed using the :attr:`SoilDatabase.df<pytuflow.SoilDatabase.df>` attribute.

The soil database is different, and a bit more awkward, than the other databases as the columns change depending
on the method used, or they can even be different for the same method. For example, the ``"GA"`` (Green-Ampt)
method expects the first column to be the name of the USDA soil type, or it can be the
"Suction" parameter for the Green-Ampt method. If the method is ``"ILCL"``, then the first column is the
initial loss value. Because of this, the DataFrame uses generic column names, such as "Column 1" and "Column 2".

The value method comes in handy here, as it will return the values with named keys based on the method used.

.. code-block:: pycon

    >>> soil.value(1)
    CaseInsDictOrdered([('method', 'GA'),
                    ('USDA Soil Type', 'CLAY'),
                    ('Initial Moisture', None),
                    ('Max Ponding Depth', None),
                    ('Horizontal Conductivity', None),
                    ('Residual Water Content', None),
                    ('Saturated Water Content', None),
                    ('alpha', None),
                    ('n', None),
                    ('L', None)])

The returned value is an ordered dictionary that also uses case-insensitive keys, so you can access the values
using named parameters, such as ``"Horizontal Conductivity"``, rather than the generic "Column 1" or "Column 2".

We can look at ``EG05_011.tcf`` to see an example of a more complex soil file:

.. code-block:: pycon

    >>> tcf = TCF('path/to/EG05_011.tcf')
    >>> soil = tcf.soils_file()
    >>> print(soil.df)
            Method  Column 1  Column 2  Column 3  Column 4  Column 5
    Soil ID
    1           GA     316.3       0.3     0.385       0.2       0.2
    2           GA     292.2       0.5     0.423       0.2       0.2
    3           GA     239.0       0.6     0.321       0.2       0.2
    4           GA     208.8       1.0     0.309       0.2       0.2
    5           GA     273.0       1.0     0.432       0.2       0.2
    6           GA     218.5       1.5     0.330       0.2       0.2
    7           GA     166.8       3.4     0.486       0.2       0.2
    8           GA      88.9       7.6     0.434       0.2       0.2
    9           GA     110.1      10.9     0.412       0.2       0.2
    10          GA      61.3      29.9     0.401       0.2       0.2
    11          GA      49.5     117.8     0.417       0.2       0.2
    12        NONE       NaN       NaN       NaN       NaN       NaN

    >>> print(soil.value(1))
    CaseInsDictOrdered([('method', 'GA'),
                    ('Suction', 316.3),
                    ('Hydraulic Conductivity', 0.3),
                    ('Porosity', 0.385),
                    ('Initial Moisture', 0.2),
                    ('Max Ponding Depth', 0.2),
                    ('Horizontal Conductivity', None),
                    ('Residual Water Content', None),
                    ('Saturated Water Content', None),
                    ('alpha', None),
                    ('n', None),
                    ('L', None)])

This example is still relatively simple, in that all the soils use the same method. However, you can imagine a situation
where different soil methods are used and this would require mapping from column names to a method-specific,
or method context-specific, parameter. Rather than the user checking whether "Column 1" is a string or a number,
the :meth:`SoilDatabase.value()<pytuflow.SoilDatabase.value>` method will return the values in a dictionary with
specific keys based on the method used. So, for example, the user can check if the key "USDA Soil Type" exists:

.. code-block:: pycon

    >>> soil_1 = soil.value(1)

    >>> if soil_1['method'] == 'GA' and 'USDA Soil Type' in soil_1:
    ...     print("This soil uses the GA method with a USDA Soil Type.")
    ... elif soil_1['method'] == 'GA':
    ...     print("This soil type uses the GA method with custom parameters.")
    ... else:
    ...     print("This soil type does not use the GA method.")
    This soil type uses the GA method with custom parameters.


