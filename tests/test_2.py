import os
import unittest
from unittest import TestCase

from pytuflow.pytuflow_types import FileTypeError
from pytuflow.outputs.bc_tables_check import BCTablesCheck
from pytuflow.fm import GXY
from pytuflow.outputs.hyd_tables_check import HydTablesCheck
from pytuflow.outputs.info import INFO
from pytuflow.outputs.tpc import TPC
from pytuflow.outputs.gpkg_1d import GPKG1D
from pytuflow.outputs.gpkg_2d import GPKG2D
from pytuflow.outputs.gpkg_rl import GPKGRL
from pytuflow.outputs.fm_ts import FMTS
from pytuflow.outputs.fv_bc_tide import FVBCTide
from pytuflow.outputs.cross_sections import CrossSections


class Test_Info_2013(unittest.TestCase):

    def test_load(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        self.assertEqual('M04_5m_001', res.name)

    def test_not_info(self):
        p = './tests/2013/EG00_001_Scen_1+Scen_2.2dm.info'
        try:
            res = INFO(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_blank_info(self):
        p = './tests/2013/M04_5m_001_1d_blank.info'
        try:
            res = INFO(p)
            raise AssertionError('Should have raised an exception')
        except EOFError:
            pass

    def test_channels(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        self.assertEqual(54, res.channel_count)
        self.assertEqual(54, len(res.ids('channel')))
        self.assertEqual(54, len(res.ids('q')))
        self.assertEqual(2, len(res.data_types('channel')))
        self.assertEqual(2, len(res.data_types('ds1')))

    def test_nodes(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        self.assertEqual(55, res.node_count)
        self.assertEqual(55, len(res.ids('node')))
        self.assertEqual(55, len(res.ids('h')))
        self.assertEqual(1, len(res.data_types('node')))
        self.assertEqual(1, len(res.data_types('ds1.1')))

    def test_id_data_type_context(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        self.assertEqual(109, len(res.ids('1d')))
        self.assertEqual(3, len(res.data_types('1d')))

    def test_times(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        self.assertEqual(181, len(res.times()))
        self.assertEqual(181, len(res.times(fmt='absolute')))

    def test_time_series(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        ts = res.time_series('ds1', 'q')
        self.assertEqual((181, 1), ts.shape)
        ts = res.time_series(['FC01.24.1', 'FC01.25.1'], 'h')
        self.assertEqual((181, 2), ts.shape)
        ts = res.time_series(None, None)
        self.assertEqual((181, 163), ts.shape)
        ts = res.time_series('ds1', None)
        self.assertEqual((181, 2), ts.shape)
        ts = res.time_series(None, 'flow')
        self.assertEqual((181, 54), ts.shape)
        ts = res.time_series('ds1', 'v', time_fmt='absolute')
        self.assertEqual((181, 1), ts.shape)

    def test_maximums(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        df = res.maximum(['ds1', 'ds2'], ['flow', 'velocity'])
        self.assertEqual((2, 4), df.shape)
        df = res.maximum(['FC01.24.1', 'FC01.25.1'], ['h'])
        self.assertEqual((2, 2), df.shape)
        df = res.maximum(['ds1', 'FC01.24.1'], ['flow', 'level'])
        self.assertEqual((2, 4), df.shape)
        df = res.maximum('ds1', None)
        self.assertEqual((1, 4), df.shape)
        df = res.maximum(None, 'flow')
        self.assertEqual((54, 2), df.shape)
        df = res.maximum(None, None)
        self.assertEqual((109, 6), df.shape)
        df = res.maximum('ds1', 'flow', time_fmt='absolute')
        self.assertEqual((1, 2), df.shape)

    def test_data_types_section(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        self.assertEqual(5, len(res.data_types('section')))

    def test_long_plot(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        df = res.section('ds1', ['bed level', 'water level', 'max water level', 'pits'], 1)
        self.assertEqual((12, 8), df.shape)

    def test_long_plot_2(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        df = res.section(['FC01.1_R', 'FC01.36'], ['bed level', 'water level', 'pipes'], 1)
        self.assertEqual((4, 7), df.shape)

    def test_long_plot_incorrect_id(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = INFO(p)
        df = res.section(['FCo1.1_R', 'FC01.36'], ['bed level', 'water level', 'pipes'], 1)
        self.assertEqual((168, 7), df.shape)


class Test_TPC_2016(TestCase):

    def test_load(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual('EG14_001', res.name)

    def test_not_tpc(self):
        p = './tests/2013/M04_5m_001_1d.info'
        try:
            tpc = TPC(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_blank_tpc(self):
        p = './tests/2016/M04_5m_001_not_complete.tpc'
        try:
            tpc = TPC(p)
            raise AssertionError('Should have raised an exception')
        except EOFError:
            pass

    def test_empty_results(self):
        p = './tests/2016/EG00_001.tpc'
        try:
            tpc = TPC(p)
            raise AssertionError('Should have raised an exception')
        except EOFError:
            pass

    def test_channel_count(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(54, res.channel_count)

    def test_node_count(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(53, res.node_count)

    def test_po_count(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(1, res.po_point_count)
        self.assertEqual(1, res.po_line_count)
        self.assertEqual(1, res.po_poly_count)

    def test_rl_count(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(1, res.rl_point_count)
        self.assertEqual(1, res.rl_line_count)
        self.assertEqual(1, res.rl_poly_count)

    def test_times(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        times = res.times()
        self.assertEqual(181, len(times))
        times = res.times(fmt='absolute')
        self.assertEqual(181, len(times))

    def test_times_domain_context(self):
        p = './tests/2016/EG14_001_unique_1d_times.tpc'
        res = TPC(p)
        times = res.times('1d')
        self.assertEqual(91, len(times))
        times = res.times('2d')
        self.assertEqual(181, len(times))
        times = res.times('po_point')
        self.assertEqual(181, len(times))
        times = res.times()
        self.assertEqual(181, len(times))

    def test_times_location_context(self):
        p = './tests/2016/EG14_001_dup_2d_dtype.tpc'
        res = TPC(p)
        times = res.times('po_line')
        self.assertEqual(181, len(times))
        times = res.times('po_line_2')
        self.assertEqual(91, len(times))
        times = res.times()
        self.assertEqual(181, len(times))

    def test_data_types(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(22, len(res.data_types()))

    def test_data_types_domain_context(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(9, len(res.data_types('1d')))
        self.assertEqual(3, len(res.data_types('node')))
        self.assertEqual(6, len(res.data_types('channel')))
        self.assertEqual(16, len(res.data_types('po')))
        self.assertEqual(4, len(res.data_types('po/line')))
        self.assertEqual(8, len(res.data_types('po/point')))
        self.assertEqual(5, len(res.data_types('po/polygon')))
        self.assertEqual(3, len(res.data_types('rl')))
        self.assertEqual(1, len(res.data_types('rl/point')))
        self.assertEqual(1, len(res.data_types('rl/line')))
        self.assertEqual(1, len(res.data_types('rl/polygon')))

    def test_data_types_location_context(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(4, len(res.data_types('po_line')))

    def test_ids(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(113, len(res.ids()))

    def test_ids_domain_context(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(54, len(res.ids('channel')))
        self.assertEqual(53, len(res.ids('node')))
        self.assertEqual(107, len(res.ids('1d')))
        self.assertEqual(6, len(res.ids('po/rl')))
        self.assertEqual(3, len(res.ids('rl')))
        self.assertEqual(3, len(res.ids('po')))
        self.assertEqual(2, len(res.ids('rl/point/line')))

    def test_ids_data_type_context(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(55, len(res.ids('h')))
        self.assertEqual(56, len(res.ids('q')))
        self.assertEqual(2, len(res.ids('vol')))

    def test_maximums(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual((1, 4), res.maximum('ds1', ['q', 'v']).shape)
        self.assertEqual((1, 2), res.maximum('ds1.1', ['h']).shape)
        self.assertEqual((1, 2), res.maximum('po_line', 'q').shape)
        self.assertEqual((2, 4), res.maximum('rl/po', 'h').shape)

    def test_time_series(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        ts = res.time_series('po_line', 'flow')
        self.assertEqual((181, 1), ts.shape)
        ts = res.time_series('ds1', 'flow')
        self.assertEqual((181, 1), ts.shape)
        ts = res.time_series(['ds1', 'ds2'], 'flow')
        self.assertEqual((181, 2), ts.shape)
        ts = res.time_series('ds1', ['flow', 'velocity'])
        self.assertEqual((181, 2), ts.shape)
        ts = res.time_series('rl/po', 'q')
        self.assertEqual((181, 2), ts.shape)
        ts = res.time_series('po', None)
        self.assertEqual((181, 17), ts.shape)
        ts = res.time_series(['po_line', 'ds1'], 'q')
        self.assertEqual((181, 2), ts.shape)

    def test_time_series_different_time_index_1d(self):
        p = './tests/2016/EG14_001_unique_1d_times.tpc'
        res = TPC(p)
        ts = res.time_series(['po_line', 'ds1'], 'q')
        self.assertEqual((181, 4), ts.shape)
        ts = res.time_series(['po_line', 'rl_line'], 'flow')
        self.assertEqual((181, 2), ts.shape)

    def test_time_series_different_time_index_po(self):
        p = './tests/2016/EG14_001_dup_2d_dtype.tpc'
        res = TPC(p)
        ts = res.time_series(['po_line', 'po_line_2'], 'q')
        self.assertEqual((181, 4), ts.shape)
        ts = res.time_series(['po_line', 'po_line_2'], 'q', time_fmt='absolute')
        self.assertEqual((181, 4), ts.shape)

    def test_long_plot_result_types(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        self.assertEqual(7, len(res.data_types('section')))

    def test_long_plot(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        df = res.section('ds1', ['bed level', 'water level'], 1)
        self.assertEqual((12, 6), df.shape)

    def test_long_plot_2(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        df = res.section('ds1', ['bed level', 'pipes', 'pits', 'water level'], 1)
        self.assertEqual((12, 8), df.shape)

    def test_long_plot_3(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        df = res.section('ds1', ['bed level', 'water level', 'max water level'], 1)
        self.assertEqual((12, 7), df.shape)

    def test_long_plot_error(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        try:
            df = res.section('ds0', ['bed level', 'water level'], 1)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_long_plot_error_2(self):
        p = './tests/2016/EG14_001.tpc'
        res = TPC(p)
        try:
            df = res.section('ds1', 'lvl', 1)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass


class Test_TPC_NC(TestCase):

    def test_load(self):
        p = './tests/nc_ts/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual('EG15_001', res.name)

    def test_times(self):
        p = './tests/nc_ts/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual(181, len(res.times()))
        self.assertEqual(181, len(res.times(fmt='absolute')))
        self.assertEqual(181, len(res.times('channel')))
        self.assertEqual(181, len(res.times('node')))
        self.assertEqual(181, len(res.times('po')))
        self.assertEqual(181, len(res.times('rl')))

    def test_data_types(self):
        p = './tests/nc_ts/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual(24, len(res.data_types()))
        self.assertEqual(8, len(res.data_types('channel')))
        self.assertEqual(5, len(res.data_types('node')))
        self.assertEqual(16, len(res.data_types('po')))
        self.assertEqual(3, len(res.data_types('rl')))
        self.assertEqual(4, len(res.data_types('po/line')))
        self.assertEqual(10, len(res.data_types('pit10')))
        self.assertEqual(13, len(res.data_types('1d')))

    def test_ids(self):
        p = './tests/nc_ts/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual(58, len(res.ids()))
        self.assertEqual(30, len(res.ids('channel')))
        self.assertEqual(34, len(res.ids('node')))

    def test_maximums(self):
        p = './tests/nc_ts/EG15_001.tpc'
        res = TPC(p)
        df = res.maximum('pit10', 'q')
        self.assertEqual((1, 2), df.shape)
        df = res.maximum('pit10', ['q', 'h'])
        self.assertEqual((1, 4), df.shape)

    def test_time_series(self):
        p = './tests/nc_ts/EG15_001.tpc'
        res = TPC(p)
        df = res.time_series('po_line', 'flow')
        self.assertEqual((181, 1), df.shape)
        df = res.time_series('po', ['q', 'h', 'vol'])
        self.assertEqual((181, 3), df.shape)

    def test_section(self):
        p = './tests/nc_ts/EG15_001.tpc'
        res = TPC(p)
        df = res.section('pipe1', ['bed level', 'max water level'], 0.5)
        self.assertEqual((10, 6), df.shape)


class Test_TPC_2019(TestCase):

    def test_load(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual('EG15_001', res.name)

    def test_channel_count(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, res.channel_count)

    def test_node_count(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(6, res.node_count)

    def test_rl_count(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(1, res.rl_point_count)
        self.assertEqual(1, res.rl_line_count)
        self.assertEqual(1, res.rl_poly_count)

    def test_channel_ids(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.ids('channel')))

    def test_channel_ids_2(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        ids = res.ids('entry loss')
        self.assertEqual(18, len(ids))

    def test_node_ids(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(6, len(res.ids('node')))

    def test_rl_ids(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.ids('rl')))

    def test_time_series(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        ts = res.time_series('FC01.1_R', 'flow')
        self.assertEqual((91, 1), ts.shape)
        ts = res.time_series('RL region 1', 'vol')
        self.assertEqual((91, 1), ts.shape)

    def test_long_plot(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        df = res.section('pipe1', ['bed elevation', 'water level', 'pipes', 'pits'], 1)
        self.assertEqual((10, 8), df.shape)

    def test_all_results(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        df = res.time_series(None, None)
        self.assertEqual((37, 246), df.shape)

    def test_maximums(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        df = res.maximum(None, None)
        self.assertEqual((52, 6), df.shape)


class Test_TPC_GPKG(TestCase):

    def test_load(self):
        p = './tests/tpc_gpkg/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual('EG15_001', res.name)

    def test_times(self):
        p = './tests/tpc_gpkg/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual(181, len(res.times()))

    def test_data_types(self):
        p = './tests/tpc_gpkg/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual(24, len(res.data_types()))

    def test_data_types_context(self):
        p = './tests/tpc_gpkg/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual(4, len(res.data_types('line')))

    def test_ids(self):
        p = './tests/tpc_gpkg/EG15_001.tpc'
        res = TPC(p)
        self.assertEqual(58, len(res.ids()))

    def test_maximums(self):
        p = './tests/tpc_gpkg/EG15_001.tpc'
        res = TPC(p)
        df = res.maximum('Pipe1', 'v')
        self.assertEqual((1, 2), df.shape)
        df = res.maximum('po_point', 'h')
        self.assertEqual((1, 2), df.shape)
        df = res.maximum('po_line', 'qa')
        self.assertEqual((1, 2), df.shape)

    def test_time_series(self):
        p = './tests/tpc_gpkg/EG15_001.tpc'
        res = TPC(p)
        df = res.time_series('pit2', ['h', 'q'])
        self.assertEqual((181, 2), df.shape)

    def test_section(self):
        p = './tests/tpc_gpkg/EG15_001.tpc'
        res = TPC(p)
        df = res.section('pipe1', ['Bed Level', 'water level'], 1)
        self.assertEqual((10, 6), df.shape)


class Test_TPC_Frankenmodel(TestCase):

    def test_load(self):
        p = './tests/2021/frankenmodel.tpc'
        res = TPC(p)
        self.assertEqual('frankenmodel', res.name)

    def test_times(self):
        p = './tests/2021/frankenmodel.tpc'
        res = TPC(p)
        times = res.times()
        self.assertEqual(73, len(times))
        times = res.times('2d')
        self.assertEqual(73, len(times))
        times = res.times('1d')
        self.assertEqual(0, len(times))
        times = res.times('ADCP1')
        self.assertEqual(73, len(times))

    def test_ids(self):
        p = './tests/2021/frankenmodel.tpc'
        res = TPC(p)
        ids = res.ids()
        self.assertEqual(9, len(ids))
        ids = res.ids('2d')
        self.assertEqual(9, len(ids))
        ids = res.ids('h')
        self.assertEqual(3, len(ids))
        ids = res.ids('sal')
        self.assertEqual(3, len(ids))
        ids = res.ids('salt flux')
        self.assertEqual(6, len(ids))
        ids = res.ids('sed 1 flux')
        self.assertEqual(6, len(ids))

    def test_data_types(self):
        p = './tests/2021/frankenmodel.tpc'
        res = TPC(p)
        dtypes = res.data_types()
        self.assertEqual(18, len(dtypes))
        dtypes = res.data_types('ADCP1')
        self.assertEqual(9, len(dtypes))
        dtypes = res.data_types('ns1')
        self.assertEqual(9, len(dtypes))

    def test_maximums(self):
        p = './tests/2021/frankenmodel.tpc'
        res = TPC(p)
        df = res.maximum('ADCP1', 'tracer 1 conc')
        self.assertEqual((1, 2), df.shape)
        df = res.maximum('ADCP1', 'tracer conc')
        self.assertTrue(df.empty)

    def test_time_series(self):
        p = './tests/2021/frankenmodel.tpc'
        res = TPC(p)
        ts = res.time_series(None, None)
        self.assertEqual((73, 81), ts.shape)
        ts = res.time_series('ADCP1', None)
        self.assertEqual((73, 9), ts.shape)
        ts = res.time_series('ns1', 'sed 1 bedload flux')
        self.assertEqual((73, 1), ts.shape)


class Test_GPKG1D(TestCase):

    def test_load(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        self.assertEqual('M06_5m_003_SWMM', res.name)

    def test_load_2(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        self.assertEqual('EG15_001', res.name)

    def test_not_gpkg(self):
        p = './tests/2023/projection.gpkg'
        try:
            res = GPKG1D(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_channel_count(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        self.assertEqual(18, res.channel_count)

    def test_channel_count_2(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        self.assertEqual(30, res.channel_count)

    def test_node_count(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        self.assertEqual(22, res.node_count)

    def test_node_count_2(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        self.assertEqual(34, res.node_count)

    def test_times(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        ts = res.times()
        self.assertEqual(37, len(ts))

    def test_times_2(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        ts = res.times()
        self.assertEqual(181, len(ts))

    def test_channel_ids(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        self.assertEqual(18, len(res.ids('channel')))

    def test_channel_ids_2(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        self.assertEqual(30, len(res.ids('channel')))

    def test_node_ids(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        self.assertEqual(22, len(res.ids('node')))

    def test_node_ids_2(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        self.assertEqual(34, len(res.ids('node')))

    def test_channel_result_types(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        self.assertEqual(5, len(res.data_types('channel')))

    def test_channel_result_types_2(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        self.assertEqual(9, len(res.data_types('channel')))

    def test_node_result_types(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        self.assertEqual(7, len(res.data_types('node')))

    def test_node_result_types_2(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        self.assertEqual(5, len(res.data_types('node')))

    def test_time_series(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        ts = res.time_series('FC01.1_R', ['q', 'v'])
        self.assertEqual((37, 2), ts.shape)

    def test_time_series_2(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        ts = res.time_series('FC01.1_R', ['q', 'v'])
        self.assertEqual((181, 2), ts.shape)

    def test_long_plot(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        df = res.section('pipe1', ['Bed Level', 'water level'], 1)
        self.assertEqual((10, 6), df.shape)

    def test_long_plot2(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        df = res.section('pipe1', ['bed level', 'pipes', 'pits'], 1)
        self.assertEqual((10, 7), df.shape)

    def test_long_plot3(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        df = res.section('pipe1', ['bed level', 'pipes', 'water level', 'max h'], 1)
        self.assertEqual((10, 8), df.shape)

    def test_long_plot4(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        df = res.section('pipe1', ['bed level', 'pipes', 'water level'], 1)
        self.assertEqual((10, 7), df.shape)

    def test_long_plot5(self):
        p = './tests/2023/EG15_001_TS_1D.gpkg'
        res = GPKG1D(p)
        df = res.section('pipe1', ['bed level', 'pipes', 'pits'], 1)
        self.assertEqual((10, 7), df.shape)

    def test_maximums_2(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        df = res.maximum('pipe1', 'q')
        self.assertEqual((1, 2), df.shape)

    def test_maximums_3(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        df = res.maximum('pipe1', None)
        self.assertEqual((1, 10), df.shape)

    def test_maximums_4(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG1D(p)
        df = res.maximum(['Pipe1', 'Pipe2', 'pipe3'], None)
        self.assertEqual((3, 10), df.shape)


class Test_GPKG2D(TestCase):

    def test_load(self):
        p = './tests/tpc_gpkg/EG15_001_TS_2D.gpkg'
        res = GPKG2D(p)
        self.assertEqual('EG15_001', res.name)

    def test_times(self):
        p = './tests/tpc_gpkg/EG15_001_TS_2D.gpkg'
        res = GPKG2D(p)
        self.assertEqual(181, len(res.times()))

    def test_data_types(self):
        p = './tests/tpc_gpkg/EG15_001_TS_2D.gpkg'
        res = GPKG2D(p)
        self.assertEqual(16, len(res.data_types()))
        # self.assertEqual(4, len(res.data_types('line')))  # source results are wrong

    def test_ids(self):
        p = './tests/tpc_gpkg/EG15_001_TS_2D.gpkg'
        res = GPKG2D(p)
        self.assertEqual(3, len(res.ids()))

    def test_maximums(self):
        p = './tests/tpc_gpkg/EG15_001_TS_2D.gpkg'
        res = GPKG2D(p)
        df = res.maximum('po_point', 'h')
        self.assertEqual((1, 2), df.shape)

    def test_time_series(self):
        p = './tests/tpc_gpkg/EG15_001_TS_2D.gpkg'
        res = GPKG2D(p)
        df = res.time_series('po_poly', 'vol')
        self.assertEqual((181, 1), df.shape)


class Test_GPKGRL(TestCase):

    def test_load(self):
        p = './tests/tpc_gpkg/EG15_001_TS_RL.gpkg'
        res = GPKGRL(p)
        self.assertEqual('EG15_001', res.name)

    def test_times(self):
        p = './tests/tpc_gpkg/EG15_001_TS_RL.gpkg'
        res = GPKGRL(p)
        self.assertEqual(181, len(res.times()))

    def test_data_types(self):
        p = './tests/tpc_gpkg/EG15_001_TS_RL.gpkg'
        res = GPKGRL(p)
        self.assertEqual(3, len(res.data_types()))
        # self.assertEqual(4, len(res.data_types('line')))  # source results are wrong

    def test_ids(self):
        p = './tests/tpc_gpkg/EG15_001_TS_RL.gpkg'
        res = GPKGRL(p)
        self.assertEqual(3, len(res.ids()))

    def test_maximums(self):
        p = './tests/tpc_gpkg/EG15_001_TS_RL.gpkg'
        res = GPKGRL(p)
        df = res.maximum('rl_point', 'h')
        self.assertEqual((1, 2), df.shape)

    def test_time_series(self):
        p = './tests/tpc_gpkg/EG15_001_TS_RL.gpkg'
        res = GPKGRL(p)
        df = res.time_series('rl_point', 'h')
        self.assertEqual((181, 1), df.shape)


class Test_FM_TS(unittest.TestCase):

    def test_gxy(self):
        p = './tests/fm/zzn/FMT_M01_001.gxy'
        gxy = GXY(p)
        self.assertEqual((115, 2), gxy.node_df.shape)
        self.assertEqual((122, 2), gxy.link_df.shape)

    def test_load(self):
        from pytuflow.fm import DAT
        p = './tests/fm/zzn/FMT_M01_001.dat'
        dat = DAT(p)
        self.assertEqual(115, len(dat.units))
        self.assertEqual(2, len(dat.unit('JUNCTION_OPEN_FC02.01d').ups_units))

    def test_load_2(self):
        from pytuflow.fm import DAT
        p = './tests/fm/gui_csv/LBE_TBP3_10PC_350.dat'
        dat = DAT(p)
        self.assertEqual(242, len(dat.units))

    def test_load_3(self):
        from pytuflow.fm import DAT
        p = './tests/fm/River_Sections_w_Junctions.dat'
        dat = DAT(p)
        self.assertEqual(1, len(dat.unit('RIVER_SECTION_US_2').dns_units))
        self.assertEqual(2, len(dat.unit('JUNCTION_OPEN_US_3').dns_units))
        self.assertEqual(2, len(dat.unit('JUNCTION_OPEN_DS_3').ups_units))

    def test_load_python_csv(self):
        p = './tests/fm/python_csv/FMT_M01_001.csv'
        res = FMTS(p)
        self.assertEqual('FMT_M01_001', res.name)

    def test_load_gui_csv_without_header_all_results(self):
        p = './tests/fm/gui_csv/LBE_TBP3_0100F_BASE_350_BM_HPC_GPU_one_column_per_node_all.csv'
        res = FMTS(p, None, None)
        self.assertEqual('LBE_TBP3_0100F_BASE_350_BM_HPC_GPU_one_column_per_node_all', res.name)

    def test_load_gui_csv_with_header_all_results(self):
        p = './tests/fm/gui_csv/LBE_TBP3_0100F_BASE_350_BM_HPC_GPU_one_column_per_node_all_header.csv'
        res = FMTS(p, None, None)
        self.assertEqual('LBE_TBP3_0100F_BASE_350_BM_HPC_GPU', res.name)

    def test_load_zzn(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        res = FMTS(p, None, None)
        self.assertEqual('FMT_M01_001', res.name)

    def test_load_with_dat(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        res = FMTS(p, dat)
        self.assertEqual('FMT_M01_001', res.name)

    def test_load_with_gxy(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FMTS(p, None, gxy)
        self.assertEqual('FMT_M01_001', res.name)

    def test_load_nodes(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FMTS(p, dat, gxy)
        self.assertEqual(115, res.node_count)

    def test_load_channels(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FMTS(p, dat, gxy)
        self.assertEqual(122, res.channel_count)

    def test_times(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        res = FMTS(p, dat)
        ts = res.times()
        self.assertEqual(37, len(ts))
        ts = res.times(fmt='absolute')
        self.assertEqual(37, len(ts))
        ts = res.times('FC01.34')
        self.assertEqual(37, len(ts))

    def test_ids(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        res = FMTS(p, dat)
        self.assertEqual(103, len(res.ids()))
        self.assertEqual(115, len(res.ids('node')))
        self.assertEqual(122, len(res.ids('channel')))

    def test_data_types(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        res = FMTS(p, dat)
        self.assertEqual(6, len(res.data_types()))
        self.assertEqual(6, len(res.data_types('node')))
        self.assertEqual(0, len(res.data_types('channel')))

    def test_lp_types(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        res = FMTS(p, dat)
        self.assertEqual(14, len(res.data_types('section')))

    def test_maximums(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        res = FMTS(p, dat)
        df = res.maximum('FC01.25', 'flow')
        self.assertEqual((1, 2), df.shape)

    def test_timeseries(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        res = FMTS(p, dat)
        ts = res.time_series('FC01.25', 'h')
        self.assertEqual((37, 1), ts.shape)

    def test_lp(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        res = FMTS(p, dat)
        df = res.section('FC01.11', ['bed level', 'water level'], 1)
        self.assertEqual((200, 6), df.shape)
        df = res.section('FC01.11', ['bed level', 'max water level', 'pipes'], -1)
        self.assertEqual((200, 7), df.shape)

    def test_lp_incorrect_id(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        res = FMTS(p, dat)
        df = res.section(['fco1.31', 'fc01.25'], 'max stage', -1)
        self.assertEqual((450, 5), df.shape)


class Test_HydTables(unittest.TestCase):

    def test_load(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        self.assertEqual(res.name, 'EG14_001')

    def test_load_2(self):  # all cross-sections are in one CSV file
        p = './tests/hyd_tables/EG14_CONCAT_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        self.assertEqual(res.name, 'EG14_CONCAT_001')

    def test_load_3(self):  # HW table mingled in
        p = './tests/hyd_tables/EG14_CONCAT_HW_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        self.assertEqual(res.name, 'EG14_CONCAT_HW_001')

    def test_not_hyd_tables(self):
        p = './tests/bc_tables/EG14_001_1d_bc_tables_check.csv'
        try:
            res = HydTablesCheck(p)
            raise AssertionError('Should have raised an exception')
        except FileTypeError:
            pass

    def test_empty_hyd_tables(self):
        p = './tests/hyd_tables/EG14_001_empty_1d_ta_tables_check.csv'
        try:
            res = HydTablesCheck(p)
            raise AssertionError('Should have raised an exception')
        except EOFError:
            pass

    def test_cross_section_count(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        self.assertEqual(55, res.cross_section_count)

    def test_cross_section_count_2(self):
        p = './tests/hyd_tables/EG14_CONCAT_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        self.assertEqual(55, res.cross_section_count)

    def test_cross_section_count_3(self):
        p = './tests/hyd_tables/EG14_CONCAT_HW_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        self.assertEqual(55, res.cross_section_count)

    def test_channel_count(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        self.assertEqual(52, res.channel_count)

    def test_ids(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        ids = res.ids()
        self.assertEqual(107, len(ids))

    def test_ids_2(self):
        p = './tests/hyd_tables/EG14_CONCAT_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        ids = res.ids()
        self.assertEqual(107, len(ids))

    def test_ids_3(self):
        p = './tests/hyd_tables/EG14_CONCAT_HW_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        ids = res.ids()
        self.assertEqual(107, len(ids))

    def test_ids_ctx(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        ids = res.ids('channel')
        self.assertEqual(52, len(ids))
        ids = res.ids('xs')
        self.assertEqual(55, len(ids))
        ids = res.ids('proc')
        self.assertEqual(55, len(ids))
        ids = res.ids('elevation')
        self.assertEqual(55, len(ids))
        ids = res.ids('xz')
        self.assertEqual(55, len(ids))
        ids = res.ids('hw')
        self.assertEqual(0, len(ids))

    def test_ids_ctx_2(self):
        p = './tests/hyd_tables/EG14_CONCAT_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        ids = res.ids('channel')
        self.assertEqual(52, len(ids))
        ids = res.ids('xs')
        self.assertEqual(55, len(ids))
        ids = res.ids('proc')
        self.assertEqual(55, len(ids))
        ids = res.ids('elevation')
        self.assertEqual(55, len(ids))
        ids = res.ids('xz')
        self.assertEqual(55, len(ids))
        ids = res.ids('hw')
        self.assertEqual(0, len(ids))

    def test_ids_ctx_3(self):
        p = './tests/hyd_tables/EG14_CONCAT_HW_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        ids = res.ids('channel')
        self.assertEqual(52, len(ids))
        ids = res.ids('xs')
        self.assertEqual(54, len(ids))
        ids = res.ids('proc')
        self.assertEqual(55, len(ids))
        ids = res.ids('elevation')
        self.assertEqual(54, len(ids))
        ids = res.ids('xz')
        self.assertEqual(54, len(ids))
        ids = res.ids('hw')
        self.assertEqual(1, len(ids))

    def test_data_types(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        dtypes = res.data_types()
        self.assertEqual(14, len(dtypes))

    def test_data_types_2(self):
        p = './tests/hyd_tables/EG14_CONCAT_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        dtypes = res.data_types()
        self.assertEqual(14, len(dtypes))

    def test_data_types_3(self):
        p = './tests/hyd_tables/EG14_CONCAT_HW_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        dtypes = res.data_types()
        self.assertEqual(14, len(dtypes))

    def test_data_types_ctx(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        dtypes = res.data_types('xs')
        self.assertEqual(2, len(dtypes))
        dtypes = res.data_types('processed')
        self.assertEqual(8, len(dtypes))
        dtypes = res.data_types('XZ')
        self.assertEqual(10, len(dtypes))
        dtypes = res.data_types('FC01.25')
        self.assertEqual(8, len(dtypes))

    def test_section(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        df = res.section(['FC01.25', 'FC01.39'], 'flow width')
        self.assertEqual((39, 4), df.shape)

    def test_section_2(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTablesCheck(p)
        df = res.section('1d_xs_M14_C121', 'elev')
        self.assertEqual((30, 2), df.shape)


class Test_BC_Tables(unittest.TestCase):

    def test_load_2d_bc_tables(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        self.assertEqual('EG00_001', res.name)

    def test_load_1d_bc_tables(self):
        p = './tests/bc_tables/EG14_001_1d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        self.assertEqual('EG14_001', res.name)

    def test_not_bc_tables(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        try:
            res = BCTablesCheck(p)
            raise AssertionError('Should have raised an exception')
        except FileTypeError:
            pass

    def test_emtpy_bc_tables(self):
        p = './tests/bc_tables/EG00_001_empty_2d_bc_tables_check.csv'
        try:
            res = BCTablesCheck(p)
            raise AssertionError('Should have raised an exception')
        except EOFError:
            pass

    def test_times(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        times = res.times()
        self.assertEqual(41, len(times))

    def test_times_ctx(self):
        p = './tests/bc_tables/EG14_001_1d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        times = res.times('QT')
        self.assertEqual(41, len(times))
        times = res.times('FC01')
        self.assertEqual(41, len(times))

    def test_ids(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        ids = res.ids()
        self.assertEqual(2, len(ids))

    def test_ids_2(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        ids = res.ids('QT')
        self.assertEqual(1, len(ids))

    def test_ids_3(self):
        p = './tests/bc_tables/EG14_001_1d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        ids = res.ids()
        self.assertEqual(2, len(ids))

    def test_ids_4(self):
        p = './tests/bc_tables/EG14_001_1d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        ids = res.ids('BC000001')
        self.assertEqual(1, len(ids))

    def test_data_types(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        rts = res.data_types()
        self.assertEqual(2, len(rts))

    def test_data_types_2(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        rts = res.data_types('FC01')
        self.assertEqual(1, len(rts))

    def test_time_series(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        df = res.time_series('FC01', 'QT')
        self.assertEqual((41, 2), df.shape)

    def test_time_series_2(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        df = res.time_series(None, None)
        self.assertEqual((102, 4), df.shape)

    def test_maximums(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        df = res.maximum('FC01', None)
        self.assertEqual((1, 2), df.shape)

    def test_maximums_2(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        df = res.maximum(None, None)
        self.assertEqual((1, 2), df.shape)

    def test_section(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTablesCheck(p)
        try:
            df = res.section('FC01', ['HQ'], 1)
            raise Exception('Should have raised a NotImplementedError')
        except NotImplementedError as e:
            pass


class Test_FVBCTide(unittest.TestCase):

    def test_load(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        self.assertEqual('Cudgen_Tide', res.name)
        self.assertEqual('Cudgen_Tide[TZ:UTC]', res.name_tz)

    def test_not_fv_bc_tide(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        try:
            res = FVBCTide(p, p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_ids(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        ids = res.ids()
        self.assertEqual(13, len(ids))

    def test_node_ids(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        ids = res.ids('node')
        self.assertEqual(12, len(ids))

    def test_node_count(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        self.assertEqual(12, res.node_count)

    def test_node_string_ids(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        ids = res.ids('line')
        self.assertEqual(1, len(ids))

    def test_node_string_count(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        self.assertEqual(1, res.node_string_count)

    def test_result_types(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        rts = res.data_types()
        self.assertEqual(1, len(rts))

    def test_node_result_types(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        rts = res.data_types('node')
        self.assertEqual(1, len(rts))
        rts = res.data_types('Ocean_pt_1')
        self.assertEqual(1, len(rts))

    def test_node_string_result_types(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        rts = res.data_types('nodestring')
        self.assertEqual(1, len(rts))

    def test_long_plot_result_types(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        rts = res.data_types('section')
        self.assertEqual(['water level'], rts)

    def test_timesteps(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        timesteps = res.times()
        self.assertEqual(3073, len(timesteps))
        timesteps = res.times(fmt='absolute')

    def test_maximums(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        mx = res.maximum('Ocean_pt_1', 'h')
        self.assertEqual((1, 2), mx.shape)

    def test_time_series(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        ts = res.time_series('Ocean_pt_1', 'h')
        self.assertEqual((3073, 1), ts.shape)

    def test_long_plot(self):
        nc = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/Cudgen_Tide.nc'
        ns = './tests/fv_bc_tide/Cudgen_Nodestrings_MGA56/2d_ns_Cudgen_004_OceanBoundary_L.shp'
        res = FVBCTide(nc, ns)
        lp = res.section('Ocean', 'h', 12083.9795)
        self.assertEqual((12, 4), lp.shape)


class Test_CrossSections(unittest.TestCase):

    def test_load(self):
        p = './tests/cross_sections/gis/1d_xs_EG14_001_L.shp'
        res = CrossSections(p)
        self.assertEqual('1d_xs_EG14_001_L', res.name)
        self.assertEqual(55, res.cross_section_count)

    def test_ids(self):
        p = './tests/cross_sections/gis/1d_xs_EG14_001_L.shp'
        res = CrossSections(p)
        ids = res.ids()
        self.assertEqual(55, len(ids))

    def test_ids_ctx(self):
        p = './tests/cross_sections/gis/1d_xs_EG14_001_L.shp'
        res = CrossSections(p)
        ids = res.ids('1d_xs_M14_C100.csv')
        self.assertEqual(1, len(ids))
        ids = res.ids('xz')
        self.assertEqual(55, len(ids))

    def test_data_types(self):
        p = './tests/cross_sections/gis/1d_xs_EG14_001_L.shp'
        res = CrossSections(p)
        dtypes = res.data_types()
        self.assertEqual(1, len(dtypes))

    def test_section(self):
        p = './tests/cross_sections/gis/1d_xs_EG14_001_L.shp'
        res = CrossSections(p)
        df = res.section('1d_xs_M14_C100.csv', None)
        self.assertEqual((30, 2), df.shape)

    def test_section_2(self):
        p = './tests/cross_sections/gis/1d_xs_EG14_001_L.shp'
        res = CrossSections(p)
        df = res.section(['1d_xs_M14_C100.csv', r'..\csv\1d_xs_M14_C130.csv:1d_xs_M14_C130'], None)
        self.assertEqual((30, 4), df.shape)

    def test_section_3(self):
        p = './tests/cross_sections/gis/1d_xs_EG14_001_L.shp'
        res = CrossSections(p)
        xs = './tests/cross_sections/csv/1d_xs_M14_C100.csv'
        xs = os.path.abspath(xs)
        df = res.section(xs, None)
        self.assertEqual((30, 2), df.shape)
