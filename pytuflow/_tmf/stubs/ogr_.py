# noinspection PyPep8Naming
class ogr_:

    OGRERR_NONE = 0

    OFTInteger = 100
    OFTReal = 101
    OFTString = 102
    OFTInteger64 = 103
    OFTIntegerList = 104
    OFTRealList = 105
    OFTStringList = 106
    OFTWideString = 107
    OFTInteger64List = 108

    wkbPoint = 200
    wkbLineString = 201
    wkbPolygon = 202
    wkbMultiPoint = 300
    wkbMultiLineString = 301
    wkbMultiPolygon = 302

    @staticmethod
    def UseExceptions(*args, **kwargs):
        pass

    @staticmethod
    def GetDriverByName(*args, **kwargs):
        raise NotImplementedError('GDAL/OGR python bindings not installed')

    @staticmethod
    def FieldDefn(*args, **kwargs):
        raise NotImplementedError('GDAL/OGR python bindings not installed')

    @staticmethod
    def Feature(*args, **kwargs):
        raise NotImplementedError('GDAL/OGR python bindings not installed')
