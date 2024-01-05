from unittest import TestCase

from pytuflow.results.tpc import TPC


class Test_TPC_2016(TestCase):

    def test_load(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(res.sim_id, 'M04_5m_001')

    def test_channel_count(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(res.channel_count(), 54)

    def test_node_count(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(res.node_count(), 56)

    def test_po_count(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(res.po_count(), 4)

    def test_rl_count(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(res.rl_count(), 3)

    def test_channel_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.channel_ids()), 54)

    def test_node_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.node_ids()), 56)

    def test_po_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.po_ids()), 4)

    def test_rl_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.rl_ids()), 3)

    def test_channel_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.channel_result_types()), 3)

    def test_node_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.node_result_types()), 2)

    def test_po_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.po_result_types()), 8)

    def test_rl_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.rl_result_types()), 3)

    def test_result_types(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.result_types()), 9)
        self.assertEqual(len(res.result_types('ds1')), 3)
        self.assertEqual(len(res.result_types('test')), 1)
        self.assertEqual(len(res.result_types('test_2')), 3)

    def test_ids(self):
        p = './2016/M04_5m_001.tpc'
        res = TPC(p)
        self.assertEqual(len(res.ids('flow')), 55)
