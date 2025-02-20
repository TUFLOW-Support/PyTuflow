try:
    from qgis.core import (QgsMesh3dAveragingMethod, QgsMeshMultiLevelsAveragingMethod,
                           QgsMeshRelativeHeightAveragingMethod, QgsMeshElevationAveragingMethod,
                           QgsMeshSigmaAveragingMethod)
    has_qgis = True
except ImportError:
    has_qgis = False
    QgsMesh3dAveragingMethod = 'QgsMesh3dAveragingMethod'
    QgsMeshMultiLevelsAveragingMethod = None
    QgsMeshRelativeHeightAveragingMethod = None
    QgsMeshElevationAveragingMethod = None
    QgsMeshSigmaAveragingMethod = None



class AveragingMethod:
    """Class for converting a string uri averaging method into a QgsMesh3dAveragingMethod object.

    The uri should follow this convention:

    * <name>?dir=<dir>&<value1>&<value2>

    Where name = singlelevel, multilevel, depth, height, elevation, sigma

    Where dir = top or bottom (only used by certain averaging methods - so can be omitted if not needed)

    Where value1, value2... = the values to be used in the averaging method (any number can be passed)
    """

    def __new__(cls, method: str):
        if isinstance(method, str):
            return object.__new__(cls.cls_from_string(method))
        return object.__new__(cls)

    def __init__(self, method: str):
        self.valid = False
        self._name, self._vals, self._mod = self.attr_from_string(method)

    def __repr__(self):
        return f'<{self.__class__.__name__}>'

    @classmethod
    def cls_from_string(cls, method: str):
        name = method.split('&')[0].split('?')[0]
        if name == 'singlelevel':
            return SingleLevel
        if name == 'multilevel':
            return MultiLevel
        if name == 'depth':
            return Depth
        if name == 'height':
            return Height
        if name == 'elevation':
            return Elevation
        if name == 'sigma':
            return Sigma
        return cls

    @staticmethod
    def attr_from_string(method: str):
        vals = None
        name = None
        if isinstance(method, str) and '&' in method:
            name, vals = method.split('&', 1)
        vals = vals.split('&') if vals is not None else [None, None]
        mod = None
        if isinstance(name, str) and '?' in name:
            name, mod = name.split('?', 1)
            if '=' in mod:
                k, v = mod.split('=', 1)
                if k == 'dir':
                    mod = v
        return name, vals, mod

    def to_qgis(self) -> QgsMesh3dAveragingMethod:
        raise NotImplementedError


class SingleLevel(AveragingMethod):

    def __init__(self, method: str):
        super().__init__(method)
        self.valid = True
        self.from_top = False if self._mod.lower() == 'bottom' else True
        self.layer_index_start = int(self._vals[0]) if self._vals is not None else 1

    def to_qgis(self) -> QgsMeshMultiLevelsAveragingMethod:
        return QgsMeshMultiLevelsAveragingMethod(self.layer_index_start, self.from_top)


class MultiLevel(SingleLevel):

    def __init__(self, method: str):
        super().__init__(method)
        if len(self._vals) < 2:
            raise ValueError(f'{self.__class__.__name__} averaging method must have two values')
        self.layer_index_end = int(self._vals[1]) if self._vals is not None else 1

    def to_qgis(self) -> QgsMeshMultiLevelsAveragingMethod:
        return QgsMeshMultiLevelsAveragingMethod(self.layer_index_start, self.layer_index_end, self.from_top)


class HeightAveragingMethod(AveragingMethod):

    def __init__(self, method: str):
        super().__init__(method)
        self.valid = True
        if len(self._vals) < 2:
            raise ValueError(f'{self.__class__.__name__} averaging method must have two values')
        self.start = float(self._vals[0]) if self._vals[0] is not None else 0.
        self.end = float(self._vals[1]) if self._vals[1] is not None else 100.


class Depth(HeightAveragingMethod):

    def __init__(self, method: str):
        super().__init__(method)
        self.from_top = True

    def to_qgis(self) -> QgsMeshRelativeHeightAveragingMethod:
        return QgsMeshRelativeHeightAveragingMethod(self.start, self.end, self.from_top)


class Height(Depth):

    def __init__(self, method: str):
        super().__init__(method)
        self.from_top = False


class Elevation(HeightAveragingMethod):

    def to_qgis(self) -> QgsMeshElevationAveragingMethod:
        return QgsMeshElevationAveragingMethod(self.start, self.end)


class Sigma(HeightAveragingMethod):

    def __init__(self, method: str):
        super().__init__(method)
        if self._vals[1] is None:
            self.end = 1.0

    def to_qgis(self):
        return QgsMeshSigmaAveragingMethod(self.start, self.end)
