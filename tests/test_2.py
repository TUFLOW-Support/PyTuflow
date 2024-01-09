from datetime import datetime
from unittest import TestCase

from pytuflow.results.tpc.tpc import TPC
from pytuflow.results.gpkg_ts.gpkg_ts import GPKG_TS


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

    def test_maximums(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        df = res.rl.maximums.df
        self.assertEqual((3, 15), df.shape)

    def test_time_series(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        ts = res.time_series('test', 'flow')
        self.assertEqual((181, 3), ts.shape)
        ts = res.time_series('ds1', 'flow')
        self.assertEqual((181, 2), ts.shape)
        ts = res.time_series(['ds1', 'ds2'], 'flow')
        self.assertEqual((181, 3), ts.shape)
        ts = res.time_series('ds1', ['flow', 'velocity'])
        self.assertEqual((181, 3), ts.shape)

    def test_time_series_2(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        ts = res.time_series('ds1', 'Q')
        self.assertEqual((181, 2), ts.shape)

    def test_req_id_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        ids, result_types = res._req_id_and_result_type([], ['flow'], None)
        self.assertEqual(55, len(ids))
        ids, result_types = res._req_id_and_result_type([], ['flow'], '1d')
        self.assertEqual(54, len(ids))
        ids, result_types = res._req_id_and_result_type([], ['flow'], '2d')
        self.assertEqual(1, len(ids))
        ids, result_types = res._req_id_and_result_type([], ['flow'], '0d')
        self.assertEqual(1, len(ids))

        ids, result_types = res._req_id_and_result_type(['test'], [], None)
        self.assertEqual(1, len(result_types))
        ids, result_types = res._req_id_and_result_type(['ds1'], [], '1d')
        self.assertEqual(3, len(result_types))
        ids, result_types = res._req_id_and_result_type(['test', 'test_2'], [], '2d')
        self.assertEqual(3, len(result_types))
        ids, result_types = res._req_id_and_result_type(['test_2'], [], '0d')
        self.assertEqual(1, len(result_types))

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
        df = res.nodes.time_series['water level'].df
        df = res.nodes.time_series['energy'].df
        df = res.channels.time_series['flow'].df
        df = res.channels.time_series['velocity'].df
        df = res.channels.time_series['flow area'].df
        df = res.rl.time_series['flow'].df
        df = res.rl.time_series['water level'].df
        df = res.rl.time_series['volume'].df

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
        self.assertEqual((91, 2), ts.shape)
        ts = res.time_series('RL region 1', 'vol')
        self.assertEqual((91, 2), ts.shape)

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
        self.assertEqual(len(res.ids('flow')), 40)

    def test_timesteps(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        ts = res.timesteps()
        self.assertEqual(37, len(ts))

    def test_time_series(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        ts = res.time_series('FC01.1_R', ['q', 'v'])
        self.assertEqual((37, 3), ts.shape)

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

    def test_maximums(self):
        p = './2023/M06_5m_003_SWMM_swmm_ts.gpkg'
        res = GPKG_TS(p)
        df = res.nodes.maximums.df
        self.assertEqual((22, 14), df.shape)
