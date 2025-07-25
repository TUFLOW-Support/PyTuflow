.. _tcf_working_with_scenarios:

Working with Scenarios and Events
=================================

Scenarios and events are important components of any given TUFLOW model. They allow many different simulations
to be run from a single model setup (e.g. different storm events, development scenarios, or sensitivity analysis).

The below examples show how pytuflow handles scenarios and events, how to add or modify scenarios and events in a model,
and to run the model for specific / event combinations.

The following example uses models provided in the
`TUFLOW Example Model Dataset <https://wiki.tuflow.com/TUFLOW_Example_Models>`_.

Checking for Scenarios and Events
---------------------------------

Pytuflow deals with scenarios and events by assigning each input a list of :class:`Scope <pyutflow.Scope>` objects that
describe the context in which the input sits within the model. For example, a command that is within an
"If Scenario" / "End If" block will have a scope list that tells pytuflow that the command is only relevant
if that particular scenario is active.

As an exmaple, we can load in the example model ``EG16_~s1~_~s2~_002.tcf`` which has two scenario groups that are
required to run the model.

.. code-block:: pycon

    >>> from pytuflow import TCF
    >>> tcf = TCF('path/to/EG16_s1_s2_002.tcf')

In this model, the following command reading in the base DEM is always active:
``Read GRID Zpts == grid\DEM_SI_Unit_01.tif`` and the ``z shape`` command
``Read GIS Z Shape == gis\2d_zsh_EG07_006_R.shp`` is only relevant
if the scenario ``"D01"``  is active.

So we can find those commands and check their scopes:

.. code-block:: pycon

    >>> inp = tcf.find_input('Read GRID Zpts')[0]
    >>> print(inp)
    Read GRID Zpts == grid\DEM_SI_Unit_01.tif
    >>> print(inp.scope)
    [<GlobalScope>]

    >>> inp = tcf.find_input('2d_zsh_EG07_006_R.shp')[0]
    >>> print(inp)
    Read GIS Z Shape == gis\2d_zsh_EG07_006_R.shp
    >>> print(inp.scope)
    [<ScenarioScope> !EXG, <ScenarioScope> D01]

The output tells us that the DEM is always active (it has a "Global Scope"), while the Z Shape command is only active
if the scenario ``"D01"`` is active. The addition of ``!`` at the front of the ``"EXG"`` scenario negates that
scenario, meaning that the command is not active if the ``"EXG"`` scenario is active. This part is important, as
if the user passes in both ``"EXG"`` and ``"D01"`` scenarios when running the model, the Z Shape command will not be
included in the run.

Adding Scenarios to a Model
---------------------------


