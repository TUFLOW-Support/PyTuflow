import os, sys
sys.path.append(os.path.dirname(__file__))
import TUFLOW_results
import TUFLOW_results2013


class ResData():
    """
    Class for handling TUFLOW Time Series result data. This class is intended as the high level class
    to be used when extracting TUFLOW results. Class from TUFLOW_results and TUFLOW_results2013 should not
    be used.
    """
    
    def __init__(self, file=None):
        self._res = None
        self._format = ''  # 2013 or 2016 file formats
        if file is not None:
            self.load(file)
    
    def format(self):
        """
        Returns the format of the loaded input file
        .TPC = 2016 format
        .INFO = 2013 format
        
        :return: str file format
        """
        
        return self._format
    
    def name(self):
        """
        Returns the name of the results file
        e.g. 'M03_5m_001'
        
        :return: str name
        """
        
        if self._res is not None:
            return os.path.splitext(os.path.basename(self._res.filename))[0]
        
        return ''
    
    def source(self):
        """
        Returbs the source file (the .tpc or .info file)
        
        :return: str full path to source
        """

        if self._res is not None:
            return self._res.filename

        return ''
        
    def load(self, file):
        """
        Load result file from either .tpc or .info. Returns ( Error, Message )
        if Error is False then file was loaded successfully.
        
        :param file: str full path to .tpc or .info file
        :return: bool Error, str Message
        """
        
        ext = os.path.splitext(file)[1].upper()
        if ext == '.TPC':
            self._res = TUFLOW_results.ResData()
            err, out = self._res.load(file)
            if not err:
                self._format = '2016'
        elif ext == '.INFO':
            self._res = TUFLOW_results2013.ResData()
            err, out = self._res.load(file)
            if not err:
                self._format = '2013'
        else:
            err = True
            out = 'Unrecognised file extension'
            
        return err, out
    
    def channels(self):
        """
        Returns a list of channel names in the results.
        
        :return: list -> str channel name
        """
        
        if self._res is not None:
            return self._res.Channels.chan_name
        
        return []
    
    def nodes(self):
        """
        Returns a lits of node names in the results.
        
        :return: list -> str node name
        """
        
        if self._res is not None:
            return self._res.nodes.node_name[:]
        
        return []
    
    def channelCount(self):
        """
        Returns the number of channels in the results.
        
        :return: int
        """
        
        if self._res is not None:
            return self._res.Data_1D.nChan
        
        return 0
    
    def nodeCount(self):
        """
        Returns the number of nodes in the results.
        
        :return: int
        """
        
        if self._res is not None:
            return self._res.Data_1D.nNode
        
        return 0
    
    def nodeUpstream(self, channelName):
        """
        Returns the upstream node name of the input channel.
        
        :param channelName: str channel name
        :return: str node name
        """
        
        if self._res is not None:
            for i, channel in enumerate(self._res.Channels.chan_name):
                if channelName.lower() == channel.lower():
                    return self._res.Channels.chan_US_Node[i]
        
        return ''
    
    def nodeDownstream(self, channelName):
        """
        Returns the downstream node name of the input channel.
        
        :param channelName: str channel name
        :return: str node name
        """

        if self._res is not None:
            for i, channel in enumerate(self._res.Channels.chan_name):
                if channelName.lower() == channel.lower():
                    return self._res.Channels.chan_DS_Node[i]

        return ''
    
    def channelConnections(self, nodeName):
        """
        Returns the channels connected to the node.
        
        :param nodeName: str node Name
        :return: list -> str channel name
        """
        
        if self._res is not None:
            for i, node in enumerate(self._res.nodes.node_name):
                if nodeName.lower() == node.lower():
                    return self._res.nodes.node_channels[i][:]
        
        return []
    
    def channelConnectionCount(self, nodeName):
        """
        Returns the number of channels connected to the node.
        
        :param nodeName: str node name
        :return: int
        """
        
        if self._res is not None:
            for i, node in enumerate(self._res.nodes.node_name):
                if nodeName.lower() == node.lower():
                    return self._res.nodes.node_nChan[i]
        
        return 0
    
    def channelsUpstream(self, nodeName):
        """
        Returns the channel upstream of the input node.
        
        :param nodeName: str node name
        :return: list -> str channel name
        """
        
        if self._res is not None:
            connectionChannels = self.channelConnections(nodeName)
            channels = []
            for channel in connectionChannels:
                downstreamNode = self.nodeDownstream(channel)
                if downstreamNode.lower() == nodeName.lower():
                    channels.append(channel)
            return channels
            
        return []
    
    def channelsDownstream(self, nodeName):
        """
        Returns the channel downstream of the input node.
        
        :param nodeName: str node name
        :return: list -> str channel name
        """

        if self._res is not None:
            connectionChannels = self.channelConnections(nodeName)
            channels = []
            for channel in connectionChannels:
                upstreamNode = self.nodeUpstream(channel)
                if upstreamNode.lower() == nodeName.lower():
                    channels.append(channel)
            return channels

        return []
    
    def channelResultTypes(self):
        """
        Returns a list of the result types available for channels.
        
        :return: list -> str result type
        """
        
        if self._res is not None:
            rtypes = []
            for rtype in self._res.Types:
                if '1D Flow Area' in rtype:
                    rtypes.append('A')
                elif '1D Velocities' in rtype:
                    rtypes.append('V')
                elif '1D Flow' in rtype:
                    rtypes.append('Q')
                elif '1D CHANNEL FLOW REGIME' in rtype.upper():
                    rtypes.append('F')
                elif '1D CHANNEL LOSSES' in rtype.upper():
                    rtypes.append('L')
            return rtypes
            
        return []
    
    def nodeResultTypes(self):
        """
        Returns a list of the result types available for nodes.
        
        :return: list -> str result type
        """
        
        if self._res is not None:
            rtypes = []
            for rtype in self._res.Types:
                if '1D Water Levels' in rtype:
                    rtypes.append('H')
                elif '1D Energy Levels' in rtype:
                    rtypes.append('E')
                elif '1D MASS BALANCE ERROR' in rtype.upper():
                    rtypes.append('MB')
                elif '1D NODE FLOW REGIME' in rtype.upper():
                    rtypes.append('F')
            return rtypes
        
        return []
    
    def poNames(self):
        """
        Returns a list of the 2D Plot Outputs (2d_po)
        
        :return: list -> str po name
        """
        
        if self._res is not None:
            if self._format == '2016':
                names = []
                if self._res.Data_2D.H.loaded:
                    names += self._res.Data_2D.H.ID
                if self._res.Data_2D.V.loaded:
                    names += self._res.Data_2D.V.ID
                if self._res.Data_2D.Q.loaded:
                    names += self._res.Data_2D.Q.ID
                if self._res.Data_2D.GL.loaded:
                    names += self._res.Data_2D.GL.ID
                if self._res.Data_2D.QA.loaded:
                    names += self._res.Data_2D.QA.ID
                if self._res.Data_2D.QI.loaded:
                    names += self._res.Data_2D.QI.ID
                if self._res.Data_2D.Vx.loaded:
                    names += self._res.Data_2D.Vx.ID
                if self._res.Data_2D.Vy.loaded:
                    names += self._res.Data_2D.Vy.ID
                if self._res.Data_2D.QS.loaded:
                    names += self._res.Data_2D.QS.ID
                if self._res.Data_2D.HUS.loaded:
                    names += self._res.Data_2D.HUS.ID
                if self._res.Data_2D.HDS.loaded:
                    names += self._res.Data_2D.HDS.ID
                if self._res.Data_2D.HAvg.loaded:
                    names += self._res.Data_2D.HAvg.ID
                if self._res.Data_2D.HMax.loaded:
                    names += self._res.Data_2D.HMax.ID
                if self._res.Data_2D.QIn.loaded:
                    names += self._res.Data_2D.QIn.ID
                if self._res.Data_2D.QOut.loaded:
                    names += self._res.Data_2D.QOut.ID
                if self._res.Data_2D.SS.loaded:
                    names += self._res.Data_2D.SS.ID
                if self._res.Data_2D.Vol.loaded:
                    names += self._res.Data_2D.Vol.ID
                names_unique = []
                for name in names:
                    if name not in names_unique:
                        names_unique.append(name)
                return sorted(names_unique)
        
        return []
    
    def poResultTypes(self):
        """
        Returns a list of the available Plot Output (2d_po) result types.
        
        :return: list -> str result type
        """
        
        if self._res is not None:
            if self._format == '2016':
                return self._res.Data_2D.types[:]
            
        return []
    
    def rlNames(self):
        """
        Returns a list of the 2D Reporting Locations (2D_RL).
        
        :return: list -> str RL name
        """

        if self._res is not None:
            if self._format == '2016':
                names = []
                if self._res.Data_RL.H_P is not None:
                    names += self._res.Data_RL.H_P.ID
                if self._res.Data_RL.Q_L is not None:
                    names += self._res.Data_RL.Q_L.ID
                if self._res.Data_RL.Vol_R is not None:
                    names += self._res.Data_RL.Vol_R.ID
                names_unique = []
                for name in names:
                    if name not in names_unique:
                        names_unique.append(name)
                return sorted(names_unique)
            
        return []
    
    def rlResultTypes(self):
        """
        Returns a list of the available Reporting Location (2d_RL) result types.
        
        :return: list -> str result type
        """
        
        if self._res is not None:
            if self._format == '2016':
                return self._res.Data_RL.types[:]
            
        return []
    
    def rlPointCount(self):
        """
        Returns the number of Reporting Location (2d_RL) point objects.
        
        :return: int
        """
        
        if self._res is not None:
            if self._format == '2016':
                return self._res.Data_RL.nPoint
                
        return 0

    def rlLineCount(self):
        """
        Returns the number of Reporting Location (2d_RL) point objects.

        :return: int
        """

        if self._res is not None:
            if self._format == '2016':
                return self._res.Data_RL.nLine
    
        return 0

    def rlRegionCount(self):
        """
        Returns the number of Reporting Location (2d_RL) point objects.

        :return: int
        """

        if self._res is not None:
            if self._format == '2016':
                return self._res.Data_RL.nRegion
    
        return 0
    
    def rlCount(self):
        """
        Returns the number of Reporting Location (2d_RL) objects.

        :return: int
        """
        
        if self._res is not None:
            if self._format == '2016':
                return self.rlPointCount() + self.rlLineCount() + self.rlRegionCount()
            
        return 0
    
    def timesteps(self):
        """
        Returns a list of the available timesteps.
        Assumes all results have the same x-axis.
        
        :return: list -> float timestep
        """
        
        if self._res is not None:
            return self._res.timeSteps()
        
        return []
    
    def getTimeSeriesData(self, element, resultType, domain=None):
        """
        Get time series data for a given element and result type
        e.g. 'Channel_1' and 'Q'
        Returns err, out, data - if an error occured err = True
        
        :param element: str name of 1D node or 1D channel or 2D PO or 2D RL
        :param resultType: str result type
        :param domain: str domain can be '1d' '2d' or 'rl'
                       if None, will guess what domain is and if there are duplicate names it will assume 1D first
                       2D second, RL last
        :return: bool Error, str Message, tuple ( list x data -> float, list y data -> float )
        """
        
        if self._res is not None:
            if domain is None:
                poNames = [x.lower() for x in self.poNames()]
                rlNames = [x.lower() for x in self.rlNames()]
                channels = [x.lower() for x in self.channels()]
                nodes = [x.lower() for x in self.nodes()]
                if element.lower() not in channels and element.lower() not in nodes:
                    if self._format == '2013':
                        return True, 'PO and RL outputs not supported in 2013 format', ([], [])
                if element.lower() in poNames:
                    domain = '2D'
                elif element.lower() in rlNames:
                    domain = 'RL'
                else:
                    domain = '1D'
            elif domain.upper() == '1D' or domain.upper() == '2D' or domain.upper() == 'RL':
                if domain.upper() == '2D' or domain.upper() == 'RL':
                    if self._format == '2013':
                        return True, 'PO and RL outputs not supported in 2013 format', ([], [])
            else:
                return True, 'Unrecognised domain type', ([], [])
            x = self.timesteps()
            success, y, out = self._res.getTSData(element, resultType, domain)
            if success:
                if len(y.shape) == 1:
                    return False, out, (x, y.tolist())
                else:
                    y_list = []
                    for i in range(y.shape[1]):
                        y_list.append(y[:,i].tolist())
                    return False, out, (x, y_list)
            else:
                return True, out, ([], [])
        
        return True, 'No results loaded', ([], [])
    
    def maximum(self, element, resultType, domain=None):
        """
        Gets the maximum for a given element and result type.
        e.g. 'Channel_a' and 'Q'
        Maximum is true maximum of every timestep.
        Supported types for nodes are 'H' and 'E'. Supported types for channels are 'Q' and 'V'.
        
        :param element: str name of 1D node or 1D channel
        :param resultType: str result type
        :param domain: str domain can be '1d' '2d' or 'rl'
                       if None, will guess what domain is and if there are duplicate names it will assume 1D first
                       2D second, RL last
        :return: bool Error, str Message, float maximum
        """
        
        if self._res is not None:
            if self._format == '2013':
                return True, 'Maximums not supported for 2013 format', 0
            poNames = [x.lower() for x in self.poNames()]
            rlNames = [x.lower() for x in self.rlNames()]
            channels = [x.lower() for x in self.channels()]
            nodes = [x.lower() for x in self.nodes()]
            if domain is None:
                if element.lower() in channels or element.lower() in nodes:
                    domain = '1D'
                elif element.lower() in poNames:
                    return True, 'Maximums not supported for PO', 0
                else:
                    domain = 'RL'
            elif domain.upper() == '1D' or domain.upper() == '2D' or domain.upper() == 'RL':
                if domain.upper() == 'PO':
                    return True, 'Maximums not support for PO', 0
            else:
                return True, 'Unrecognised domain type', 0
            if domain.upper() == '1D':
                if element.lower() in nodes:
                    ids = [x.lower() for x in self._res.Data_1D.Node_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        if resultType.upper() == 'H':
                            return False, '', self._res.Data_1D.Node_Max.HMax[i]
                        elif resultType.upper() == 'E':
                            return False, '', self._res.Data_1D.Node_Max.EMax[i]
                        else:
                            return True, 'Result type not recognised or unavailable as max type', 0
                    else:
                        return True, 'Unexpected Error - could not find element in node max ids', 0
                elif element.lower() in channels:
                    ids = [x.lower() for x in self._res.Data_1D.Chan_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        if resultType.upper() == 'Q':
                            return False, '', self._res.Data_1D.Chan_Max.QMax[i]
                        elif resultType.upper() == 'V':
                            return False, '', self._res.Data_1D.Chan_Max.VMax[i]
                        else:
                            return True, 'Result type not recognised or unavailable as max type', 0
                    else:
                        return True, 'Unexpected Error - could not find element in channel max ids', 0
                else:
                    return True, 'Could not find element ID in available results', 0
            elif domain.upper() == 'RL':
                if resultType.upper() == 'H':
                    ids = [x.lower() for x in self._res.Data_RL.P_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.P_Max.HMax[i]
                elif resultType.upper() == 'Q':
                    ids = [x.lower() for x in self._res.Data_RL.L_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.L_Max.QMax[i]
                elif resultType.upper() == 'VOL':
                    ids = [x.lower() for x in self._res.Data_RL.R_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.R_Max.VolMax[i]
                else:
                    return True, 'Unrecognised result type for Reporting Locations', 0
                
        return True, 'No results loaded', 0
    
    def timeOfMaximum(self, element, resultType, domain=None):
        """
        Get the time of maximum for a given element and result type.
        e.g. 'Channel_1' and 'H'
        Only supported type for node is 'H'. Only support type for channel is 'V'.
        
        :param element: str name of 1D node or 1D channel
        :param resultType: str result type
        :param domain: str domain can be '1d' '2d' or 'rl'
                       if None, will guess what domain is and if there are duplicate names it will assume 1D first
                       2D second, RL last
        :return: bool Error, str Message, float time
        """
        
        if self._res is not None:
            if self._format == '2013':
                return True, 'Time of maximum not supported for 2013 format', 0
            poNames = [x.lower() for x in self.poNames()]
            rlNames = [x.lower() for x in self.rlNames()]
            channels = [x.lower() for x in self.channels()]
            nodes = [x.lower() for x in self.nodes()]
            if domain is None:
                if element.lower() in channels or element.lower() in nodes:
                    domain = '1D'
                elif element.lower() in poNames:
                    return True, 'Time of maximum not supported for PO', 0
                else:
                    domain = 'RL'
            elif domain.upper() == '1D' or domain.upper() == '2D' or domain.upper() == 'RL':
                if domain.upper() == '2D':
                    return True, 'Time of maximum not supported for PO', 0
            else:
                return True, 'Unrecognised domain type', 0
            if domain.upper() == '1D':
                if element.lower() in nodes:
                    ids = [x.lower() for x in self._res.Data_1D.Node_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        if resultType.upper() == 'H':
                            return False, '', self._res.Data_1D.Node_Max.tHmax[i]
                        else:
                            return True, 'Result type not recognised or unavailable for time of maximum', 0
                    else:
                        return True, 'Unexpected Error - could not find element in node time of maximum ids', 0
                elif element.lower() in channels:
                    ids = [x.lower() for x in self._res.Data_1D.Chan_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        if resultType.upper() == 'V':
                            return False, '', self._res.Data_1D.Chan_Max.tVmax[i]
                        elif resultType.upper() == 'Q':
                            return False, '', self._res.Data_1D.Chan_Max.tQmax[i]
                        else:
                            return True, 'Result type not recognised or unavailable for time of maximum', 0
                    else:
                        return True, 'Unexpected Error - could not find element in channel time of maximum ids', 0
                else:
                    return True, 'Could not find element ID in available results', 0
            elif domain.upper() == 'RL':
                if resultType.upper() == 'H':
                    ids = [x.lower() for x in self._res.Data_RL.P_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.P_Max.tHmax[i]
                elif resultType.upper() == 'Q':
                    ids = [x.lower() for x in self._res.Data_RL.L_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.L_Max.tQmax[i]
                elif resultType.upper() == 'VOL':
                    ids = [x.lower() for x in self._res.Data_RL.R_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.R_Max.tVolMax[i]
                else:
                    return True, 'Unrecognised result type for Reporting Locations', 0

        return True, 'No results loaded', 0
    
    def maximumTimestepChange(self, element, resultType, domain=None):
        """
        Maximum change in value in one timestep for a give results.
        Only available for Reporting Locations.
        
        :param element: str name of 1D node or 1D channel
        :param resultType: str result type
        :param domain: str domain can be '1d' '2d' or 'rl'
                       if None, will guess what domain is and if there are duplicate names it will assume 1D first
                       2D second, RL last
        :return: bool Error, str Message, float value
        """

        if self._res is not None:
            if self._format == '2013':
                return True, 'Maximum timestep change not supported for 2013 format', 0
            poNames = [x.lower() for x in self.poNames()]
            rlNames = [x.lower() for x in self.rlNames()]
            channels = [x.lower() for x in self.channels()]
            nodes = [x.lower() for x in self.nodes()]
            if domain is None:
                if element.lower() in channels or element.lower() in nodes:
                    domain = '1D'
                elif element.lower() in poNames:
                    domain = '2D'
                else:
                    domain = 'RL'
            if domain.upper() == '1D' or domain.upper() == '2D' or domain.upper() == 'RL':
                if domain.upper() == '1D':
                    return True, 'Maximum timestep change not supported for 1D', 0
                elif domain.upper() == '2D':
                    return True, 'Maximum timestep change not supported for PO', 0
            else:
                return True, 'Unrecognised domain type', 0
            if domain.upper() == 'RL':
                if resultType.upper() == 'H':
                    ids = [x.lower() for x in self._res.Data_RL.P_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.P_Max.dHMax[i]
                elif resultType.upper() == 'Q':
                    ids = [x.lower() for x in self._res.Data_RL.L_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.L_Max.dQMax[i]
                elif resultType.upper() == 'VOL':
                    ids = [x.lower() for x in self._res.Data_RL.R_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.R_Max.dVolMax[i]
                else:
                    return True, 'Unrecognised result type for Reporting Locations', 0

        return True, 'No results loaded', 0

    def timeOfMaximumTimestepChange(self, element, resultType, domain=None):
        """
        Time of maximum change in value in one timestep for a give results.
        Only available for Reporting Locations.

        :param element: str name of 1D node or 1D channel
        :param resultType: str result type
        :param domain: str domain can be '1d' '2d' or 'rl'
                       if None, will guess what domain is and if there are duplicate names it will assume 1D first
                       2D second, RL last
        :return: bool Error, str Message, float time
        """
    
        if self._res is not None:
            if self._format == '2013':
                return True, 'Time of maximum timestep change not supported for 2013 format', 0
            poNames = [x.lower() for x in self.poNames()]
            rlNames = [x.lower() for x in self.rlNames()]
            channels = [x.lower() for x in self.channels()]
            nodes = [x.lower() for x in self.nodes()]
            if domain is None:
                if element.lower() in channels or element.lower() in nodes:
                    domain = '1D'
                elif element.lower() in poNames:
                    domain = '2D'
                else:
                    domain = 'RL'
            if domain.upper() == '1D' or domain.upper() == '2D' or domain.upper() == 'RL':
                if domain.upper() == '1D':
                    return True, 'Time of maximum timestep change not supported for 1D', 0
                elif domain.upper() == '2D':
                    return True, 'Time of maximum timestep change not supported for PO', 0
            else:
                return True, 'Unrecognised domain type', 0
            if domain.upper() == 'RL':
                if resultType.upper() == 'H':
                    ids = [x.lower() for x in self._res.Data_RL.P_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.P_Max.tdHmax[i]
                elif resultType.upper() == 'Q':
                    ids = [x.lower() for x in self._res.Data_RL.L_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.L_Max.tdQmax[i]
                elif resultType.upper() == 'VOL':
                    ids = [x.lower() for x in self._res.Data_RL.R_Max.ID]
                    if element.lower() in ids:
                        i = ids.index(element.lower())
                        return False, '', self._res.Data_RL.R_Max.tdVolMax[i]
                else:
                    return True, 'Unrecognised result type for Reporting Locations', 0
    
        return True, 'No results loaded', 0
    
    
    def getLongProfileData(self, timestep, resultType, channel, channel2=None):
        """
        Get long profile data for a given channel(s) for a result type.
        e.g. 1.0, 'H', 'Channel_1'
        Specifying one element will get data until downstream point. Specifying two elements will
        get data between the two elements.
        
        :param timestep: float
        :param resultType: str result type
        :param channel: str channel name
        :param channel2: str channel name
        :return: bool Error, str Message, tuple ( list x data -> float, list y data - > float )
        """
        
        if self._res is not None:
            err, out = self._res.getLPConnectivity(channel, channel2)
            if err:
                return True, out, ([], [])
            else:
                err, out = self._res.getLPStaticData()
                if err:
                    return True, out, ([], [])
                else:
                    if type(timestep) is str:
                        if timestep.lower() == 'max' or timestep.lower() == 'maximum':
                            timestep = -99999
                        else:
                            try:
                                timestep = float(timestep)
                            except ValueError:
                                return True, 'Timestep not valid', ([], [])
                    elif timestep == 99999:
                        timestep = -99999
                    err, out, data = self._res.getLongPlotXY(resultType, timestep)
                    if err:
                        return True, out, ([], [])
                    return False, '', data
            
        return True, 'No results loaded', ([], [])
    
    def getAdverseGradients(self):
        """
        Get any adverse water level or energy gradients in current long profile.
        getLongProfile() must be called before calling getAdverseGradients().
        Returns point X, Y locations of adverse gradients
        
        :return: adverse water level (list x data, list y data), adverse energy level (list x data, list y data)
        """
        
        if self._res is not None:
            if self._format != '2013':
                if self._res.LP.chan_list:
                    return (self._res.LP.adverseH.chainage[:], self._res.LP.adverseH.elevation[:]), \
                           (self._res.LP.adverseE.chainage[:], self._res.LP.adverseE.elevation[:])
            
        return ([], []), ([], [])
    
    def getPipes(self):
        """
        Gets pipe data in current long profile in matplotlib patch format.
        getLongProfile() must be called before calling getPipes().
        Returns in matplotlib patch format
        
        :return: pipe list -> vertex list for each pipe -> tuple ( x point, y point )
        """

        if self._res is not None:
            if self._format != '2013':
                if self._res.LP.chan_list:
                    return self._res.LP.culv_verts[:]
            
        return [[()]]
    
    def longProfileResultTypes(self):
        """
        Returns a list of the available result types for long profile plotting.
        
        :return: list -> str result type
        """
        
        if self._res is not None:
            rtypes = self.nodeResultTypes()
            rtypes.insert(0, 'Bed Level')
            rtypes.append('Left Bank Obvert')
            rtypes.append('Right Bank Obvert')
            rtypes.append('Pit Ground Levels')
            return rtypes
        
        return []
        
    def getLongProfileTimeOfMaximum(self):
        """
        Gets the time of maximum for water level along the current long profile.
        getLongProfile() must be called before calling getLongProfileTimeOfMaximum()
        
        :return: list x data, list y data
        """
        
        if self._res is not None:
            if self._format != '2013':
                if self._res.LP.chan_list:
                    return self._res.LP.dist_chan_inverts[:], self._res.LP.tHmax[:]
            
        return [], []


if __name__ == "__main__":
    # debugging
    tpc = r"C:\_Tutorial\TUFLOW\results\M03\2d\plot\M03_5m_001.tpc"
    res = ResData()
    err, mess = res.load(tpc)
    if err:
        print(mess)
    err, mess, data = res.getTimeSeriesData("FC01.2_R", "CF")
    if err:
        print(mess)

    print("Finisehd")