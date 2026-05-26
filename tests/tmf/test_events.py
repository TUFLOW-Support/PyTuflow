from pathlib import Path

import pytest
from ...pytuflow._tmf.cf.tef import TEF
from ...pytuflow._tmf.event import EventDatabase
from ...pytuflow._tmf.settings import TCFConfig
from ...pytuflow._tmf.context import Context


def test_empty_event():
    tef = './tests/tmf/test_datasets/event_file.tef'
    event_db = TEF.parse_event_file(Path(tef), TCFConfig())
    assert len(event_db) == 7
    assert event_db.get('SSP1-2.6M') is not None
    assert event_db.get('SSP5-8.5H+') is not None


def test_event_scope():
    tef = TEF('./tests/tmf/test_datasets/EG11_004.tef')
    inps = tef.context('-e1 Q100 -e2 2hr').find_input('BC Event Source')
    assert len(inps) == 2


def test_if_event_file():
    p = './tests/tmf/test_datasets/if_event_file.tef'
    event_db = TEF.parse_event_file(Path(p).resolve(), TCFConfig())
    ctx = Context({'e1': 'Q100', 'e2': '2hr'})
    ctx.load_events(event_db)
    assert ctx.translate('Test__event1__event2___event3___event4_.csv') == 'Test_100yr2hr_ARR1987_Dummy.csv'

    ctx = Context({'e1': 'Q50', 'e2': '2hr'})
    ctx.load_events(event_db)
    assert ctx.translate('Test__event1__event2___event3___event4_.csv') == 'Test_50yr2hr_ARR2016_Dummy.csv'


def test_events_in_tcf():
    p = './tests/tmf/test_datasets/event_tcf.tcf'
    config = TCFConfig(Path(p).resolve())
    assert config.event_db
    ctx = Context(config=config)
    assert ctx.translate('Test__event1__event2_.csv') == 'Test_100yr2hr.csv'


def test_old_events_in_tcf():
    p = './tests/tmf/test_datasets/event_old_tcf.tcf'
    config = TCFConfig(Path(p).resolve())
    assert config.event_db
    ctx = Context(config=config)
    assert ctx.translate('Test___event__.csv') == 'Test_100yr2hr.csv'


def test_event_file_old():
    p = './tests/tmf/test_datasets/event_file_old.tef'
    event_db = TEF.parse_event_file(Path(p).resolve(), TCFConfig())
    ctx = Context({'e1': 'Q100', 'e2': '2hr'})
    ctx.load_events(event_db)
    assert ctx.translate('Test__event1__event2_.csv') == 'Test_100yr2hr.csv'


def test_event_file_old_not_supported():
    p = './tests/tmf/test_datasets/event_file_old_not_supported.tef'
    with pytest.raises(NotImplementedError):
        event_db = TEF.parse_event_file(Path(p).resolve(), TCFConfig())
