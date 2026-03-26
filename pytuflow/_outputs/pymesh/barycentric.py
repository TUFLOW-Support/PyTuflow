import numpy as np


def barycentric_coord(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> tuple[float, float, float]:
    v0 = b - a
    v1 = c - a
    v2 = p - a
    if len(p.shape) == 1:
        den = 1 / (v0[0] * v1[1] - v1[0] * v0[1])
        v = (v2[0] * v1[1] - v1[0] * v2[1]) * den
        w = (v0[0] * v2[1] - v2[0] * v0[1]) * den
    else:
        den = 1 / (v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1])
        v = (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) * den
        w = (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) * den
    u = 1.0 - v - w
    return u, v, w
