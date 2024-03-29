import os, sys

import numpy as np

import pytuflow as tu
if sys.version_info[0] == 3:
    import unittest
else:
    import unittest2 as unittest
from datetime import datetime, timedelta
from pytuflow.helper import roundSeconds


class TestGPKGTS(unittest.TestCase):

    def test_load(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        self.assertFalse(err)

    def test_channel_names(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        ch = res.channels()
        self.assertEqual(36, len(ch))

    def test_node_names(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        nd = res.nodes()
        self.assertEqual(37, len(nd))

    def test_channel_count(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        nchan = res.channelCount()
        self.assertEqual(36, nchan)

    def test_node_count(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        nnode = res.nodeCount()
        self.assertEqual(37, nnode)

    def test_chan_us_node(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        node = res.nodeUpstream('MH-12-11')
        self.assertEqual('MH-12', node)

    def test_chan_ds_node(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        node = res.nodeDownstream('MH-13-12')
        self.assertEqual('MH-12', node)

    def test_chan_us_channels(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        chs = {ch: us_ch for ch, us_ch in zip(res.channels(), res._res.Channels.chan_US_Chan)}
        self.assertEqual(['MH-15-14'], chs['MH-14-12'])
        self.assertEqual(['MH-13-12', 'MH-14-12'], chs['MH-12-11'])

    def test_chan_ds_channels(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        chs = {ch: us_ch for ch, us_ch in zip(res.channels(), res._res.Channels.chan_DS_Chan)}
        self.assertEqual(['MH-11-10'], chs['MH-12-11'])

    def test_chan_lengths(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        lens = res._res.Channels.chan_Length
        self.assertEqual(36, len(lens))

    def test_node_bed(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        z = res._res.nodes.node_bed
        self.assertEqual(37, len(z))
        self.assertFalse(0 in z)

    def test_chan_us_invert(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        z = res._res.Channels.chan_US_Inv
        i = res.channels().index('MH-02-01')
        inv = z[i]
        self.assertTrue(np.isclose(39.66, inv))

    def test_chan_ds_invert(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        z = res._res.Channels.chan_DS_Inv
        i = res.channels().index('MH-02-01')
        inv = z[i]
        self.assertTrue(np.isclose(39.52, inv))

    def test_chan_slope(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        s = res._res.Channels.chan_slope
        i = res.channels().index('MH-02-01')
        slope = s[i]
        self.assertTrue(np.isclose(0.00148, slope, atol=0.0001))

    def test_node_us_channels(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        chs = res.channelsUpstream('MH-17')
        self.assertEqual(['MH-18-17'], chs)
        chs = res.channelsUpstream('MH-08')
        self.assertEqual(['MH-09-08', 'MH-16-08'], chs)

    def test_node_ds_channels(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        chs = res.channelsDownstream('MH-11')
        self.assertEqual(['MH-11-10'], chs)

    def test_chan_result_types(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        res_types = res.channelResultTypes()
        self.assertEqual(5, len(res_types))

    def test_node_result_types(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        res_types = res.nodeResultTypes()
        self.assertEqual(7, len(res_types))

    def test_po_names(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        names = res.poNames()
        self.assertEqual([], names)

    def test_po_result_types(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        names = res.poResultTypes()
        self.assertEqual([], names)

    def test_rl_names(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        names = res.rlNames()
        self.assertEqual([], names)

    def test_rl_result_types(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        names = res.rlResultTypes()
        self.assertEqual([], names)

    def test_rl_point_count(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        count = res.rlPointCount()
        self.assertEqual(0, count)

    def test_rl_line_count(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        count = res.rlLineCount()
        self.assertEqual(0, count)

    def test_rl_region_count(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        count = res.rlRegionCount()
        self.assertEqual(0, count)

    def test_timesteps(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        ts = res.timesteps()
        self.assertEqual(60, len(ts))

    def test_time_series(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        err, msg, (x, y) = res.getTimeSeriesData('MH-10-09', 'Q')
        self.assertFalse(err)
        self.assertEqual(60, len(x))
        self.assertEqual(60, len(y))

    def test_long_profile(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        err, msg, (x, y) = res.getLongProfileData(1., 'H', 'XS100-99')
        self.assertFalse(err)
        self.assertEqual(32, len(x))
        self.assertEqual(32, len(y))
        pipes = res.getPipes()

    def test_units(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2023', 'xp_tut_001_swmm_ts 1.gpkg')
        res = tu.ResData()
        err, out = res.load(tpc)
        units = res.units()
        self.assertEqual('METRIC', units)


class TestImport(unittest.TestCase):
    """Test load() function"""

    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData()
        err, out = res.load(tpc)
        self.assertFalse(err)
        self.assertEqual(out, '')

    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData()
        err, out = res.load(info)
        self.assertFalse(err)
        self.assertEqual(out, '')
        
        
class TestFormat(unittest.TestCase):
    """Test format() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.format()
        self.assertIs(t, '2016')
        
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        f = res.format()
        self.assertIs(f, '2013')
        
        
class TestName(unittest.TestCase):
    """Test name() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.name()
        self.assertEqual(t, 'M04_5m_001')
        
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.name()
        self.assertEqual(t, 'M04_5m_001_1d')
        
        
class TestSource(unittest.TestCase):
    """Test source() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.source()
        self.assertEqual(t, tpc)
        
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.source()
        self.assertEqual(t, info)


class TestChannels(unittest.TestCase):
    """Test channels() function"""

    channels = ['ds1', 'ds2', 'ds3', 'ds4', 'ds5', 'ds_weir', 'FC01.01', 'FC01.02', 'FC01.03', 'FC01.04', 'FC01.05',
                'FC01.06', 'FC01.07', 'FC01.08', 'FC01.09', 'FC01.12', 'FC01.13', 'FC01.14', 'FC01.15', 'FC01.16',
                'FC01.17', 'FC01.18', 'FC01.19', 'FC01.1_R', 'FC01.20', 'FC01.21', 'FC01.22', 'FC01.23', 'FC01.24',
                'FC01.25', 'FC01.26', 'FC01.27', 'FC01.28A', 'FC01.28B', 'FC01.29', 'FC01.2_R', 'FC01.30', 'FC01.31',
                'FC01.32', 'FC01.33', 'FC01.34', 'FC01.36', 'FC01.37', 'FC01.38', 'FC01.39', 'FC01.40', 'FC02.01',
                'FC02.02', 'FC02.03', 'FC02.04', 'FC02.05', 'FC02.06', 'FC04.1_C', 'FC_weir1']
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.channels()
        self.assertEqual(t, self.channels)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.channels()
        self.assertEqual(t, self.channels)


class TestNodes(unittest.TestCase):
    """Test nodes() function"""
    
    nodes = ['ds1.1', 'ds1.2', 'ds2.2', 'ds3.2', 'ds4.2', 'ds5.2', 'ds_weir.2', 'FC01.01.1', 'FC01.02.1', 'FC01.03.1',
             'FC01.04.1', 'FC01.05.1', 'FC01.06.1', 'FC01.07.1', 'FC01.08.1', 'FC01.09.1', 'FC01.12.1', 'FC01.12.2',
             'FC01.13.1', 'FC01.14.1', 'FC01.15.1', 'FC01.16.1', 'FC01.17.1', 'FC01.18.1', 'FC01.19.1', 'FC01.1_R.1',
             'FC01.1_R.2', 'FC01.20.1', 'FC01.21.1', 'FC01.22.1', 'FC01.23.1', 'FC01.24.1', 'FC01.25.1', 'FC01.26.1',
             'FC01.27.1', 'FC01.28A.1', 'FC01.28B.1', 'FC01.29.1', 'FC01.30.1', 'FC01.31.1', 'FC01.32.1', 'FC01.33.1',
             'FC01.36.1', 'FC01.37.1', 'FC01.38.1', 'FC01.39.1', 'FC01.40.1', 'FC02.01.1', 'FC02.02.1', 'FC02.03.1',
             'FC02.04.1', 'FC02.05.1', 'FC02.06.1', 'FC04.1_C.1', 'FC04.1_C.2']
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.nodes()
        self.assertEqual(t, self.nodes)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.nodes()
        self.assertEqual(t, self.nodes)


class TestChannelCount(unittest.TestCase):
    """Test channelCount() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.channelCount()
        self.assertEqual(t, 54)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.channelCount()
        self.assertEqual(t, 54)


class TestNodeCount(unittest.TestCase):
    """Test nodeCount() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.nodeCount()
        self.assertEqual(t, 55)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.nodeCount()
        self.assertEqual(t, 55)


class TestNodeUpstream(unittest.TestCase):
    """Test nodeUpstream() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.nodeUpstream('fc01.14')
        self.assertEqual(t, 'FC01.14.1')
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.nodeUpstream('fc01.14')
        self.assertEqual(t, 'FC01.14.1')


class TestNodeDownstream(unittest.TestCase):
    """Test nodeDownstream() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.nodeDownstream('fC01.1_R')
        self.assertEqual(t, 'FC01.1_R.2')
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.nodeDownstream('fC01.1_R')
        self.assertEqual(t, 'FC01.1_R.2')


class TestChannelConnections(unittest.TestCase):
    """Test channelConnections() function"""
    
    channelConnections = ['FC01.02', 'FC01.01']
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.channelConnections('fc01.01.1')
        self.assertEqual(t, self.channelConnections)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.channelConnections('FC01.01.1')
        self.assertEqual(t, self.channelConnections)


class TestChannelConnectionCount(unittest.TestCase):
    """Test channelConnectionCount() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.channelConnectionCount('Fc01.23.1')
        self.assertEqual(t, 3)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.channelConnectionCount('FC01.23.1')
        self.assertEqual(t, 3)


class TestChannelsUpstream(unittest.TestCase):
    """Test channelsUpstream() function"""
    
    channelsUpstream = ['FC01.33', 'FC_weir1']
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.channelsUpstream('fc01.32.1')
        self.assertEqual(t, self.channelsUpstream)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.channelsUpstream('FC01.32.1')
        self.assertEqual(t, self.channelsUpstream)


class TestChannelsDownstream(unittest.TestCase):
    """Test channelsUpstream() function"""
    
    channelsDownstream = ['FC01.32']
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.channelsDownstream('fc01.32.1')
        self.assertEqual(t, self.channelsDownstream)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.channelsDownstream('FC01.32.1')
        self.assertEqual(t, self.channelsDownstream)


class TestChannelResultTypes(unittest.TestCase):
    """Test channelsUpstream() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.channelResultTypes()
        self.assertEqual(t, ['Q', 'V', 'A'])
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.channelResultTypes()
        self.assertEqual(t, ['Q', 'V'])


class TestNodeResultTypes(unittest.TestCase):
    """Test nodeResultsTypes() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.nodeResultTypes()
        self.assertEqual(t, ['H', 'E'])
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.nodeResultTypes()
        self.assertEqual(t, ['H'])


class TestPONames(unittest.TestCase):
    """Test poNames() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.poNames()
        self.assertEqual(t, ['test', 'test_2', 'test_3', 'test_4'])
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.poNames()
        self.assertEqual(t, [])


class TestPOResultTypes(unittest.TestCase):
    """Test poResultTypes() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.poResultTypes()
        self.assertEqual(t, ['Q', 'QA', 'QI', 'H', 'V', 'QIn', 'QOut', 'Vol'])
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.poResultTypes()
        self.assertEqual(t, [])


class TestRLNames(unittest.TestCase):
    """Test rlNames() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.rlNames()
        self.assertEqual(t, ['test', 'test_2', 'test_3'])
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.rlNames()
        self.assertEqual(t, [])


class TestRLResultTypes(unittest.TestCase):
    """Test rlResultTypes() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.rlResultTypes()
        self.assertEqual(t, ['H', 'Q', 'Vol'])
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.rlResultTypes()
        self.assertEqual(t, [])


class TestRLPointCount(unittest.TestCase):
    """Test rlPointCount() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.rlPointCount()
        self.assertEqual(t, 1)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.rlPointCount()
        self.assertEqual(t, 0)


class TestRLLineCount(unittest.TestCase):
    """Test rlLineCount() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.rlLineCount()
        self.assertEqual(t, 1)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.rlLineCount()
        self.assertEqual(t, 0)


class TestRLRegionCount(unittest.TestCase):
    """Test rlRegionCount() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.rlRegionCount()
        self.assertEqual(t, 1)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.rlRegionCount()
        self.assertEqual(t, 0)


class TestRLCount(unittest.TestCase):
    """Test rlCount() function"""
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.rlCount()
        self.assertEqual(t, 3)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.rlCount()
        self.assertEqual(t, 0)


class TestTimesteps(unittest.TestCase):
    """Test timesteps() function"""
    
    timesteps = [0, 0.016667, 0.033333, 0.05, 0.066667, 0.083333, 0.1, 0.116667, 0.133333, 0.15, 0.166667, 0.183333,
                 0.2, 0.216667, 0.233333, 0.25, 0.266667, 0.283333, 0.3, 0.316667, 0.333333, 0.35, 0.366667, 0.383333,
                 0.4, 0.416667, 0.433333, 0.45, 0.466667, 0.483333, 0.5, 0.516667, 0.533333, 0.55, 0.566667, 0.583333,
                 0.6, 0.616667, 0.633333, 0.65, 0.666667, 0.683333, 0.7, 0.716667, 0.733333, 0.75, 0.766667, 0.783333,
                 0.8, 0.816667, 0.833333, 0.85, 0.866667, 0.883333, 0.9, 0.916667, 0.933333, 0.95, 0.966667, 0.983333,
                 1, 1.016667, 1.033333, 1.05, 1.066667, 1.083333, 1.1, 1.116667, 1.133333, 1.15, 1.166667, 1.183333,
                 1.2, 1.216667, 1.233333, 1.25, 1.266667, 1.283333, 1.3, 1.316667, 1.333333, 1.35, 1.366667, 1.383333,
                 1.4, 1.416667, 1.433333, 1.45, 1.466667, 1.483333, 1.5, 1.516667, 1.533333, 1.55, 1.566667, 1.583333,
                 1.6, 1.616667, 1.633333, 1.65, 1.666667, 1.683333, 1.7, 1.716667, 1.733333, 1.75, 1.766667, 1.783333,
                 1.8, 1.816667, 1.833333, 1.85, 1.866667, 1.883333, 1.9, 1.916667, 1.933333, 1.95, 1.966667, 1.983333,
                 2, 2.016667, 2.033334, 2.05, 2.066667, 2.083333, 2.1, 2.116667, 2.133333, 2.15, 2.166667, 2.183333,
                 2.2, 2.216667, 2.233333, 2.25, 2.266667, 2.283334, 2.3, 2.316667, 2.333333, 2.35, 2.366667, 2.383333,
                 2.4, 2.416667, 2.433333, 2.45, 2.466667, 2.483333, 2.5, 2.516667, 2.533334, 2.55, 2.566667, 2.583333,
                 2.6, 2.616667, 2.633333, 2.65, 2.666667, 2.683333, 2.7, 2.716667, 2.733334, 2.75, 2.766667, 2.783334,
                 2.8, 2.816667, 2.833333, 2.85, 2.866667, 2.883333, 2.9, 2.916667, 2.933333, 2.95, 2.966667, 2.983334,
                 3]
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.timesteps()
        self.assertEqual(t, self.timesteps)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.timesteps()
        self.assertEqual(t, self.timesteps)


class TestTimeSeries(unittest.TestCase):
    """Test getTimeSeriesData() function"""
    
    timesteps = [0, 0.016667, 0.033333, 0.05, 0.066667, 0.083333, 0.1, 0.116667, 0.133333, 0.15, 0.166667, 0.183333,
                 0.2, 0.216667, 0.233333, 0.25, 0.266667, 0.283333, 0.3, 0.316667, 0.333333, 0.35, 0.366667, 0.383333,
                 0.4, 0.416667, 0.433333, 0.45, 0.466667, 0.483333, 0.5, 0.516667, 0.533333, 0.55, 0.566667, 0.583333,
                 0.6, 0.616667, 0.633333, 0.65, 0.666667, 0.683333, 0.7, 0.716667, 0.733333, 0.75, 0.766667, 0.783333,
                 0.8, 0.816667, 0.833333, 0.85, 0.866667, 0.883333, 0.9, 0.916667, 0.933333, 0.95, 0.966667, 0.983333,
                 1, 1.016667, 1.033333, 1.05, 1.066667, 1.083333, 1.1, 1.116667, 1.133333, 1.15, 1.166667, 1.183333,
                 1.2, 1.216667, 1.233333, 1.25, 1.266667, 1.283333, 1.3, 1.316667, 1.333333, 1.35, 1.366667, 1.383333,
                 1.4, 1.416667, 1.433333, 1.45, 1.466667, 1.483333, 1.5, 1.516667, 1.533333, 1.55, 1.566667, 1.583333,
                 1.6, 1.616667, 1.633333, 1.65, 1.666667, 1.683333, 1.7, 1.716667, 1.733333, 1.75, 1.766667, 1.783333,
                 1.8, 1.816667, 1.833333, 1.85, 1.866667, 1.883333, 1.9, 1.916667, 1.933333, 1.95, 1.966667, 1.983333,
                 2, 2.016667, 2.033334, 2.05, 2.066667, 2.083333, 2.1, 2.116667, 2.133333, 2.15, 2.166667, 2.183333,
                 2.2, 2.216667, 2.233333, 2.25, 2.266667, 2.283334, 2.3, 2.316667, 2.333333, 2.35, 2.366667, 2.383333,
                 2.4, 2.416667, 2.433333, 2.45, 2.466667, 2.483333, 2.5, 2.516667, 2.533334, 2.55, 2.566667, 2.583333,
                 2.6, 2.616667, 2.633333, 2.65, 2.666667, 2.683333, 2.7, 2.716667, 2.733334, 2.75, 2.766667, 2.783334,
                 2.8, 2.816667, 2.833333, 2.85, 2.866667, 2.883333, 2.9, 2.916667, 2.933333, 2.95, 2.966667, 2.983334,
                 3]
    
    flow_1d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.02, 0.48, 2.108, 4.141, 5.507, 6.741, 8.01, 9.425, 11.511,
               13.946, 16.682, 19.655, 22.854, 26.526, 30.268, 33.526, 36.427, 39.065, 41.678, 44.228, 46.865, 49.726,
               52.587, 55.238, 57.547, 59.392, 60.818, 61.934, 62.817, 63.537, 64.144, 64.665, 65.111, 65.506, 65.862,
               66.183, 66.481, 66.93, 67.413, 67.873, 68.363, 68.863, 69.355, 69.828, 70.25, 70.648, 71.062, 71.385,
               71.624, 71.793, 71.891, 71.924, 71.894, 71.803, 71.655, 71.455, 71.21, 70.931, 70.626, 70.301, 69.959,
               69.603, 69.243, 68.884, 68.531, 68.193, 67.874, 67.576, 67.296, 67.031, 66.79, 66.557, 66.364, 66.137,
               65.898, 65.625, 65.413, 65.184, 64.93, 64.653, 64.347, 64.007, 63.638, 63.223, 62.762, 62.248, 61.675,
               61.039, 60.327, 59.521, 58.605, 57.561, 56.374, 55.012, 53.436, 51.563, 49.349, 46.829, 44.058, 41.153,
               38.193, 35.405, 32.907, 30.743, 28.915, 27.335, 26.01, 24.86, 23.845, 22.949, 22.158, 21.427, 20.765,
               20.145, 19.571, 19.042, 18.538, 18.063, 17.623, 17.19, 16.761, 16.349, 15.962, 15.6, 15.241, 14.886,
               14.532, 14.18, 13.829, 13.481, 13.141, 12.803, 12.465, 12.145, 11.829, 11.513, 11.215, 10.9, 10.599,
               10.307, 10.047, 9.8, 9.575, 9.361, 9.139, 8.866, 8.599, 8.324, 8.04, 7.77, 7.507, 7.246]
    
    velocity_1d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.16, 0.505, 0.881, 1.086, 1.169, 1.215, 1.24, 1.256,
                   1.299, 1.316, 1.302, 1.277, 1.255, 1.242, 1.231, 1.217, 1.206, 1.199, 1.199, 1.203, 1.213, 1.227,
                   1.243, 1.255, 1.264, 1.269, 1.27, 1.27, 1.269, 1.268, 1.268, 1.268, 1.267, 1.267, 1.267, 1.267,
                   1.267, 1.27, 1.273, 1.275, 1.278, 1.281, 1.284, 1.286, 1.288, 1.29, 1.292, 1.293, 1.294, 1.294,
                   1.293, 1.293, 1.291, 1.29, 1.288, 1.286, 1.284, 1.281, 1.279, 1.277, 1.274, 1.272, 1.269, 1.267,
                   1.265, 1.263, 1.261, 1.26, 1.258, 1.257, 1.256, 1.255, 1.254, 1.253, 1.252, 1.25, 1.249, 1.248,
                   1.246, 1.245, 1.243, 1.241, 1.238, 1.236, 1.233, 1.229, 1.226, 1.222, 1.217, 1.211, 1.205, 1.198,
                   1.189, 1.179, 1.167, 1.151, 1.131, 1.108, 1.082, 1.055, 1.027, 1.002, 0.981, 0.965, 0.954, 0.946,
                   0.942, 0.939, 0.938, 0.937, 0.937, 0.937, 0.938, 0.939, 0.94, 0.94, 0.941, 0.942, 0.943, 0.943,
                   0.943, 0.943, 0.943, 0.944, 0.944, 0.945, 0.945, 0.944, 0.944, 0.944, 0.944, 0.943, 0.942, 0.943,
                   0.943, 0.944, 0.945, 0.945, 0.945, 0.944, 0.943, 0.942, 0.942, 0.942, 0.941, 0.936, 0.932, 0.927,
                   0.919, 0.913, 0.906, 0.9]
    water_level_1d = [31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259,
                      31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259,
                      31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259,
                      31.259, 31.2608, 31.2648, 31.2892, 31.3598, 31.5006, 31.6962, 32.0221, 32.5113, 32.8862, 33.0757,
                      33.192, 33.2797, 33.3544, 33.4313, 33.5139, 33.5958, 33.6711, 33.7355, 33.7918, 33.8419, 33.8869,
                      33.9273, 33.963, 33.9942, 34.0227, 34.0502, 34.0776, 34.1046, 34.1302, 34.1538, 34.1751, 34.1939,
                      34.2103, 34.2248, 34.2376, 34.2491, 34.2597, 34.2696, 34.2792, 34.2887, 34.298, 34.3071, 34.3163,
                      34.3253, 34.3338, 34.3418, 34.349, 34.3551, 34.3597, 34.363, 34.3651, 34.3665, 34.3671, 34.3672,
                      34.3666, 34.3652, 34.3623, 34.3581, 34.3528, 34.3468, 34.3404, 34.3336, 34.3269, 34.3202, 34.3137,
                      34.3073, 34.3012, 34.2953, 34.2898, 34.2845, 34.2796, 34.2749, 34.2703, 34.2657, 34.2611, 34.2565,
                      34.2516, 34.2465, 34.2409, 34.235, 34.2284, 34.2213, 34.2135, 34.2049, 34.1954, 34.185, 34.1735,
                      34.1608, 34.1468, 34.1313, 34.1141, 34.0951, 34.0739, 34.0499, 34.0221, 33.9902, 33.9548, 33.9167,
                      33.8773, 33.8377, 33.7988, 33.7612, 33.7253, 33.6902, 33.6562, 33.6244, 33.595, 33.5684, 33.5443,
                      33.5227, 33.5032, 33.4856, 33.4696, 33.4548, 33.4411, 33.4283, 33.4163, 33.405, 33.3945, 33.3846,
                      33.3753, 33.3663, 33.3578, 33.3498, 33.3413, 33.3327, 33.3249, 33.318, 33.3119, 33.3058, 33.2981,
                      33.2886, 33.2778, 33.2664, 33.2548, 33.2434, 33.2327, 33.2227, 33.2134, 33.2045, 33.1961, 33.1879,
                      33.18, 33.172]
    energy_1d = [0.0, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259,
                 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259,
                 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.259, 31.2608,
                 31.2654, 31.2919, 31.3676, 31.5177, 31.7278, 32.0723, 32.574, 32.9427, 33.1312, 33.2499, 33.3418,
                 33.4151, 33.4939, 33.5788, 33.6627, 33.739, 33.804, 33.8609, 33.9118, 33.9576, 33.9986, 34.0348,
                 34.0665, 34.0957, 34.124, 34.1523, 34.1799, 34.2062, 34.2303, 34.2519, 34.271, 34.2877, 34.3023,
                 34.3154, 34.3271, 34.3379, 34.3481, 34.358, 34.3677, 34.3773, 34.3868, 34.3962, 34.4054, 34.4142,
                 34.4224, 34.4297, 34.4358, 34.4404, 34.4436, 34.4457, 34.4469, 34.4475, 34.4475, 34.4469, 34.4452,
                 34.4421, 34.4376, 34.432, 34.4257, 34.419, 34.4121, 34.4052, 34.3982, 34.3916, 34.385, 34.3787,
                 34.3726, 34.367, 34.3616, 34.3565, 34.3517, 34.347, 34.3423, 34.3375, 34.3327, 34.3276, 34.3223,
                 34.3165, 34.3103, 34.3035, 34.2961, 34.2879, 34.2789, 34.2691, 34.2582, 34.2462, 34.2329, 34.2183,
                 34.2021, 34.1841, 34.1642, 34.1421, 34.1168, 34.0876, 34.0543, 34.0173, 33.9778, 33.9371, 33.8964,
                 33.8565, 33.8181, 33.7814, 33.7452, 33.7104, 33.6779, 33.648, 33.6209, 33.5965, 33.5746, 33.5549,
                 33.5371, 33.5209, 33.506, 33.4922, 33.4793, 33.4672, 33.456, 33.4455, 33.4357, 33.4265, 33.4176,
                 33.4094, 33.4016, 33.3922, 33.3829, 33.3746, 33.3673, 33.3607, 33.3539, 33.3451, 33.3344, 33.3225,
                 33.3099, 33.2973, 33.2851, 33.2735, 33.2627, 33.2527, 33.2432, 33.2341, 33.2252, 33.2166, 33.208]
    
    area_1d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.122, 0.949, 2.393, 3.812, 4.711, 5.548, 6.461, 7.505, 8.862,
               10.594, 12.808, 15.389, 18.205, 21.366, 24.591, 27.55, 30.214, 32.589, 34.758, 36.751, 38.652, 40.51,
               42.317, 44.008, 45.521, 46.82, 47.9, 48.785, 49.508, 50.101, 50.595, 51.011, 51.373, 51.69, 51.973,
               52.224, 52.451, 52.698, 52.962, 53.225, 53.492, 53.764, 54.036, 54.3, 54.546, 54.776, 55.001, 55.2,
               55.363, 55.492, 55.585, 55.643, 55.669, 55.663, 55.626, 55.559, 55.468, 55.353, 55.22, 55.072, 54.911,
               54.738, 54.558, 54.373, 54.186, 54.001, 53.82, 53.646, 53.479, 53.321, 53.173, 53.031, 52.906, 52.776,
               52.641, 52.499, 52.369, 52.235, 52.093, 51.94, 51.773, 51.589, 51.387, 51.161, 50.911, 50.63, 50.316,
               49.967, 49.575, 49.132, 48.629, 48.058, 47.406, 46.661, 45.802, 44.795, 43.615, 42.248, 40.702, 39.012,
               37.194, 35.34, 33.542, 31.85, 30.302, 28.89, 27.619, 26.467, 25.428, 24.488, 23.641, 22.864, 22.135,
               21.459, 20.831, 20.247, 19.695, 19.174, 18.687, 18.221, 17.772, 17.338, 16.922, 16.525, 16.139, 15.76,
               15.385, 15.013, 14.646, 14.281, 13.928, 13.578, 13.229, 12.886, 12.542, 12.2, 11.869, 11.536, 11.211,
               10.921, 10.653, 10.398, 10.162, 9.937, 9.714, 9.469, 9.225, 8.982, 8.745, 8.514, 8.284, 8.053]
    
    flow_in_2d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0422, 0.2026,
                  0.3737, 0.5515, 0.6533, 0.7693, 0.883, 0.9729, 1.0642, 1.9938, 4.6202, 7.0295, 8.5476, 9.8946,
                  10.8878, 11.6146, 12.1343, 12.4323, 12.7083, 12.8781, 13.0135, 13.1136, 13.1495, 13.148, 13.1249,
                  13.0896, 13.004, 12.8404, 12.6235, 12.4109, 12.1608, 11.7929, 11.2903, 10.7216, 10.1205, 9.562,
                  9.0137, 8.397, 7.7487, 7.0782, 6.3728, 5.7095, 5.088, 4.4643, 3.891, 3.3525, 2.8851, 2.4744, 2.1686,
                  1.8782, 1.6486, 1.5028, 1.3798, 1.2852, 1.2073, 1.1462, 1.1056, 1.0728, 1.0432, 1.0116, 0.9768,
                  0.9408, 0.9002, 0.8584, 0.8218, 0.7648, 0.6956, 0.6344, 0.5712, 0.4912, 0.421, 0.3012, 0.1896,
                  0.1124, 0.0331, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                  0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    flow_out_2d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0028, 0.17,
                   0.4584, 0.6988, 0.9404, 1.1755, 1.3897, 1.5973, 1.8027, 2.3664, 3.8479, 5.5689, 7.4962, 9.1501,
                   10.3612, 11.1758, 11.7833, 12.195, 12.4759, 12.6835, 12.8235, 12.9308, 13.0012, 13.0257, 13.0251,
                   13.0061, 12.9725, 12.8894, 12.7575, 12.5992, 12.4164, 12.2065, 11.8947, 11.5025, 11.0586, 10.5532,
                   10.0977, 9.6485, 9.1596, 8.6, 8.0425, 7.5252, 7.007, 6.5016, 5.989, 5.4839, 4.9831, 4.5285, 4.1055,
                   3.7274, 3.3529, 3.0331, 2.745, 2.498, 2.2868, 2.1146, 2.0024, 1.9167, 1.8417, 1.7672, 1.6905, 1.6085,
                   1.5212, 1.4273, 1.3321, 1.2214, 1.1148, 1.0025, 0.8789, 0.7385, 0.5875, 0.4407, 0.2749, 0.1162,
                   0.0447, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    vol_2d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
              0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.6702, 4.8866, 11.7475,
              17.6475, 23.4239, 28.6196, 33.6471, 38.857, 46.8055, 85.0348, 253.4762, 524.6104, 759.8281, 913.3241,
              1013.9515, 1079.2936, 1121.9258, 1148.87, 1169.4951, 1184.2415, 1194.097, 1201.4274, 1205.6873,
              1207.0391, 1206.5654, 1205.0145, 1201.8533, 1194.7375, 1184.095, 1171.442, 1157.6392, 1139.443,
              1113.2889, 1080.9148, 1043.5312, 999.7416, 958.5553, 914.8566, 866.2934, 811.439, 754.5608, 697.1193,
              640.0192, 580.587, 519.6379, 459.4251, 400.0298, 342.7039, 292.0954, 244.7868, 200.792, 164.4885,
              134.2065, 108.708, 89.7758, 76.1221, 66.8908, 60.0832, 54.9673, 50.8729, 46.349, 42.3624, 38.7486,
              35.5412, 33.0132, 30.3239, 27.4455, 24.4216, 21.2961, 17.7855, 14.5599, 10.6828, 6.3178, 3.3362, 1.063,
              0.1254, 0.0669, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
              0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
              0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
              0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    flow_2d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.1133, 0.4083, 0.7821, 1.2223, 1.7044, 2.2546, 2.8691, 3.5573, 4.2593, 4.9052, 5.5018,
               5.9984, 6.4206, 6.7679, 7.0516, 7.294, 7.5013, 7.6797, 7.8376, 7.9757, 8.1028, 8.2187, 7.2423, 6.5192,
               6.2125, 6.0402, 5.9454, 5.8998, 5.8976, 5.9185, 5.9489, 6.0088, 6.0798, 6.1489, 6.2068, 6.251, 6.2791,
               6.2872, 6.2785, 6.2537, 6.2146, 6.1684, 6.1187, 6.0694, 6.0239, 5.9873, 5.9621, 5.9515, 5.961, 5.9947,
               6.0546, 6.1373, 6.2397, 6.3714, 6.5227, 6.6751, 6.8232, 6.7899, 6.9364, 7.2427, 8.0388, 8.0745, 8.0081,
               7.9292, 7.8438, 7.7502, 7.6481, 7.5357, 7.4125, 7.2763, 7.1228, 6.953, 6.7674, 6.5591, 6.3248, 6.0648,
               5.772, 5.4438, 5.0725, 4.6438, 4.1548, 3.5868, 2.9373, 2.2644, 1.6126, 1.1071, 0.7407, 0.4345, 0.2136,
               0.0845, 0.0332, -0.0022, -0.01, -0.0106, -0.0085, -0.0066, -0.0055, -0.0046, -0.0038, -0.0031, -0.0028,
               -0.0026, -0.0023, -0.0021, -0.0019, -0.0016, -0.0013, -0.0011, -0.0011, -0.001, -0.0009, -0.0008,
               -0.0007, -0.0005, -0.0001, -0.0001, -0.0002, -0.0002, -0.0001, -0.0002, -0.0002, -0.0001, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    flow_area_2d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1602, 1.6877,
                    4.2241, 6.4173, 10.8509, 19.8646, 26.1365, 30.8521, 34.5092, 37.6827, 40.4906, 43.6383, 48.45,
                    54.4501, 60.1568, 65.1684, 69.2016, 72.1126, 74.4858, 76.3576, 78.0566, 79.8359, 81.8077, 84.0132,
                    86.4928, 89.2197, 92.2176, 95.4688, 98.9965, 102.7752, 106.9712, 111.3956, 115.9304, 120.3243,
                    124.5813, 128.5191, 132.0605, 135.1796, 137.9167, 140.2098, 142.0283, 143.4654, 144.4348, 144.9846,
                    145.1137, 144.8608, 144.2132, 143.2238, 141.8696, 140.2606, 138.4282, 136.3352, 134.0054, 131.4265,
                    128.7137, 125.8122, 122.6954, 119.5636, 116.3429, 113.084, 109.8028, 106.441, 103.1632, 99.8015,
                    96.4779, 93.0457, 89.5221, 86.04, 82.4096, 78.7177, 75.076, 71.331, 67.6234, 63.8167, 59.9716,
                    56.0815, 52.2729, 48.5229, 45.0767, 41.7623, 38.5948, 35.6678, 32.8741, 30.2464, 27.7888, 25.6017,
                    23.6467, 21.871, 20.234, 18.7163, 17.3769, 16.0258, 14.7224, 13.547, 12.5449, 11.5598, 10.703,
                    9.8776, 9.1476, 8.473, 7.7789, 7.1712, 6.6482, 6.1615, 5.67, 5.2736, 4.9439, 4.6168, 4.2767,
                    3.9647, 3.6669, 3.3667, 3.0654, 2.7858, 2.5354, 2.2942, 1.9206, 1.733, 1.4099, 1.1345, 0.7125,
                    0.721, 0.3964, 0.2657, 0.2645, 0.2639, 0.1546, 0.1533, 0.08, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    flow_integral_2d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4433,
                        16.8507, 81.9596, 222.9706, 483.9339, 986.8833, 1772.3037, 2769.8579, 3946.4663, 5284.0215,
                        6771.8193, 8435.0459, 10355.7373, 12626.7363, 15275.5391, 18272.4688, 21558.8027, 25057.6289,
                        28713.2441, 32487.3516, 36347.9531, 40277.1484, 44266.3164, 48309.3906, 52401.2188, 56537.5078,
                        60713.2695, 64923.8516, 69165.375, 73432.5234, 77719.8047, 82021.4766, 86333.3281, 90649.7812,
                        94961.2109, 99256.1016, 103522.2422, 107753.0547, 111946.25, 116098.0781, 120201.7422,
                        124249.4141, 128235.3672, 132156, 136008.0625, 139787.7969, 143489.9844, 147109.75, 150646.0156,
                        154099.3594, 157470.8906, 160761.2656, 163969.75, 167095.8281, 170140.7344, 173107.25,
                        175997.5156, 178816.4375, 181573.5312, 184276.9062, 186928.9219, 189529.8125, 192080.7188,
                        194581.0625, 197029.0625, 199422.6719, 201758.75, 204033.6562, 206242.8594, 208382.4375,
                        210448.8438, 212435.0938, 214331.2656, 216129.7344, 217824.2656, 219408.5312, 220881.7344,
                        222244.7188, 223505.4219, 224673, 225751.0781, 226746.7344, 227665.1562, 228511.2188,
                        229289.2344, 230002.7188, 230657.1406, 231258.1562, 231811.5156, 232320.8594, 232788.7031,
                        233217.4531, 233608.1719, 233962.5781, 234283.1875, 234572.9844, 234835.0469, 235071.8594,
                        235284.7031, 235475.2344, 235645.3281, 235796.5312, 235930.7812, 236049.6875, 236154.7188,
                        236247.5938, 236329.4062, 236400.4688, 236463.0312, 236518.5156, 236566.5938, 236607.1562,
                        236640.3594, 236667.6562, 236690.25, 236708.4688, 236722.7656, 236733.6094, 236741.3906,
                        236746.5312, 236749.5469, 236751.1406, 236751.875, 236752.1094, 236752.1719, 236752.2344,
                        236752.2812, 236752.3125, 236752.3281, 236752.3438, 236752.3438, 236752.3438, 236752.3438,
                        236752.3438, 236752.3438, 236752.3438, 236752.3438, 236752.3438, 236752.3438, 236752.3438,
                        236752.3438, 236752.3438, 236752.3438, 236752.3438, 236752.3438]
    
    water_level_2d = [41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155,
                      41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155,
                      41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155,
                      41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155,
                      41.6155, 41.6488, 41.7699, 41.859, 41.9273, 41.9833, 42.0304, 42.0765, 42.1335, 42.1986,
                      42.2599, 42.3136, 42.3567, 42.389, 42.4159, 42.4391, 42.4613, 42.4849, 42.5112, 42.5396,
                      42.5698, 42.6016, 42.6341, 42.6668, 42.6992, 42.7308, 42.7617, 42.7914, 42.8197, 42.8459,
                      42.8699, 42.8919, 42.911, 42.9278, 42.9421, 42.9539, 42.9633, 42.9704, 42.9752, 42.9778,
                      42.9783, 42.9769, 42.9735, 42.9684, 42.9616, 42.9532, 42.9435, 42.9323, 42.92, 42.9064,
                      42.8916, 42.8757, 42.8589, 42.8414, 42.8235, 42.8051, 42.786, 42.7667, 42.7467, 42.7263,
                      42.705, 42.6829, 42.6598, 42.6357, 42.6105, 42.584, 42.5562, 42.5265, 42.4947, 42.461,
                      42.4247, 42.3854, 42.3437, 42.2996, 42.2546, 42.2082, 42.1614, 42.1137, 42.0664, 42.0191,
                      41.973, 41.9292, 41.8862, 41.8452, 41.8075, 41.7714, 41.7336, 41.6996, 41.6662, 41.6342,
                      41.6206, 41.6184, 41.6176, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155,
                      41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155,
                      41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155,
                      41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155,
                      41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155, 41.6155,
                      41.6155]
    
    velocity_2d = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   0.0, 0.1013, 0.2366, 0.3075, 0.3705, 0.4192, 0.4608, 0.512, 0.5725, 0.6392, 0.697, 0.744, 0.7768,
                   0.7977, 0.8132, 0.8205, 0.8221, 0.82, 0.8142, 0.8054, 0.7945, 0.7815, 0.7671, 0.7521, 0.7376, 0.723,
                   0.7084, 0.6947, 0.6818, 0.669, 0.6563, 0.643, 0.63, 0.6177, 0.6066, 0.596, 0.5853, 0.5749, 0.565,
                   0.5556, 0.5466, 0.538, 0.5292, 0.5208, 0.513, 0.5058, 0.4993, 0.4931, 0.4871, 0.4816, 0.4766,
                   0.4724, 0.4686, 0.4663, 0.4656, 0.4659, 0.4657, 0.466, 0.4662, 0.4664, 0.467, 0.467, 0.4667,
                   0.4663, 0.465, 0.4636, 0.4611, 0.4573, 0.4511, 0.4449, 0.4378, 0.4282, 0.4182, 0.4069, 0.3985,
                   0.3888, 0.3757, 0.3604, 0.3436, 0.3242, 0.3008, 0.277, 0.2541, 0.2245, 0.1974, 0.1732, 0.143,
                   0.1099, 0.0805, 0.0359, 0.0133, 0.0092, 0.0074, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                   0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    
    vol_rl = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.008, 0.014,
              0.192, 64.346, 195.219, 366.543, 567.91, 711.544, 823.229, 921.673, 1016.449, 1119.8, 1234.529,
              1359.897, 1494.424, 1636.818, 1794.781, 1988.195, 2239.146, 2563.606, 2987.81, 3722.823, 4559.457,
              5116.306, 5541.091, 5895.566, 6207.726, 6495.356, 6753.795, 7066.854, 7537.658, 8083.01, 8612.551,
              9052.729, 9394.24, 9641.777, 9827.516, 9964.758, 10071.729, 10162.044, 10244.312, 10327.764, 10412.729,
              10500.328, 10591.721, 10686.754, 10784.619, 10882.23, 10977.864, 11070.181, 11162.879, 11249.209,
              11322.495, 11381.808, 11425.254, 11452.476, 11472.361, 11481.458, 11474.794, 11450.347, 11412.622,
              11362.619, 11301.144, 11228.734, 11141.016, 11041.25, 10932.813, 10816.768, 10694.796, 10568.17,
              10433.705, 10294.755, 10152.802, 10009.785, 9867.815, 9732.715, 9609.904, 9494.931, 9382.785,
              9270.326, 9157.287, 9041.501, 8922.485, 8798.721, 8669.05, 8534.966, 8393.936, 8245.066, 8085.166,
              7911.634, 7720.957, 7506.877, 7268.518, 7007.838, 6733.036, 6460.076, 6203.475, 5963.532, 5737.567,
              5514.806, 5308.035, 5118.324, 4941.185, 4775.743, 4624.963, 4488.735, 4364.541, 4249.962, 4143.172,
              4042.481, 3945.468, 3851.388, 3759.923, 3673.243, 3592.553, 3515.419, 3438.057, 3364.712, 3293.661,
              3224.188, 3156.879, 3092.05, 3031.226, 2974.97, 2921.937, 2872.085, 2823.805, 2776.917, 2734.423,
              2688.854, 2645.207, 2603.934, 2564.402, 2526.046, 2488.953, 2452.57, 2415.73, 2378.625, 2340.891,
              2302.961, 2264.488, 2225.415, 2186.046, 2146.654, 2106.866, 2067.766, 2029.807, 1992.473, 1955.792,
              1919.844, 1884.784, 1850.099, 1815.901, 1781.544, 1746.664, 1710.922, 1674.024, 1635.635, 1595.791,
              1556.018, 1515.647, 1474.96, 1434.167, 1393.378]
    
    flow_rl = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 0.179, 1.329, 2.563, 3.568, 4.508, 5.494, 6.524, 7.649, 8.949, 10.584,
               12.831, 15.58, 18.606, 21.555, 25.114, 29.716, 34.265, 38.564, 42.658, 46.697, 50.6, 54.848, 60.425,
               67.792, 76.099, 84.292, 91.362, 96.603, 100.519, 103.094, 104.482, 104.972, 104.985, 104.416, 103.93,
               103.291, 102.83, 102.274, 101.897, 101.282, 100.833, 100.431, 100.19, 99.893, 99.502, 99.014, 98.399,
               97.855, 97.238, 96.575, 95.881, 95.034, 94.125, 93.161, 92.119, 91.042, 89.823, 88.54, 87.248, 85.949,
               84.67, 83.404, 82.092, 80.816, 79.554, 78.359, 77.218, 76.202, 75.345, 74.606, 73.94, 73.233, 72.616,
               71.94, 71.284, 70.666, 69.861, 69.075, 68.252, 67.221, 66.175, 64.931, 63.536, 61.978, 60.235, 58.261,
               56.176, 53.975, 51.843, 49.82, 47.791, 45.76, 43.723, 41.657, 39.737, 37.932, 36.284, 34.734, 33.381,
               32.235, 31.219, 30.286, 29.265, 28.271, 27.297, 26.378, 25.542, 24.768, 23.993, 23.238, 22.538, 21.858,
               21.229, 20.613, 20.044, 19.506, 19.008, 18.531, 18.069, 17.629, 17.229, 16.811, 16.407, 16.011, 15.639,
               15.276, 14.927, 14.589, 14.248, 13.904, 13.565, 13.225, 12.884, 12.543, 12.209, 11.884, 11.563, 11.253,
               10.958, 10.665, 10.378, 10.098, 9.83, 9.571, 9.321, 9.073, 8.827, 8.58, 8.318, 8.05, 7.778, 7.507,
               7.238, 6.971, 6.708]
    
    water_level_rl = [None, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5,
                      36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5, 36.5]
    
    def test_tpc_flow_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('FC01.09', 'Q')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.flow_1d))
    
    def test_info_flow_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('FC01.09', 'Q')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.flow_1d))

    def test_tpc_velocity_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('FC01.09', 'V')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.velocity_1d))

    def test_info_velocity_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('FC01.09', 'V')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.velocity_1d))
        
    def test_tpc_water_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('ds5.2', 'H')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.water_level_1d))

    def test_info_water_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('ds5.2', 'H')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.water_level_1d))
        
    def test_tpc_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('ds5.2', 'E')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.energy_1d))

    def test_info_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('ds5.2', 'E')
        self.assertTrue(err)
        self.assertEqual(out, 'Warning - Expecting unexpected data type for 1D: E')
        self.assertEqual(data, ([], []))
        
    def test_tpc_area_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('FC01.09', 'A')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.area_1d))

    def test_info_area_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('FC01.09', 'A')
        self.assertTrue(err)
        self.assertEqual(out, 'Warning - Expecting unexpected data type for 1D: A')
        self.assertEqual(data, ([], []))
        
    def test_tpc_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test_4', 'Qin')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.flow_in_2d))

    def test_info_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test_4', 'Qin')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test_4', 'Qout')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.flow_out_2d))

    def test_info_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test_4', 'Qout')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_vol_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test_4', 'vol')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.vol_2d))

    def test_info_vol_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test_4', 'vol')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_flow_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test', 'Q')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.flow_2d))

    def test_info_flow_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test_2', 'QA')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.flow_area_2d))

    def test_info_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test_2', 'QA')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test_2', 'QI')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.flow_integral_2d))

    def test_info_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test_2', 'QI')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_water_level_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test_3', 'H')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.water_level_2d))

    def test_info_water_level_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test_3', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_velocity_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test_3', 'V')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.velocity_2d))

    def test_info_velocity_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test_3', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_vol_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test_2', 'Vol', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.vol_rl))

    def test_info_vol_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test_2', 'Vol', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_flow_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test', 'Q', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.flow_rl))

    def test_info_flow_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test', 'Q', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        
    def test_tpc_water_level_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, data = res.getTimeSeriesData('test_3', 'H', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(data, (self.timesteps, self.water_level_rl))

    def test_info_water_level_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, data = res.getTimeSeriesData('test_3', 'H', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'PO and RL outputs not supported in 2013 format')
        self.assertEqual(data, ([], []))
        

class TestMaximums(unittest.TestCase):
    """Test maximum() function"""

    def test_tpc_flow_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('FC01.09', 'Q')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 71.924)

    def test_info_flow_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('FC01.09', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_velocity_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('FC01.09', 'V')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 1.3203)

    def test_info_velocity_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('FC01.09', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('ds5.2', 'H')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 34.3672)

    def test_info_water_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('ds5.2', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('ds5.2', 'E')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 34.4476)

    def test_info_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('ds5.2', 'E')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_area_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('FC01.09', 'A')
        self.assertTrue(err)
        self.assertEqual(out, 'Result type not recognised or unavailable as max type')
        self.assertEqual(m, 0)

    def test_info_area_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('FC01.09', 'A')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test_4', 'Qin')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test_4', 'Qin')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test_4', 'Qout')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test_4', 'Qout')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_vol_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test_4', 'vol')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for PO')
        self.assertEqual(m, 0)

    def test_info_vol_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test_4', 'vol')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test_2', 'QA')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test_2', 'QA')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test_2', 'QI')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test_2', 'QI')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test_3', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for PO')
        self.assertEqual(m, 0)

    def test_info_water_level_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test_3', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_velocity_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test_3', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for PO')
        self.assertEqual(m, 0)

    def test_info_velocity_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test_3', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_vol_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test_2', 'Vol', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 11481.68)

    def test_info_vol_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test_2', 'Vol', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test', 'Q', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 105.042)

    def test_info_flow_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test', 'Q', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximum('test_3', 'H', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 36.5)

    def test_info_water_level_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximum('test_3', 'H', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximums not supported for 2013 format')
        self.assertEqual(m, 0)
        
        
class TestTimeOfMaximum(unittest.TestCase):
    """Test timeOfMaximum() function"""

    def test_tpc_flow_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('FC01.09', 'Q')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 1.3321)

    def test_info_flow_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('FC01.09', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_velocity_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('FC01.09', 'V')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 0.639)

    def test_info_velocity_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('FC01.09', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('ds5.2', 'H')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 1.4977)

    def test_info_water_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('ds5.2', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('ds5.2', 'E')
        self.assertTrue(err)
        self.assertEqual(out, 'Result type not recognised or unavailable for time of maximum')
        self.assertEqual(m, 0)

    def test_info_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('ds5.2', 'E')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_area_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('FC01.09', 'A')
        self.assertTrue(err)
        self.assertEqual(out, 'Result type not recognised or unavailable for time of maximum')
        self.assertEqual(m, 0)

    def test_info_area_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('FC01.09', 'A')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test_4', 'Qin')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test_4', 'Qin')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test_4', 'Qout')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test_4', 'Qout')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_vol_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test_4', 'vol')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for PO')
        self.assertEqual(m, 0)

    def test_info_vol_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test_4', 'vol')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test_2', 'QA')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test_2', 'QA')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test_2', 'QI')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test_2', 'QI')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test_3', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for PO')
        self.assertEqual(m, 0)

    def test_info_water_level_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test_3', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_velocity_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test_3', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for PO')
        self.assertEqual(m, 0)

    def test_info_velocity_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test_3', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_vol_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test_2', 'Vol', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 1.2335)

    def test_info_vol_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test_2', 'Vol', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test', 'Q', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 0.9629)

    def test_info_flow_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test', 'Q', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximum('test_3', 'H', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 0)

    def test_info_water_level_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximum('test_3', 'H', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum not supported for 2013 format')
        self.assertEqual(m, 0)
        
        
class TestMaximumTimestepChange(unittest.TestCase):
    """Test maximumTimestepChange() function"""

    def test_tpc_flow_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('FC01.09', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_flow_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('FC01.09', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_velocity_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('FC01.09', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_velocity_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('FC01.09', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('ds5.2', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_water_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('ds5.2', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('ds5.2', 'E')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('ds5.2', 'E')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_area_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('FC01.09', 'A')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_area_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('FC01.09', 'A')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test_4', 'Qin')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test_4', 'Qin')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test_4', 'Qout')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test_4', 'Qout')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_vol_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test_4', 'vol')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_vol_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test_4', 'vol')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test_2', 'QA')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test_2', 'QA')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test_2', 'QI')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test_2', 'QI')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test_3', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_water_level_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test_3', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_velocity_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test_3', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_velocity_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test_3', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_vol_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test_2', 'Vol', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 19.896)

    def test_info_vol_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test_2', 'Vol', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test', 'Q', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 0.1671)

    def test_info_flow_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test', 'Q', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.maximumTimestepChange('test_3', 'H', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 0)

    def test_info_water_level_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.maximumTimestepChange('test_3', 'H', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)
        
        
class TestTimeOfMaximumTimestepChange(unittest.TestCase):
    """Test timeOfMaximumTimestepChange() function"""

    def test_tpc_flow_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('FC01.09', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_flow_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('FC01.09', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_velocity_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('FC01.09', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_velocity_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('FC01.09', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('ds5.2', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_water_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('ds5.2', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('ds5.2', 'E')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_energy_level_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('ds5.2', 'E')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_area_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('FC01.09', 'A')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 1D')
        self.assertEqual(m, 0)

    def test_info_area_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('FC01.09', 'A')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test_4', 'Qin')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_in_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test_4', 'Qin')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test_4', 'Qout')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_out_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test_4', 'Qout')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_vol_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test_4', 'vol')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_vol_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test_4', 'vol')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test', 'Q')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test_2', 'QA')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_area_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test_2', 'QA')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test_2', 'QI')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_flow_integral_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test_2', 'QI')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test_3', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_water_level_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test_3', 'H')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_velocity_2d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test_3', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for PO')
        self.assertEqual(m, 0)

    def test_info_velocity_2d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test_3', 'V')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_vol_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test_2', 'Vol', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 0.6413)

    def test_info_vol_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test_2', 'Vol', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_flow_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test', 'Q', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 0.8358)

    def test_info_flow_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test', 'Q', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)

    def test_tpc_water_level_rl(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, m = res.timeOfMaximumTimestepChange('test_3', 'H', 'RL')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(m, 0)

    def test_info_water_level_rl(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, m = res.timeOfMaximumTimestepChange('test_3', 'H', 'RL')
        self.assertTrue(err)
        self.assertEqual(out, 'Time of maximum timestep change not supported for 2013 format')
        self.assertEqual(m, 0)
        
        
class TestLongProfileResultTypes(unittest.TestCase):
    """Test longProfileResultTypes() function"""

    def test_tpc_flow_1d(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        t = res.longProfileResultTypes()
        self.assertEqual(t, ['Bed Level', 'H', 'E', 'Left Bank Obvert', 'Right Bank Obvert', 'Pit Ground Levels'])

    def test_info_flow_1d(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        t = res.longProfileResultTypes()
        self.assertEqual(t, ['Bed Level', 'H', 'Left Bank Obvert', 'Right Bank Obvert', 'Pit Ground Levels'])
        
        
class TestLongProfileData(unittest.TestCase):
    """Test getLongProfileData() function"""
    
    x_one_channel = [0.0001, 19.7999, 19.8, 79.9998, 79.9999, 107.79969999999999, 107.79979999999999, 122.79959999999998,
                     122.79969999999999, 168.49949999999998, 168.4996, 210.29939999999996, 210.29949999999997,
                     244.69929999999997, 244.69939999999997, 260.1992, 260.1993, 269.99910000000006, 269.99920000000003,
                     303.2990000000001, 303.29910000000007, 333.4989000000001, 333.4990000000001, 392.09880000000015,
                     392.0989000000001, 493.29870000000017, 493.29880000000014, 604.8986000000002, 604.8987000000002,
                     795.9985000000003, 795.9986000000002, 812.1984000000003]
    
    x_two_channels = [0.0001, 19.7999, 19.8, 79.9998, 79.9999, 107.79969999999999, 107.79979999999999,
                      122.79959999999998, 122.79969999999999, 168.49949999999998, 168.4996, 210.29939999999996]
    
    bed_level_one_channel = [37.6, 37.5, 37.462, 36.78, 36.78, 36.419, 36.419, 36.392, 36.392, 36.289, 36.289,
                             36.202, 36.202, 36.13, 36.13, 36.084, 36.084, 36.056, 36.056, 35.989, 35.95, 35.9,
                             35.9, 35.32, 35.32, 34.292, 34.292, 33.189, 33.189, 31.26, 32.58, 32.58]
    
    bed_level_two_channels = [37.6, 37.5, 37.462, 36.78, 36.78, 36.419, 36.419, 36.392, 36.392, 36.289, 36.289, 36.202]
    
    water_level_one_channel = [42.3451, 40.5331, 40.5331, 40.2207, 40.2207, 40.1175, 40.1175, 40.0827, 40.0827,
                               39.8871, 39.8871, 39.5294, 39.5294, 39.0808, 39.0808, 39.0024, 39.0024, 38.9586,
                               38.9586, 38.788, 38.788, 38.688, 38.688, 38.1795, 38.1795, 37.1793, 37.1793,
                               35.6358, 35.6358, 33.9942, 33.9942, 32.9532]
    
    water_level_two_channels = [42.3451, 40.5331, 40.5331, 40.2207, 40.2207, 40.1175, 40.1175, 40.0827,
                                40.0827, 39.8871, 39.8871, 39.5294]
    
    energy_level_one_channel = [42.3518, 40.6152, 40.6152, 40.2966, 40.2966, 40.1769, 40.1769, 40.1428, 40.1428,
                                39.9804, 39.9804, 39.6825, 39.6825, 39.2164, 39.2164, 39.0742, 39.0742, 39.0223,
                                39.0223, 38.8388, 38.8388, 38.7612, 38.7612, 38.3005, 38.3005, 37.3026, 37.3026,
                                35.7238, 35.7238, 34.0665, 34.0665, 33.1573]
    
    energy_level_two_channels = [42.3518, 40.6152, 40.6152, 40.2966, 40.2966, 40.1769, 40.1769, 40.1428,
                                 40.1428, 39.9804, 39.9804, 39.6825]
    
    left_ob_one_channel =  [38.8, 38.7, 39.519, 38.728, 38.728, 39.14, 39.14, 38.457, 41.516, 52.409, 43.051,
                            42.928, 42.928, 42.694, 41.81, 39.14, 39.14, 39.112, 38.825, 38.757, 38.457, 43.769,
                            43.754, 40.397, 42.5, 45.769, 44.317, 43.213, 44.666, 42.737, 40.397, 42.737]
    
    left_ob_two_channels = [38.8, 38.7, 39.519, 38.728, 38.728, 39.14, 39.14, 38.457, 41.516, 52.409, 43.051, 42.928]
    
    right_ob_one_channel = [38.8, 38.7, 39.986, 38.87, 38.87, 38.586, 38.586, 37.732, 41.516, 50.64, 41.532,
                            41.494, 41.494, 41.614, 41.045, 39.14, 39.14, 39.112, 38.825, 38.757, 37.732,
                            44.142, 44.317, 42.737, 42.056, 39.536, 39.636, 43.213, 44.666, 46.295, 42.737, 42.737]
    
    right_ob_two_channels = [38.8, 38.7, 39.986, 38.87, 38.87, 38.586, 38.586, 37.732, 41.516, 50.64, 41.532, 41.494]

    water_level_max_two_channels = [42.9328, 40.6786, 40.6786, 40.3747, 40.3747, 40.2696, 40.2696, 40.2332,
                                    40.2332, 40.0342, 40.0342, 39.6813]
    
    water_level_max_two_channels_info = [42.9327, 40.6786, 40.6786, 40.3747, 40.3747, 40.2695, 40.2695,
                                         40.2332, 40.2332, 40.0342, 40.0342, 39.6813]
    
    
    def test_tpc_bed_level_one_channel(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'Bed Level', 'FC01.2_R')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_one_channel, self.bed_level_one_channel))

    def test_info_bed_level_one_channel(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'Bed Level', 'FC01.2_R')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_one_channel, self.bed_level_one_channel))
        
    def test_tpc_bed_level_two_channel(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'Bed Level', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.bed_level_two_channels))

    def test_info_bed_level_two_channel(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'Bed Level', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.bed_level_two_channels))
        
    def test_tpc_water_level_one_channel(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'H', 'FC01.2_R')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_one_channel, self.water_level_one_channel))

    def test_info_water_level_one_channel(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'H', 'FC01.2_R')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_one_channel, self.water_level_one_channel))
        
    def test_tpc_water_level_two_channels(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'H', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.water_level_two_channels))

    def test_info_water_level_two_channels(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'H', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.water_level_two_channels))
        
    def test_tpc_energy_level_one_channel(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'E', 'FC01.2_R')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_one_channel, self.energy_level_one_channel))

    def test_info_energy_level_one_channel(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'E', 'FC01.2_R')
        self.assertTrue(err)
        self.assertEqual(out, 'Unrecognised result type')
        self.assertEqual(d, ([], []))
        
    def test_tpc_energy_level_two_channels(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'E', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.energy_level_two_channels))

    def test_info_energy_level_two_channels(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'E', 'FC01.2_R', 'FC01.05')
        self.assertTrue(err)
        self.assertEqual(out, 'Unrecognised result type')
        self.assertEqual(d, ([], []))
        
    def test_tpc_lob_one_channel(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'Left Bank Obvert', 'FC01.2_R')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_one_channel, self.left_ob_one_channel))

    def test_info_lob_one_channel(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'Left Bank Obvert', 'FC01.2_R')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_one_channel, self.left_ob_one_channel))
        
    def test_tpc_lob_two_channels(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'Left Bank Obvert', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.left_ob_two_channels))

    def test_info_lob_two_channels(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'Left Bank Obvert', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.left_ob_two_channels))
        
    def test_tpc_rob_one_channel(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'Right Bank Obvert', 'FC01.2_R')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_one_channel, self.right_ob_one_channel))

    def test_info_rob_one_channel(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'Right Bank Obvert', 'FC01.2_R')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_one_channel, self.right_ob_one_channel))
        
    def test_tpc_rob_two_channels(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData(1.0, 'Right Bank Obvert', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.right_ob_two_channels))

    def test_info_rob_two_channels(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData(1.0, 'Right Bank Obvert', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.right_ob_two_channels))
        
    def test_tpc_max_two_channels(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData('max', 'H', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.water_level_max_two_channels))

    def test_info_max_two_channels(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData('max', 'H', 'FC01.2_R', 'FC01.05')
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(d, (self.x_two_channels, self.water_level_max_two_channels_info))
        
        
class TestAdverseGradients(unittest.TestCase):
    """Test for getAdverseGradients() function"""
    
    advH = ([], [])
    advE = ([], [])
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData('max', 'H', 'FC01.2_R', 'FC01.05')
        advH, advE = res.getAdverseGradients()
        self.assertEqual(advH, self.advH)
        self.assertEqual(advE, self.advE)
        
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData('max', 'H', 'FC01.2_R', 'FC01.05')
        advH, advE = res.getAdverseGradients()
        self.assertEqual(advH, ([], []))
        self.assertEqual(advE, ([], []))


class TestPipes(unittest.TestCase):
    """Test for getPipes() function"""
    
    pipes = [[(0.0001, 37.6), (19.7999, 37.5), (19.7999, 38.7), (0.0001, 38.8)]]
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData('max', 'H', 'FC01.2_R', 'FC01.05')
        pipes = res.getPipes()
        self.assertEqual(pipes, self.pipes)
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData('max', 'H', 'FC01.2_R', 'FC01.05')
        pipes = res.getPipes()
        self.assertEqual(pipes, [[()]])
        
        
class TestLongProfileTimeOfMaximum(unittest.TestCase):
    """Test for getLongProfileTimeOfMaximum() function"""

    x_two_channels = [0.0001, 19.7999, 19.8, 79.9998, 79.9999, 107.79969999999999, 107.79979999999999,
                      122.79959999999998, 122.79969999999999, 168.49949999999998, 168.4996, 210.29939999999996]
    
    tom = [1.3377, 1.3521, 1.3521, 1.3627, 1.3627, 1.3652, 1.3652, 1.3658, 1.3658, 1.371, 1.371, 1.3829]
    
    def test_tpc(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2016', 'M04_5m_001.tpc')
        res = tu.ResData(tpc)
        err, out, d = res.getLongProfileData('max', 'H', 'FC01.2_R', 'FC01.05')
        tom = res.getLongProfileTimeOfMaximum()
        self.assertEqual(tom, (self.x_two_channels, self.tom))
    
    def test_info(self):
        dir = os.path.dirname(__file__)
        info = os.path.join(dir, '2013', 'M04_5m_001_1d.info')
        res = tu.ResData(info)
        err, out, d = res.getLongProfileData('max', 'H', 'FC01.2_R', 'FC01.05')
        tom = res.getLongProfileTimeOfMaximum()
        self.assertEqual(tom, ([], []))


class TestNCOutput(unittest.TestCase):

    def testNC(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2019', 'M03_5m_001.tpc')
        res = tu.ResData()
        err, mess = res.load(tpc)
        self.assertFalse(err)
        self.assertEqual("", mess)

        err, mess, data = res.getTimeSeriesData("FC01.2_R", "Q")

class TestDepthOutput(unittest.TestCase):

    def testDepth(self):
        tp_depth = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0.0033,0.501,0.6408,0.734,0.7981,0.888,0.9761,
                    1.0618,1.1487,1.2893,1.4666,1.687,1.8296,1.9982,2.1635,2.3153,2.451,2.5767,2.6919,2.7834,
                    2.8621,2.9266,2.9764,3.0149,3.0493,3.096,3.1597,3.2266,3.2881,3.3373,3.3752,3.4082,3.4414,
                    3.4786,3.5201,3.5646,3.6175,3.6692,3.7181,3.7672,3.8125,3.8527,3.8876,3.9163,3.9403,3.9595,
                    3.9748,3.9863,3.9959,4.0025,4.0068,4.0091,4.0096,4.0085,4.006,4.0023,3.9975,3.9915,3.9847,
                    3.977,3.9684,3.9591,3.9495,3.9384,3.927,3.9152,3.9024,3.8893,3.8754,3.8612,3.8465,3.8315,
                    3.8163,3.801,3.7859,3.771,3.7561,3.7414,3.7265,3.7113,3.6958,3.6797,3.6628,3.6452,3.6266,
                    3.6067,3.5853,3.5621,3.5369,3.5094,3.4797,3.4472,3.4126,3.3752,3.3356,3.2949,3.2528,3.2086,
                    3.168,3.1206,3.0724]
        tl_depth = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0.0033,0.501,0.6408,0.734,0.7981,0.888,0.9761,
                   1.0618,1.1487,1.2893,1.4666,1.687,0.459,0.2463,0.267,0.2778,0.3252,0.3475,0.3796,0.4148,
                   0.4447,0.4647,0.4764,0.4823,0.5025,0.5333,0.5442,0.5762,0.62,0.6169,0.6237,0.6426,0.6608,
                   0.6815,0.6866,0.7143,0.751,0.7909,0.8325,0.8349,0.8584,0.8772,0.8909,0.9206,0.9028,0.9021,
                   0.9176,0.9297,0.9392,0.946,0.93,0.9324,0.933,0.932,0.9296,0.926,0.9212,0.9154,0.9087,
                   0.9012,0.8928,0.9033,0.8936,0.8828,0.8717,0.8604,0.8481,0.8547,0.8414,0.8279,0.8526,
                   0.8378,0.823,0.8081,0.8129,0.7984,0.7841,0.7892,0.7749,0.7606,0.7652,0.7501,0.7343,
                   0.7368,0.739,0.7201,0.7198,0.698,0.675,0.6695,0.6434,0.6339,0.6049,0.6111,0.5798,
                   0.5677,0.538,0.5258,0.5172,0.4889,0.4616]

        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2020', 'EG07_1D2D_5m_001_HPC.tpc')
        res = tu.ResData()
        err, mess = res.load(tpc)
        self.assertFalse(err)
        self.assertEqual("", mess)
        err, mess, data = res.getTimeSeriesData("test_point", "D")
        self.assertFalse(err)
        self.assertEqual("", mess)
        self.assertEqual(tp_depth, data[1])
        err, mess, data = res.getTimeSeriesData("test_line", "D")
        self.assertFalse(err)
        self.assertEqual("", mess)
        self.assertEqual(tl_depth, data[1])

class TestReferenceTime(unittest.TestCase):

    def testSettingReferenceTime(self):
        rel_time1 = [0.0, 0.016667, 0.033333, 0.05, 0.066667, 0.083333, 0.1, 0.116667, 0.133333, 0.15, 0.166667,
                    0.183333, 0.2, 0.216667, 0.233333, 0.25, 0.266667, 0.283333, 0.3, 0.316667, 0.333333, 0.35,
                    0.366667, 0.383333, 0.4, 0.416667, 0.433333, 0.45, 0.466667, 0.483333, 0.5, 0.516667, 0.533333,
                    0.55, 0.566667, 0.583333, 0.6, 0.616667, 0.633333, 0.65, 0.666667, 0.683333, 0.7, 0.716667,
                    0.733333, 0.75, 0.766667, 0.783333, 0.8, 0.816667, 0.833333, 0.85, 0.866667, 0.883333, 0.9,
                    0.916667, 0.933333, 0.95, 0.966667, 0.983333, 1.0, 1.016667, 1.033333, 1.05, 1.066667, 1.083333,
                    1.1, 1.116667, 1.133333, 1.15, 1.166667, 1.183333, 1.2, 1.216667, 1.233333, 1.25, 1.266667,
                    1.283333, 1.3, 1.316667, 1.333333, 1.35, 1.366667, 1.383333, 1.4, 1.416667, 1.433333, 1.45,
                    1.466667, 1.483333, 1.5, 1.516667, 1.533333, 1.55, 1.566667, 1.583333, 1.6, 1.616667, 1.633333,
                    1.65, 1.666667, 1.683333, 1.7, 1.716667, 1.733333, 1.75, 1.766667, 1.783333, 1.8, 1.816667,
                    1.833333, 1.85, 1.866667, 1.883333, 1.9, 1.916667, 1.933333, 1.95, 1.966667, 1.983333, 2.0]
        r1 = datetime(1990, 1, 1, 0)

        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2020', 'EG07_1D2D_5m_001_HPC.tpc')
        res = tu.ResData()
        err, mess = res.load(tpc)
        self.assertFalse(err)
        self.assertEqual("", mess)
        timesteps = res.timesteps(datetime(2000, 1, 1, 0, 0, 0))
        self.assertEqual(timesteps, rel_time1)
        res.setReferenceTime(datetime(1990, 1, 1, 0, 0, 0))
        timesteps = res.timesteps()
        self.assertEqual(timesteps, rel_time1)
        dates = res.timesteps(asDates=True)
        self.assertEqual(dates, [roundSeconds(r1 + timedelta(hours=x), 2) for x in rel_time1])
        timesteps = res.timesteps(datetime(1989, 12, 31, 0, 0, 0))
        self.assertEqual(timesteps, [x + 24 for x in rel_time1])
        dates = res.timesteps(datetime(1989, 12, 31, 0, 0, 0), True)
        self.assertEqual(dates, [roundSeconds(r1 + timedelta(hours=x), 2) for x in rel_time1])
        res.setReferenceTime(datetime(2000, 1, 1, 0, 0, 0))
        timesteps = res.timesteps()
        self.assertEqual([round(x, 6) for x in timesteps], [round(x, 6) for x in rel_time1])
        timesteps = res.timesteps(datetime(1999, 12, 31, 0, 0, 0))
        self.assertEqual([round(x, 6) for x in timesteps], [round(x + 24, 6) for x in rel_time1])

    def testLoadReferenceTime(self):
        rel_time1 = [0, 0.016667, 0.033333, 0.05, 0.066667, 0.083333, 0.1, 0.116667, 0.133333, 0.15, 0.166667, 0.183333,
                 0.2, 0.216667, 0.233333, 0.25, 0.266667, 0.283333, 0.3, 0.316667, 0.333333, 0.35, 0.366667, 0.383333,
                 0.4, 0.416667, 0.433333, 0.45, 0.466667, 0.483333, 0.5, 0.516667, 0.533333, 0.55, 0.566667, 0.583333,
                 0.6, 0.616667, 0.633333, 0.65, 0.666667, 0.683333, 0.7, 0.716667, 0.733333, 0.75, 0.766667, 0.783333,
                 0.8, 0.816667, 0.833333, 0.85, 0.866667, 0.883333, 0.9, 0.916667, 0.933333, 0.95, 0.966667, 0.983333,
                 1, 1.016667, 1.033333, 1.05, 1.066667, 1.083333, 1.1, 1.116667, 1.133333, 1.15, 1.166667, 1.183333,
                 1.2, 1.216667, 1.233333, 1.25, 1.266667, 1.283333, 1.3, 1.316667, 1.333333, 1.35, 1.366667, 1.383333,
                 1.4, 1.416667, 1.433333, 1.45, 1.466667, 1.483333, 1.5, 1.516667, 1.533333, 1.55, 1.566667, 1.583333,
                 1.6, 1.616667, 1.633333, 1.65, 1.666667, 1.683333, 1.7, 1.716667, 1.733333, 1.75, 1.766667, 1.783333,
                 1.8, 1.816667, 1.833333, 1.85, 1.866667, 1.883333, 1.9, 1.916667, 1.933333, 1.95, 1.966667, 1.983333,
                 2, 2.016667, 2.033334, 2.05, 2.066667, 2.083333, 2.1, 2.116667, 2.133333, 2.15, 2.166667, 2.183333,
                 2.2, 2.216667, 2.233333, 2.25, 2.266667, 2.283334, 2.3, 2.316667, 2.333333, 2.35, 2.366667, 2.383333,
                 2.4, 2.416667, 2.433333, 2.45, 2.466667, 2.483333, 2.5, 2.516667, 2.533334, 2.55, 2.566667, 2.583333,
                 2.6, 2.616667, 2.633333, 2.65, 2.666667, 2.683333, 2.7, 2.716667, 2.733334, 2.75, 2.766667, 2.783334,
                 2.8, 2.816667, 2.833333, 2.85, 2.866667, 2.883333, 2.9, 2.916667, 2.933333, 2.95, 2.966667, 2.983334,
                 3]
        r1 = datetime(1990, 1, 1, 0)

        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2020', 'EG07_1D2D_5m_001_CLA.tpc')
        res = tu.ResData()
        err, mess = res.load(tpc)
        self.assertFalse(err)
        self.assertEqual("", mess)
        rt = res.referenceTime()
        self.assertEqual(rt, r1)
        timesteps = res.timesteps()
        self.assertEqual(timesteps, rel_time1)
        dates = res.timesteps(asDates=True)
        self.assertEqual(dates, [roundSeconds(r1 + timedelta(hours=x), 2) for x in rel_time1])


class TestImportFV(unittest.TestCase):

    def test_tpc_test_rig(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2021', 'trap_steady_05_005.tpc')
        res = tu.ResData()
        err, out = res.load(tpc)
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(res.poNames(), ['ADCP1', 'ADCP2', 'ADCP3', 'NS1', 'NS2', 'NS3', 'NS4', 'NS5', 'NS6'])
        self.assertEqual(res.poResultTypes(), ['Q', 'TRACE_1_FLUX', 'TRACE_2_FLUX', 'H', 'Vx', 'Vy'])
        err, msg, (x,y) = res.getTimeSeriesData('NS1', 'TRACE_1_FLUX')
        self.assertFalse(err)
        self.assertEqual(out, '')

    def test_tpc_frankenmodel(self):
        dir = os.path.dirname(__file__)
        tpc = os.path.join(dir, '2021', 'frankenmodel.tpc')
        res = tu.ResData()
        err, out = res.load(tpc)
        self.assertFalse(err)
        self.assertEqual(out, '')
        self.assertEqual(res.poNames(), ['ADCP1', 'ADCP2', 'ADCP3', 'NS1', 'NS2', 'NS3', 'NS4', 'NS5', 'NS6'])
        self.assertEqual(res.poResultTypes(),
                         ['Q', 'SALT_FLUX', 'TEMP_FLUX', 'SED_1_FLUX', 'SED_2_FLUX', 'TRACE_1_FLUX', 'TRACE_2_FLUX',
                          'SED_1_BEDLOAD_FLUX', 'SED_2_BEDLOAD_FLUX', 'H', 'Vx', 'Vy', 'temperature', 'salinity',
                          'sediment fraction 1 concentration', 'sediment fraction 2 concentration',
                          'tracer 1 concentration', 'tracer 2 concentration'])
        err, msg, (x,y) = res.getTimeSeriesData('NS3', 'SALT_FLUX')
        self.assertFalse(err)
        self.assertEqual(out, '')





# if __name__ == '__main__':
#     unittest.main()