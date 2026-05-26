import os

import numpy as np

from ...pytuflow._tmf.db.drivers.xstf import TuflowCrossSection


def test_xs_csv_driver_load():
    p = './tests/tmf/test_datasets/1d_xs_M14_C100.csv'
    xs = TuflowCrossSection(os.getcwd(), {'source': p, 'type': 'XZ', 'column_1': 'x', 'column_2': 'z'})
    xs.load()
    assert xs.df.shape == (30, 2)


def test_xs_csv_driver_load_2():
    p = './tests/tmf/test_datasets/1d_xs_M14_C100.csv'
    xs = TuflowCrossSection(os.getcwd(), {'source': p, 'type': 'XZ', 'column_1': None, 'column_2': None})
    xs.load()
    assert xs.df.shape == (30, 2)


def test_xs_csv_driver_load_3():
    p = './tests/tmf/test_datasets/1d_xs_M14_C100_2.csv'
    xs = TuflowCrossSection(os.getcwd(), {'source': p, 'type': 'XZ', 'column_1': 'x', 'column_2': 'z'})
    xs.load()
    assert xs.df.shape == (30, 2)
    assert xs.df.columns.tolist() == ['X', 'Z']


def test_xs_csv_driver_load_4():
    p = './tests/tmf/test_datasets/1d_xs_M14_C100_3.csv'
    xs = TuflowCrossSection(os.getcwd(), {'source': p, 'type': 'XZ', 'flags': 'n','column_1': 'x', 'column_2': 'z'})
    xs.load()
    assert xs.df.shape == (30, 3)
    assert xs.df.columns.tolist() == ['X', 'Z', 'N']


def test_xs_csv_driver_load_5():
    p = './tests/tmf/test_datasets/1d_xs_M14_C100_4.csv'
    xs = TuflowCrossSection(os.getcwd(), {'source': p, 'type': 'XZ', 'flags': 'n','column_1': 'x', 'column_2': 'z', 'column_3': 'n'})
    xs.load()
    assert xs.df.shape == (30, 3)
    assert xs.df.columns.tolist() == ['X', 'Z', 'N']


def test_xs_csv_driver_load_6():
    p = './tests/tmf/test_datasets/1d_xs_M14_C100_5.csv'
    xs = TuflowCrossSection(os.getcwd(), {'source': p, 'type': 'XZ', 'flags': 'n','column_1': 'x', 'column_2': 'z', 'column_3': 'n'})
    xs.load()
    assert xs.df.shape == (30, 3)
    assert xs.df.columns.tolist() == ['X', 'Z', 'N']
    assert xs.df['X'].dtype == np.dtype('float64')


def test_bg_layer():
    p = './tests/tmf/test_datasets/csv/1d_xs_EG11_BB01_1.csv'
    xs = TuflowCrossSection(os.getcwd(), {'source': p, 'type': 'BG'})
    xs.load()
    assert xs.df.shape == (4, 2)


def test_na_layer():
    p = './tests/tmf/test_datasets/csv/1d_na.csv'
    xs = TuflowCrossSection(os.getcwd(), {'source': p, 'type': 'NA'})
    xs.load()
    assert xs.df.shape == (4, 2)
