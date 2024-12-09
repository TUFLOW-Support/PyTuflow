import numpy as np


class TemporalProp:

    def __init__(self, start, end, dt):
        self.start = start
        self.end = end
        self.dt = dt

    def __eq__(self, other):
        return np.isclose([self.start, self.end, self.dt], [other.start, other.end, other.dt], rtol=0., atol=0.0001).all()
