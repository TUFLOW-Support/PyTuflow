import unittest
from datetime import datetime
from unittest import TestCase

from pytuflow.results.bc_tables.bc_tables import BCTables
from pytuflow.results.fm.fm import FM_TS
from pytuflow.results.fm.fm_nodes import FMNodes
from pytuflow.results.fm.gxy import GXY
from pytuflow.results.hyd_tables.hyd_tables import HydTables
from pytuflow.results.info.info import Info
from pytuflow.results.tpc.tpc import TPC
from pytuflow.results.gpkg_ts.gpkg_ts import GPKG_TS
from pytuflow.results.iterator_util import Iterator


class Test_TPC_2016(TestCase):

    def test_load(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual('M04_5m_001', res.sim_id)

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
        except ValueError:
            pass

    def test_empty_results(self):
        p = './tests/2016/EG00_001.tpc'
        try:
            tpc = TPC(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_channel_count(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(54, res.channel_count())

    def test_node_count(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(55, res.node_count())

    def test_po_count(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(4, res.po_count())

    def test_rl_count(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, res.rl_count())

    def test_channel_ids(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(54, len(res.channel_ids()))

    def test_channel_ids_error(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        try:
            ids = res.channel_ids('level')
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_ids_error(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        # works
        ids = res.ids('level', '1d')
        # doesn't work
        try:
            ids = res.ids('levl', '1d')  # misspell
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_node_ids(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(55, len(res.node_ids()))

    def test_po_ids(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(4, len(res.po_ids()))

    def test_rl_ids(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.rl_ids()))

    def test_channel_result_types(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.channel_result_types()))

    def test_node_result_types(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(2, len(res.node_result_types()))

    def test_node_result_types_error(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        try:
            rts = res.node_result_types('ds1')
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_result_types_error(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        # works
        rts = res.result_types('ds1')
        # doesn't work
        try:
            rts = res.result_types('ds0')  # doesn't exist in any result item
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_po_result_types(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(8, len(res.po_result_types()))

    def test_rl_result_types(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.rl_result_types()))

    def test_result_types(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(9, len(res.result_types()))
        self.assertEqual(3, len(res.result_types('ds1')))
        self.assertEqual(1, len(res.result_types('test')))
        self.assertEqual(3, len(res.result_types('test_2')))

    def test_ids(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.ids('flow')), 55)

    def test_ids2(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.ids()), 113)

    def test_maximums(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.rl.maximums.df
        self.assertEqual((3, 14), df.shape)

    def test_maximums_2(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual((1, 4), res.maximum('ds1', ['q', 'v']).shape)

    def test_maximums_po(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.po.maximums.df
        self.assertEqual((4, 16), df.shape)

    def test_maximums_po_2(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual((1, 4), res.maximum('test', 'flow').shape)

    def test_time_series(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        ts = res.time_series('test', 'flow')
        self.assertEqual((181, 2), ts.shape)
        ts = res.time_series('ds1', 'flow')
        self.assertEqual((181, 1), ts.shape)
        ts = res.time_series(['ds1', 'ds2'], 'flow')
        self.assertEqual((181, 2), ts.shape)
        ts = res.time_series('ds1', ['flow', 'velocity'])
        self.assertEqual((181, 2), ts.shape)

    def test_time_series_2(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        ts = res.time_series('ds1', 'Q')
        self.assertEqual((181, 1), ts.shape)

    def test_time_series_error(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        try:
            ts = res.time_series('ds0', 'Q')
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_connectivity(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.connectivity(['ds1', 'ds4'])
        self.assertEqual((4, 10), df.shape)

    def test_long_plot_result_types(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(7, len(res.long_plot_result_types()))

    def test_long_plot(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.long_plot('ds1', ['bed level', 'water level'], 1)
        self.assertEqual((12, 5), df.shape)

    def test_long_plot_2(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.long_plot('ds1', ['bed level', 'pipes', 'pits', 'water level'], 1)
        self.assertEqual((12, 7), df.shape)

    def test_long_plot_3(self):
        p = './tests/2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.long_plot('ds1', ['bed level', 'water level', 'max water level'], 1)
        self.assertEqual((12, 7), df.shape)


class Test_TPC_2019(TestCase):

    def test_load(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual('M03_5m_001', res.sim_id)
        self.assertEqual(datetime(2000, 1, 1), res.reference_time)
        df = res.nodes.time_series['Water Level'].df
        df = res.nodes.time_series['Energy'].df
        df = res.channels.time_series['Flow'].df
        df = res.channels.time_series['Velocity'].df
        df = res.channels.time_series['Flow Area'].df
        df = res.rl.time_series['Flow'].df
        df = res.rl.time_series['Water Level'].df
        df = res.rl.time_series['Volume'].df

    def test_channel_count(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, res.channel_count())

    def test_node_count(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(6, res.node_count())

    def test_rl_count(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, res.rl_count())

    def test_channel_ids(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.channel_ids()))

    def test_channel_ids_2(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        ids = res.channel_ids('entry loss')
        self.assertEqual(18, len(ids))

    def test_node_ids(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(6, len(res.node_ids()))

    def test_rl_ids(self):
        p = './tests/2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.rl_ids()))

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
        df = res.long_plot('pipe1', ['bed elevation', 'water level', 'pipes', 'pits'], 1)
        self.assertEqual((10, 7), df.shape)

    def test_all_results(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        df = res.time_series(None, None)
        self.assertEqual((37, 212), df.shape)

    def test_maximum_types(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        result_types = res.maximum_result_types()
        self.assertEqual(3, len(result_types))

    def test_maximum_types_2(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        result_types = res.maximum_result_types('FC01.1_R')
        self.assertEqual(2, len(result_types))

    def test_maximums(self):
        p = './tests/2020/EG15_001.tpc'
        res = TPC(p)
        df = res.maximum(None, None)
        self.assertEqual((52, 6), df.shape)


class Test_GPKG_TS_2023(TestCase):

    def test_load(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual('M06_5m_003_SWMM', res.sim_id)

    def test_not_gpkg(self):
        p = './tests/2023/projection.gpkg'
        try:
            res = GPKG_TS(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_channel_count(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(18, res.channel_count())

    def test_node_count(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(22, res.node_count())

    def test_channel_ids(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(18, len(res.channel_ids()))

    def test_node_ids(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(22, len(res.node_ids()))

    def test_channel_result_types(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(5, len(res.channel_result_types()))

    def test_node_result_types(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(7, len(res.node_result_types()))

    def test_ids(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(40, len(res.ids('flow')))

    def test_timesteps(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        ts = res.timesteps()
        self.assertEqual(37, len(ts))

    def test_time_series(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        ts = res.time_series('FC01.1_R', ['q', 'v'])
        self.assertEqual((37, 2), ts.shape)

    def test_connectivity(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.connectivity(['pipe2'])
        self.assertEqual((7, 10), df.shape)

    def test_long_plot(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.long_plot('pipe1', ['bed level', 'water level'], 1)
        self.assertEqual((10, 5), df.shape)

    def test_long_plot2(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.long_plot('pipe1', ['bed level', 'pipes', 'pits'], 1)
        self.assertEqual((10, 6), df.shape)

    def test_long_plot3(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.long_plot('pipe1', ['bed level', 'pipes', 'water level', 'max h'], 1)
        self.assertEqual((10, 8), df.shape)

    def test_long_plot4(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.long_plot('pipe1', ['bed level', 'pipes', 'water level', 'energy'], 1)
        self.assertEqual((10, 6), df.shape)

    def test_maximum_types(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        result_types = res.maximum_result_types()
        self.assertEqual(12, len(result_types))

    def test_maximums(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.nodes.maximums.df
        self.assertEqual((22, 14), df.shape)

    def test_maximums_2(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.maximum('pipe1', 'q')
        self.assertEqual((1, 2), df.shape)

    def test_maximums_3(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.maximum('pipe1', None)
        self.assertEqual((1, 10), df.shape)

    def test_maximums_4(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.maximum(['Pipe1', 'Pipe2', 'pipe3'], None)
        self.assertEqual((3, 10), df.shape)


class Test_Iterator(TestCase):

    def test_get_nodes(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        iter = Iterator(res.channels, res.nodes, res.po, res.rl)
        items = iter._corrected_items(['node20'], ['flow'], 'node', 'temporal', res.nodes)
        self.assertEqual(1, len(items))
        self.assertIsNotNone(items[0].id)
        self.assertIsNotNone(items[0].result_type)

    def test_get_nodes_2(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        iter = Iterator(res.channels, res.nodes, res.po, res.rl)
        items = iter._corrected_items([], ['flow'], 'node', 'temporal', res.nodes)
        self.assertEqual(22, len(items))

    def test_get_nodes_3(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        iter = Iterator(res.channels, res.nodes, res.po, res.rl)
        items = iter._corrected_items(['node20'], [], 'node', 'temporal', res.nodes)
        self.assertEqual(7, len(items))

    def test_id_result_type_gen(self):
        p = './tests/2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        iter = Iterator(res.channels, res.nodes, res.po, res.rl)
        items = list(iter.id_result_type(['node20'], ['flow'], None, 'temporal'))
        self.assertEqual(1, len(items))


class Test_FM_TS(unittest.TestCase):

    def test_gxy(self):
        p = './tests/fm/zzn/FMT_M01_001.gxy'
        gxy = GXY(p)
        self.assertEqual((115, 2), gxy.node_df.shape)
        self.assertEqual((122, 2), gxy.link_df.shape)

    def test_import(self):
        from pytuflow.results.fm.dat import Dat
        from pytuflow.results.fm.dat import available_classes
        from pytuflow.results.fm.dat import UNITS_DIR
        self.assertEqual(len(list(UNITS_DIR.glob('*.py')))-2, len(available_classes))

    def test_load(self):
        from pytuflow.results.fm.dat import Dat
        p = './tests/fm/zzn/FMT_M01_001.dat'
        dat = Dat(p)
        self.assertEqual(67, len(dat._units_id))

    def test_load_2(self):
        from pytuflow.results.fm.dat import Dat
        p = './tests/fm/gui_csv/LBE_TBP3_10PC_350.dat'
        dat = Dat(p)
        self.assertEqual(161, len(dat._units_id))

    def test_load_python_csv(self):
        p = './tests/fm/python_csv/FMT_M01_001.csv'
        res = FM_TS(p, None, None)
        self.assertEqual('FMT_M01_001', res.sim_id)

    def test_load_gui_csv_without_header_all_results(self):
        p = './tests/fm/gui_csv/LBE_TBP3_0100F_BASE_350_BM_HPC_GPU_one_column_per_node_all.csv'
        res = FM_TS(p, None, None)
        self.assertEqual('LBE_TBP3_0100F_BASE_350_BM_HPC_GPU_one_column_per_node_all', res.sim_id)

    def test_load_gui_csv_with_header_all_results(self):
        p = './tests/fm/gui_csv/LBE_TBP3_0100F_BASE_350_BM_HPC_GPU_one_column_per_node_all_header.csv'
        res = FM_TS(p, None, None)
        self.assertEqual('LBE_TBP3_0100F_BASE_350_BM_HPC_GPU', res.sim_id)

    def test_load_zzn(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        res = FM_TS(p, None, None)
        self.assertEqual('FMT_M01_001', res.sim_id)

    def test_load_nodes(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FM_TS(p, gxy, dat)
        self.assertEqual(6, len(res.nodes.time_series))
        self.assertEqual((37, 103), res.nodes.time_series['Flow'].df.shape)

    def test_load_nodes_2(self):
        from pytuflow.results.fm.dat import Dat
        p = './tests/dummy'
        gxy = GXY('./tests/fm/zzn/FMT_M01_001.gxy')
        dat = Dat('./tests/fm/zzn/FMT_M01_001.dat')
        id_list = list(dat._units_id.keys())
        fm_node = FMNodes(p, id_list, gxy, dat)
        self.assertEqual((67, 4), fm_node.df.shape)

    def test_load_channels(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FM_TS(p, gxy, dat)
        self.assertEqual((60, 11), res.channels.df.shape)

    def test_fm_channels(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FM_TS(p, gxy, dat)
        self.assertEqual(122, len(res.channel_ids()))

    def test_lp_types(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FM_TS(p, gxy, dat)
        self.assertEqual(['Bed Level', 'Stage', 'Stage Max'], res.long_plot_result_types())

    def test_lp(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FM_TS(p, gxy, dat)
        df = res.long_plot('FC01.25', ['bed level', 'water level'], 1)
        self.assertEqual((8, 5), df.shape)

    def test_maximums(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FM_TS(p, gxy, dat)
        df = res.maximum('FC01.25', 'flow')
        self.assertEqual((1, 2), df.shape)

    def test_timeseries(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FM_TS(p, gxy, dat)
        ts = res.time_series('FC01.25', 'h')
        self.assertEqual((37, 1), ts.shape)

    def test_timesteps(self):
        p = './tests/fm/zzn/FMT_M01_001.zzn'
        dat = './tests/fm/zzn/FMT_M01_001.dat'
        gxy = './tests/fm/zzn/FMT_M01_001.gxy'
        res = FM_TS(p, gxy, dat)
        ts = res.timesteps()
        self.assertEqual(37, len(ts))
        ts = res.timesteps(dtype='absolute')
        self.assertEqual(37, len(ts))


class Test_Info_2013(unittest.TestCase):

    def test_load(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = Info(p)
        self.assertEqual('M04_5m_001', res.sim_id)

    def test_not_info(self):
        p = './tests/2013/EG00_001_Scen_1+Scen_2.2dm.info'
        try:
            res = Info(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_blank_info(self):
        p = './tests/2013/M04_5m_001_1d_blank.info'
        try:
            res = Info(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_channels(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = Info(p)
        self.assertEqual(54, res.channel_count())
        self.assertEqual(54, len(res.channel_ids()))

    def test_nodes(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = Info(p)
        self.assertEqual(55, res.node_count())
        self.assertEqual(55, len(res.node_ids()))

    def test_time_series(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = Info(p)
        ts = res.time_series('ds1', 'q')
        self.assertEqual((181, 1), ts.shape)
        ts = res.time_series(['FC01.24.1', 'FC01.25.1'], 'h')
        self.assertEqual((181, 2), ts.shape)

    def test_maximums(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = Info(p)
        df = res.maximum(['ds1', 'ds2'], ['flow', 'velocity'])
        self.assertEqual((2, 4), df.shape)
        df = res.maximum(['FC01.24.1', 'FC01.25.1'], ['h'])
        self.assertEqual((2, 2), df.shape)

    def test_long_plot_result_types(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = Info(p)
        self.assertEqual(5, len(res.long_plot_result_types()))

    def test_long_plot(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = Info(p)
        df = res.long_plot('ds1', ['bed level', 'water level', 'max water level'], 1)
        self.assertEqual((12, 7), df.shape)

    def test_long_plot_2(self):
        p = './tests/2013/M04_5m_001_1d.info'
        res = Info(p)
        df = res.long_plot(['FC01.1_R', 'FC01.36'], ['bed level', 'water level', 'pipes'], 1)
        self.assertEqual((4, 6), df.shape)


class Test_HydTables(unittest.TestCase):

    def test_load(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        self.assertEqual(res.sim_id, 'EG14_001')
        self.assertEqual((55, 3), res.cross_sections.df.shape)
        self.assertEqual((52, 13), res.channels.df.shape)
        self.assertEqual(52, len(res.channels.database))
        self.assertEqual(res.cross_sections.df['Name'].loc['XS00001'], '1d_xs_M14_C99')

    def test_load_2(self):  # all cross-sections are in one CSV file
        p = './tests/hyd_tables/EG14_CONCAT_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        self.assertEqual(res.sim_id, 'EG14_CONCAT_001')
        self.assertEqual((55, 3), res.cross_sections.df.shape)
        self.assertEqual((52, 13), res.channels.df.shape)
        self.assertEqual(52, len(res.channels.database))
        self.assertEqual(res.cross_sections.df['Name'].loc['XS00001'], '1d_xs_M14_C99')

    def test_load_3(self):  # HW table mingled in
        p = './tests/hyd_tables/EG14_CONCAT_HW_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        self.assertEqual(res.sim_id, 'EG14_CONCAT_HW_001')
        self.assertEqual((55, 3), res.cross_sections.df.shape)
        self.assertEqual((52, 13), res.channels.df.shape)
        self.assertEqual(52, len(res.channels.database))
        self.assertEqual(res.cross_sections.df['Name'].loc['XS00043'], '1d_xs_M14_C143')
        self.assertEqual(res.cross_sections.df['Type'].loc['XS00043'], 'HW')

    def test_not_hyd_tables(self):
        p = './tests/bc_tables/EG14_001_1d_bc_tables_check.csv'
        try:
            res = HydTables(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_empty_hyd_tables(self):
        p = './tests/hyd_tables/EG14_001_empty_1d_ta_tables_check.csv'
        try:
            res = HydTables(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_channel_count(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        self.assertEqual(52, res.channel_count())

    def test_node_count(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        self.assertEqual(0, res.node_count())

    def test_ids(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        ids = res.ids()
        self.assertEqual(107, len(ids))
        self.assertEqual('1d_xs_M14_C99', ids[0])
        ids = res.ids('Elevation')
        self.assertEqual(55, len(ids))
        self.assertEqual('1d_xs_M14_C99', ids[0])
        ids = res.ids('area')
        self.assertEqual(52, len(ids))
        ids = res.ids('K')
        self.assertEqual(107, len(ids))

    def test_ids_2(self):
        p = './tests/hyd_tables/EG14_CONCAT_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        ids = res.ids()
        self.assertEqual(107, len(ids))
        self.assertEqual('1d_xs_M14_C99', ids[0])

    def test_ids_3(self):
        p = './tests/hyd_tables/EG14_CONCAT_HW_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        ids = res.ids()
        self.assertEqual(107, len(ids))
        self.assertEqual('1d_xs_M14_C99', ids[0])

    def test_result_types(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        rts = res.result_types()
        self.assertEqual(14, len(rts))
        rts = res.result_types('1d_xs_M14_C99')
        self.assertEqual(10, len(rts))
        rts = res.result_types('FC01.39')
        self.assertEqual(8, len(rts))

    def test_time_series(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        df = res.time_series('1d_xs_M14_C99', 'Elevation')
        self.assertEqual((29, 1), df.shape)

    def test_time_series_2(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        df = res.time_series('1d_xs_M14_C99', ['Elevation', 'Width'])
        self.assertEqual((29, 4), df.shape)

    def test_time_series_3(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        df = res.time_series('1d_xs_M14_C99', ['Eff Width', 'Eff Area'])
        self.assertEqual((27, 2), df.shape)

    def test_time_series_4(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        df = res.time_series(['1d_xs_M14_C99', '1d_xs_M14_C100'], ['Eff Width', 'Eff Area'])
        self.assertEqual((30, 8), df.shape)

    def test_time_series_5(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        df = res.time_series('FC01.39', 'area')
        self.assertEqual((35, 1), df.shape)

    def test_time_series_6(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        df = res.time_series(['FC01.39', '1d_xs_M14_C99'], ['area', 'eff area'])
        self.assertEqual((35, 4), df.shape)

    def test_time_series_7(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        df = res.time_series(['FC01.39', '1d_xs_M14_C99'], ['area', 'Eff Width', 'Eff Area', 'Radius'])
        self.assertEqual((35, 10), df.shape)

    def test_time_series_8(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        df = res.time_series(None, ['Eff Width'])
        self.assertEqual((49, 110), df.shape)

    def test_maximum_types(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        result_types = res.maximum_result_types()
        self.assertEqual(0, len(result_types))

    def test_maximums(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        df = res.maximum('1d_xs_M14_C99', 'Elevation')
        self.assertEqual((0, 0), df.shape)

    def test_long_plot(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        try:
            df = res.long_plot('1d_xs_M14_C99', ['Elevation', 'Width'], 1)
            raise Exception('Should have raised a NotImplementedError')
        except NotImplementedError as e:
            pass

    def test_cross_section_ids(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        ids = res.cross_section_ids()
        self.assertEqual(55, len(ids))

    def test_cross_section_ids_2(self):
        p = './tests/hyd_tables/EG14_CONCAT_HW_001_1d_ta_tables_check.csv'
        res = HydTables(p)
        ids = res.cross_section_ids('Elevation')
        self.assertEqual(54, len(ids))


class Test_BC_Tables(unittest.TestCase):

    def test_load_2d_bc_tables(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        self.assertIsNotNone(res.boundary)

    def test_load_1d_bc_tables(self):
        p = './tests/bc_tables/EG14_001_1d_bc_tables_check.csv'
        res = BCTables(p)
        self.assertIsNotNone(res.boundary)

    def test_not_bc_tables(self):
        p = './tests/hyd_tables/EG14_001_1d_ta_tables_check.csv'
        try:
            res = BCTables(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_emtpy_bc_tables(self):
        p = './tests/bc_tables/EG00_001_empty_2d_bc_tables_check.csv'
        try:
            res = BCTables(p)
            raise AssertionError('Should have raised an exception')
        except ValueError:
            pass

    def test_ids(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        ids = res.boundary_ids()
        self.assertEqual(2, len(ids))

    def test_ids_2(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        ids = res.boundary_ids('QT')
        self.assertEqual(1, len(ids))

    def test_ids_3(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        ids = res.ids()
        self.assertEqual(2, len(ids))

    def test_result_types(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        rts = res.result_types()
        self.assertEqual(2, len(rts))

    def test_result_types_2(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        rts = res.result_types('FC01')
        self.assertEqual(1, len(rts))

    def test_time_series(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        df = res.time_series('FC01', 'QT')
        self.assertEqual((41, 1), df.shape)

    def test_time_series_2(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        df = res.time_series(None, ['HQ', 'QT'])
        self.assertEqual((102, 4), df.shape)

    def test_maximums(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        df = res.maximum('FC01', 'HQ')
        self.assertEqual((0, 0), df.shape)

    def test_long_plot(self):
        p = './tests/bc_tables/EG00_001_2d_bc_tables_check.csv'
        res = BCTables(p)
        try:
            df = res.long_plot('FC01', ['HQ'], 1)
            raise Exception('Should have raised a NotImplementedError')
        except NotImplementedError as e:
            pass
