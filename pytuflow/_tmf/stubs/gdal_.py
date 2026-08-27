# noinspection PyPep8Naming
class gdal_:

    CE_None = 0
    CE_Debug = 1
    CE_Warning = 2
    CE_Failure = 3
    CE_Fatal = 4

    @staticmethod
    def PushErrorHandler(*args, **kwargs):
        pass

    @staticmethod
    def PopErrorHandler(*args, **kwargs):
        pass

    @staticmethod
    def OpenEx(*args, **kwargs):
        raise NotImplementedError('GDAL/OGR python bindings not installed')

    @staticmethod
    def Open(*args, **kwargs):
        raise NotImplementedError('GDAL/OGR python bindings not installed')

    @staticmethod
    def TranslateOptions(*args, **kwargs):
        raise NotImplementedError('GDAL/OGR python bindings not installed')

    @staticmethod
    def Translate(*args, **kwargs):
        raise NotImplementedError('GDAL/OGR python bindings not installed')
