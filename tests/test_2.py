from unittest import TestCase

from pytuflow.results.tpc import TPC


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
        self.assertEqual(56, res.node_count())

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
        self.assertEqual(56, len(res.node_ids()))

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

    def test_time_series(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
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
