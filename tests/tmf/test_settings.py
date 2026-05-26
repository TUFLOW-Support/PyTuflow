from pathlib import Path

from ...pytuflow._tmf.settings import TCFConfig
from ...pytuflow._tmf.cf.tef import TEF


def test_empty_settings():
    settings = TCFConfig()


def test_settings_with_tcf():
    tcf = './tests/tmf/test_datasets/EG15_001.tcf'
    settings = TCFConfig(tcf)
    assert settings.model_name == 'EG15_001'


def test_settings_variables():
    tcf = './tests/tmf/test_datasets/models/variables_1/runs/EG00_001.tcf'
    settings = TCFConfig(tcf)
    assert settings.model_name == 'EG00_001'
    assert 'ITER' in settings.variables
    assert 'MODEL_NAME' in settings.variables


def test_settings_event_file():
    tcf = './tests/tmf/test_datasets/models/shp/runs/EG00_001.tcf'
    settings = TCFConfig(tcf)
    assert len(settings.event_db) == 2
    assert len(settings.event_db.event_variables().get('_event_', [])) == 2
