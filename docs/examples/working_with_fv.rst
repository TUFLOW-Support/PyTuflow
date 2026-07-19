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

The inputs listed above are similar to commands like ``Sediment Control File == `` or in Classic ``Geometry Control File == ``. The input has a reference to any loaded control files, or in this case the input has a reference to the loaded block. Because the blocks inherit from the control file class, it has access to the control file methods e.g. ``find_input`` or ``preview``. Take the first bc block input as an example:

.. code-block:: pycon

    >>> bc = bc_inps[0]
    >>> bc_block = bc.block_control()
    >>> bc_block.preview()
    BC Header == Time_hr,FC01                                                                       ! Columns to read data from for Time (hrs), Flow (m^3/s)
    Sub-Type == 4                                                                                           ! {1} Assign inflows to cells along nodestring, flow weighted according to water depth^1.5

Include Files
-------------

How include files are treated

Boundary and Material Databases
-------------------------------

bc_dbase() and mat_file()

Running a TUFLOW FV Model
-------------------------

Ipsem lorem.
