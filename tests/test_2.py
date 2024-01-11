from datetime import datetime
from unittest import TestCase

from pytuflow.results.tpc.tpc import TPC
from pytuflow.results.gpkg_ts.gpkg_ts import GPKG_TS
from pytuflow.results.iterator_util import Iterator


class Test_TPC_2016(TestCase):

    def test_load(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual('M04_5m_001', res.sim_id)

    def test_channel_count(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(54, res.channel_count())

    def test_node_count(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(55, res.node_count())

    def test_po_count(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(4, res.po_count())

    def test_rl_count(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, res.rl_count())

    def test_channel_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(54, len(res.channel_ids()))

    def test_node_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(55, len(res.node_ids()))

    def test_po_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(4, len(res.po_ids()))

    def test_rl_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.rl_ids()))

    def test_channel_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.channel_result_types()))

    def test_node_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(2, len(res.node_result_types()))

    def test_po_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(8, len(res.po_result_types()))

    def test_rl_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.rl_result_types()))

    def test_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(9, len(res.result_types()))
        self.assertEqual(3, len(res.result_types('ds1')))
        self.assertEqual(1, len(res.result_types('test')))
        self.assertEqual(3, len(res.result_types('test_2')))

    def test_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.ids('flow')), 55)

    def test_ids2(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.ids()), 113)

    def test_maximums(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.rl.maximums.df
        self.assertEqual((3, 15), df.shape)

    def test_time_series(self):
        p = './2016/M04_5m_001.tpc'
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
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        ts = res.time_series('ds1', 'Q')
        self.assertEqual((181, 1), ts.shape)

    def test_connectivity(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.connectivity(['ds1', 'ds4'])
        self.assertEqual((4, 10), df.shape)

    def test_long_plot_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(5, len(res.long_plot_result_types()))

    def test_long_plot(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.long_plot('ds1', ['bed level', 'water level'], 1)
        self.assertEqual((12, 5), df.shape)


class Test_TPC_2019(TestCase):

    def test_load(self):
        p = './2019/M03_5m_001.tpc'
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
        p = './2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, res.channel_count())

    def test_node_count(self):
        p = './2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(6, res.node_count())

    def test_rl_count(self):
        p = './2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, res.rl_count())

    def test_channel_ids(self):
        p = './2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.channel_ids()))

    def test_node_ids(self):
        p = './2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(6, len(res.node_ids()))

    def test_rl_ids(self):
        p = './2019/M03_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(3, len(res.rl_ids()))

    def test_time_series(self):
        p = './2019/M03_5m_001.tpc'
        res = TPC(p)
        ts = res.time_series('FC01.1_R', 'flow')
        self.assertEqual((91, 1), ts.shape)
        ts = res.time_series('RL region 1', 'vol')
        self.assertEqual((91, 1), ts.shape)

    def test_long_plot(self):
        p = './2020/EG15_001.tpc'
        res = TPC(p)
        df = res.long_plot('pipe1', ['bed elevation', 'water level', 'pipes', 'pits'], 1)
        self.assertEqual((10, 7), df.shape)


class Test_GPKG_TS_2023(TestCase):

    def test_load(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual('M06_5m_003_SWMM', res.sim_id)

    def test_channel_count(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(18, res.channel_count())

    def test_node_count(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(22, res.node_count())

    def test_channel_ids(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(18, len(res.channel_ids()))

    def test_node_ids(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(22, len(res.node_ids()))

    def test_channel_result_types(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(5, len(res.channel_result_types()))

    def test_node_result_types(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(7, len(res.node_result_types()))

    def test_ids(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        self.assertEqual(40, len(res.ids('flow')))

    def test_timesteps(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        ts = res.timesteps()
        self.assertEqual(37, len(ts))

    def test_time_series(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        ts = res.time_series('FC01.1_R', ['q', 'v'])
        self.assertEqual((37, 2), ts.shape)

    def test_connectivity(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.connectivity(['pipe2'])
        self.assertEqual((7, 10), df.shape)

    def test_long_plot(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.long_plot('pipe1', ['bed level', 'water level'], 1)
        self.assertEqual((10, 5), df.shape)

    def test_long_plot2(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.long_plot('pipe1', ['bed level', 'pipes', 'pits'], 1)
        self.assertEqual((10, 6), df.shape)

    def test_long_plot3(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.long_plot('pipe1', ['bed level', 'pipes', 'water level', 'max h'], 1)
        self.assertEqual((10, 8), df.shape)


    def test_long_plot4(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.long_plot('pipe1', ['bed level', 'pipes', 'water level', 'energy'], 1)
        self.assertEqual((10, 6), df.shape)

    def test_maximums(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.nodes.maximums.df
        self.assertEqual((22, 14), df.shape)

    def test_maximums_2(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.maximum('pipe1', 'q')
        self.assertEqual((1, 2), df.shape)

    def test_maximums_3(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.maximum('pipe1', None)
        self.assertEqual((1, 10), df.shape)

    def test_maximums_4(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.maximum(['Pipe1', 'Pipe2', 'pipe3'], None)
        self.assertEqual((3, 10), df.shape)


class Test_Iterator(TestCase):

    def test_get_nodes(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        iter = Iterator(res.channels, res.nodes, res.po, res.rl)
        items = iter.get_nodes(['node20'], ['flow'], 'temporal')
        self.assertEqual(1, len(items))
        self.assertIsNotNone(items[0].id)
        self.assertIsNotNone(items[0].result_type)

    def test_get_nodes_2(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        iter = Iterator(res.channels, res.nodes, res.po, res.rl)
        items = iter.get_nodes([], ['flow'], 'temporal')
        self.assertEqual(22, len(items))

    def test_get_nodes_3(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        iter = Iterator(res.channels, res.nodes, res.po, res.rl)
        items = iter.get_nodes(['node20'], [], 'temporal')
        self.assertEqual(7, len(items))

    def test_id_result_type_gen(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        iter = Iterator(res.channels, res.nodes, res.po, res.rl)
        items = list(iter.ids_result_types_domain(['node20'], ['flow'], None, 'temporal'))
        self.assertEqual(1, len(items))
