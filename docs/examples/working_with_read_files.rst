.. _working_with_read_files:

Working with Read Files
=======================

Read files are used in TUFLOW for file and input management as a method of keeping control files neater, and therefore,
more readable and maintainable. Typical examples of when read files are used include:

- To store large blocks of logic. An example of this is where rainfall losses are event dependent, and the loss values
  (e.g. initial loss / continuing loss) are set to a variable depending on the event. This can be done in the event file,
  however quite often the losses are dependent on the AEP and duration combination, so the alternative is to use
  a read file to store a large block of "If Event == " logic.
- To read in elevation data. An example of this is where the model uses a LiDAR tile set, and the model uses
  upward of ten tiles. Instead of having a large number of "Read GRID Zpts == " commands for the base model elevation,
  a read file can be used to group these together, and then the control file just uses a single line to reference the
  read file.

Read files in pytuflow are not represented as separate control files, but rather the inputs are treated
as part of the calling control file. The command "Read File == " itself will not be present in the list of
inputs. Instead, inputs have a :attr:`trd<pytuflow.SettingInput.trd>` attribute that is set to the read file path if the
input is from a read file, or it is set to ``None`` if the input is not from a read file.

Creating a Model with a Read File
-----------------------------------------

There are no example models in the TUFLOW Example Model Dataset that use read files, so we will add one
to an existing model. We will create an example where we setup a cell size sensitivity analysis for a 2D model.
This example will use scenarios, variables, and a read file to accomplish this.

We will use ``EG00_001.tcf`` and the goal is to:

1. Create a new scenario group that represents the model cell size.
2. Update the model settings so that the cell size will be based on the scenario that is being run.
3. Place the logic for setting the cell size in a read file.
4. Run the model through the new sensitivity analysis scenarios.

The following example is a nice use case example for pytuflow, where a sensitivity analysis can be inserted into an
existing model (not necessarily with a read file). Setting up a script for this allows common sensitivity analyses to be run quickly and easily on
any existing model.

1. Create a New Scenario Group
------------------------------

The first step is to load ``EG00_001.tcf`` and save it with a new name that includes a scenario slot for our
new scenario group.

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG00_001.tcf')

    >>> tcf.fpath = tcf.fpath.with_name('EG00_~s1~_001a.tcf')
    >>> tcf.write('inplace')
    <TuflowControlFile> EG00_~s1~_001a.tcf

The above example is similar to the example in the :ref:`running_scenarios_in_a_model`, for more description of
what the above code does, please refer to that section. The difference is that we are updating the number to 001a so
that this new number is propagated to the TGC when we update the model settings.

2. Setting the Model Cell Size
------------------------------

Next, we will create a new variable called ``"CELL_SIZE"`` that will be set to the cell size depending on the scenario
that is being run. Since we are setting up a variable, and not actually setting the cell size directly, we will create
these commands in the TCF and not the TGC.

It doesn't matter where these commands are placed in the TCF, but for organisation, we will place these
close to the top with the other general model settings. The DEM resolution is 0.5m, so we will start with
a cell size of 0.5m and then increase up to 10m. In fact, we will stack the new commands from the bottom, so in terms
of the code insertion order, we will start with 10m and go down (this is just easier as we can use the same
reference input).

.. code-block:: pycon

    >>> ref_inp = tcf.find_input('sgs sample target distance')[0]
    >>> for cell_size in [10, 5, 2, 1, 0.5]:
    ...     cmd = f'Set Variable CELL_SIZE == {cell_size}'
    ...     tcf.insert_input(ref_inp, cmd, after=True)

Next, we need to set the input scope of the new inputs to put them inside a "If Scenario" block.
To get the "IF" / "Else If" behaviour, we need to make sure to also use negative scope for the inputs.
This is explained in more detail in the :ref:`working_with_scenarios` example.

.. code-block:: pycon

    >>> from pytuflow import Scope
    >>> prev_scope = []
    >>> for inp in tcf.find_input('Set Variable CELL_SIZE'):
    ...     scope = Scope('Scenario', f'{inp.value:04.1f}m')
    ...     inp.scope = [x.as_neg() for x in prev_scope] + [scope]
    ...     prev_scope = inp.scope

Finally, we need to set the value of the ``Cell Size ==`` command to be the new variable we created.

.. code-block:: pycon

    >>> tcf.find_input('cell size')[0].rhs = '<<CELL_SIZE>>'

3. Create a Read File for the Cell Size Logic
---------------------------------------------

The final steps are to move the new inputs into a read file and then write the model to disk.
We will call the read file ``cell_size_logic.trd`` and place it in the ``model`` directory. This code could have been
placed in the loop in the previous step, but for clarity, we will do it in a separate step.

.. code-block:: pycon

    >>> trd_path =  tcf.fpath.parent / '..' / 'model' / 'cell_size_logic.trd'
    >>> for inp in tcf.find_input('set variable cell_size'):
    ...     inp.trd = trd_path

    >>> tcf.write('inplace')
    <TuflowControlFile> EG00_~s1~_001a.tcf

4. Running the Model with the Read File
---------------------------------------

Now we have a model that uses a read file to set the cell size based on the scenario name. We can now setup
a series of simulations to run our sensitivity analysis. We don't need to do anything special to run the model with
the read file.

Note, this step might require a TUFLOW license as the smaller cell sizes might not be supported by the free TUFLOW
license. You can just run the 10m and 5m if you want to run this example without a license (or you don't want
to wait for the smaller cell sizes to run).

.. code-block:: pycon

    >>> for cell_size in [10, 5, 2, 1, 0.5]:
    ...     scen_name = f'{cell_size:04.1f}m'
    ...     print('Runnning scenario:', scen_name)
    ...     proc = tcf.context(f'-s1 {scen_name}').run('2025.1.2')
    ...     proc.wait()
