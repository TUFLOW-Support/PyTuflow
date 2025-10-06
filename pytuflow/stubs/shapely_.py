def shapely_(*args, **kwargs):
    raise ImportError('The shapely library needs to be installed to use GridLine functions.')


def distance(*args, **kwargs):
    shapely_(*args, **kwargs)


def intersection(*args, **kwargs):
    shapely_(*args, **kwargs)


class Shapely_:

    def __init__(self, *args, **kwargs):
        raise ImportError('The shapely library needs to be installed to use GridLine functions.')


class Point(Shapely_):
    pass


class LineString(Shapely_):
    pass


class Polygon(Shapely_):
    pass
