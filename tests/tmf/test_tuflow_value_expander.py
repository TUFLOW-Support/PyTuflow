import pytest

from ...pytuflow._tmf.parsers.expand_tuflow_value import TuflowValueExpander


def test_tuflow_value_expander_gpkg():
    value = 'gis/test.gpkg >> test_layer'
    expander = TuflowValueExpander({}, None)
    expanded = expander.expand(value)
    assert expanded == 'gis/test.gpkg >> test_layer'


def test_tuflow_value_expander_gpkg_2():
    value = 'gis/test.gpkg >> test_layer && test_layer2'
    expander = TuflowValueExpander({}, None)
    expanded = expander.expand(value)
    assert expanded == 'gis/test.gpkg >> test_layer | gis/test.gpkg >> test_layer2'


def test_tuflow_value_expander_gpkg_3():
    value = 'gis/test_<<VAR>>.gpkg >> test_layer && test_layer2'
    expander = TuflowValueExpander({}, None)
    expanded = expander.expand(value)
    assert expanded == 'gis/test_<<VAR>>.gpkg >> test_layer | gis/test_<<VAR>>.gpkg >> test_layer2'
