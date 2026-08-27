from pathlib import Path

import pytest

from ...pytuflow._tmf.db.drivers.driver import DatabaseDriver
from ...pytuflow._tmf.db.drivers.csv import CsvDatabaseDriver
from ...pytuflow._tmf.db.drivers.ts1 import TS1DatabaseDriver
from ...pytuflow._tmf.db.drivers.get_database_driver_class import get_database_driver_class


def test_driver_init_csv():
    p = Path(__file__).parent / 'csv_database.csv'
    with p.open('w') as f:
        f.write('a,b,c\n1,2,3')
    try:
        driver = get_database_driver_class(p)()
        assert isinstance(driver, CsvDatabaseDriver)
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_driver_init_csv_2():
    p = Path(__file__).parent / 'csv_database.txt'
    with p.open('w') as f:
        f.write('a,b,c\n1,2,3')
    try:
        driver = get_database_driver_class(p)()
        assert isinstance(driver, CsvDatabaseDriver)
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_driver_init_csv_3():
    p = Path(__file__).parent / 'csv_database.csv'
    driver = get_database_driver_class(p)()
    assert isinstance(driver, CsvDatabaseDriver)


def test_driver_init_not_csv():
    p = Path(__file__).parent / 'csv_database.txt'
    with p.open('wb') as f:
        f.write(b'\x00\x01\x02')
    try:
        driver = get_database_driver_class(p)()
        assert not isinstance(driver, CsvDatabaseDriver)
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_driver_init_not_csv_2():
    p = Path(__file__).parent / 'csv_database.txt'
    with p.open('w') as f:
        f.write('a\tb\tc\n1\t2\t3')
    try:
        driver = get_database_driver_class(p)()
        assert not isinstance(driver, CsvDatabaseDriver)
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_driver_init_csv_fail():
    p = Path(__file__).parent / 'csv_database.txt'
    with p.open('w') as f:
        f.write('\n')
    try:
        driver = get_database_driver_class(p)()
        assert not isinstance(driver, CsvDatabaseDriver)
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_driver_load():
    p = Path(__file__).parent / 'csv_database.csv'
    with p.open('w') as f:
        f.write('a,b,c\n1,2,3')
    try:
        driver = get_database_driver_class(p)()
        df = driver.load(p, {'header': 0}, 0)
        assert df.shape == (1, 2)
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_driver_ts1():
    p = './tests/tmf/test_datasets/ts1/brisbane_RF_1p720m.ts1'
    p = Path(p).resolve()
    driver = get_database_driver_class(p)()
    assert isinstance(driver, TS1DatabaseDriver)
    df = driver.load(p)
    assert df.shape == (26, 20)
