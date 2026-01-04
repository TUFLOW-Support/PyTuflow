import numpy as np


def multi_level(levels: list[int] | np.ndarray, zlevels: np.ndarray, values: np.ndarray, from_top: bool) -> np.ndarray:
    levels = np.asarray(levels)

    # force 2D values & zlevels
    if values.ndim == 1:
        values = values.reshape(1, -1)
    if zlevels.ndim == 1:
        zlevels = zlevels.reshape(1, -1)

    N, Z = zlevels.shape
    if levels.ndim == 1:
        levels = levels.reshape(1, -1)
    if levels.shape[1] != 2:
        raise ValueError("levels must contain exactly two values per row (top, bottom)")

    # make elev shape (N,2) to match number of rows if single pair provided
    levels = np.sort(levels, axis=1)
    if levels.shape[0] == 1 and N > 1:
        levels = np.repeat(levels, N, axis=0)

    valid_layers = ~np.isnan(zlevels[:, :-1]) & ~np.isnan(zlevels[:, 1:])
    diff = np.abs(np.diff(zlevels, axis=1))  # layer thickness
    diff[~valid_layers] = 0.0  # layer thickness

    idx1 = np.clip(levels[:, 0] - 1, 0, Z - 1)
    idx2 = np.clip(levels[:, 1] - 1, 0, Z - 1)

    if not from_top:
        diff = np.flip(diff, axis=1)
        values = np.flip(values, axis=1)

    valid = ~np.isnan(values)
    first_idx = np.argmax(valid, axis=1)
    has_valid = valid.any(axis=1)
    range_ = np.arange(Z - 1)
    cols = np.full(values.shape, -1)
    cols[has_valid] = np.where(
        range_ >= first_idx[has_valid, None],
        range_ - first_idx[has_valid, None],
        -1
    )

    # row-slice mask
    slice_mask = (cols >= idx1[:, None]) & (cols <= idx2[:, None])

    weights = diff * slice_mask
    numerator = (weights * np.nan_to_num(values, nan=0.)).sum(axis=1)
    denominator = weights.sum(axis=1)

    result = numerator / denominator

    return result


def single_level(level: int, zlevels: np.ndarray, values: np.ndarray, from_top: bool) -> np.ndarray:
    return multi_level([level, level], zlevels, values, from_top)


def depth(dist: np.ndarray | list[float], zlevels: np.ndarray, values: np.ndarray, from_top: bool) -> np.ndarray:
    """Vectorized depth averaging over specified depth ranges."""
    dist = np.asarray(dist)

    # force 2D values & zlevels
    if values.ndim == 1:
        values = values.reshape(1, -1)
    if zlevels.ndim == 1:
        zlevels = zlevels.reshape(1, -1)

    # ensure dist is (N, 2)
    if dist.size == zlevels.shape[0]:
        dist = np.column_stack((np.zeros(zlevels.shape[0]), dist))
    else:
        dist = dist.reshape(-1, 2)
    if dist.size == 2:
        dist = np.repeat(dist, zlevels.shape[0], axis=0)

    valid_layers = ~np.isnan(zlevels[:, :-1]) & ~np.isnan(zlevels[:, 1:])
    diff = np.abs(np.diff(zlevels, axis=1))
    diff[~valid_layers] = 0.0 # layer thickness

    # flip if measuring from bottom
    if from_top:
        cum_depths = diff.cumsum(axis=1)
    else:
        diff = np.flip(diff, axis=1)
        cum_depths = diff.cumsum(axis=1)
        values = np.flip(values, axis=1)

    # ensure dist sorted & clipped at zero
    dist = np.sort(dist, axis=1)
    dist[:, 0] = np.clip(dist[:, 0], 0, None)

    # total depth
    total_depth = cum_depths[:, -1]

    # rows where start depth exceeds total depth → nan
    invalid = dist[:, 0] > total_depth

    # find idx1
    mask1 = cum_depths >= dist[:, [0]]
    idx1 = np.where(mask1.any(axis=1), mask1.argmax(axis=1), -1)

    # find idx2
    mask2 = cum_depths >= dist[:, [1]]
    idx2 = np.where(mask2.any(axis=1), mask2.argmax(axis=1), values.shape[1] - 1)

    # build mask for row slices
    rows = np.arange(cum_depths.shape[0])
    cols = np.arange(cum_depths.shape[1])

    # adjust fractional thickness at slice boundaries
    diff = diff.copy()
    valid = idx1 != -1

    # adjust first cell thickness
    diff[rows[valid], idx1[valid]] = cum_depths[rows[valid], idx1[valid]] - dist[valid, 0]

    # adjust last cell thickness
    last_full = np.maximum(idx2 - 1, 0)
    diff[rows[valid], idx2[valid]] = np.minimum(
        dist[valid, 1] - cum_depths[rows[valid], last_full[valid]],
        diff[rows[valid], idx2[valid]]
    )

    # row-slice mask
    slice_mask = (cols[None, :] >= idx1[:, None]) & (cols[None, :] <= idx2[:, None])

    weights = diff * slice_mask
    numerator = (weights * np.nan_to_num(values, nan=0.)).sum(axis=1)
    denominator = weights.sum(axis=1)

    result = numerator / denominator

    # apply invalid values
    result[invalid] = np.nan

    return result


def elevation(elev: list[float], zlevels: np.ndarray, values: np.ndarray) -> np.ndarray:
    elev = np.asarray(elev)
    zlevels = np.asarray(zlevels)
    values = np.asarray(values)

    # ensure 2D profile arrays
    if zlevels.ndim == 1:
        zlevels = zlevels.reshape(1, -1)
    if values.ndim == 1:
        values = values.reshape(1, -1)

    N, Z = zlevels.shape
    if elev.ndim == 1:
        elev = elev.reshape(1, -1)
    if elev.shape[1] != 2:
        raise ValueError("elev must contain exactly two values per row (top, bottom)")

    # make elev shape (N,2) to match number of rows if single pair provided
    if elev.shape[0] == 1 and N > 1:
        elev = np.repeat(elev, N, axis=0)

    # sort each row high->low (surface -> deeper)
    elev = np.sort(elev, axis=1)[:, ::-1]
    e_top = elev[:, 0]
    e_bot = elev[:, 1]

    # layer tops and bottoms (Z-1 layers)
    layer_top = zlevels[:, :-1]  # shape (N, Z-1)
    layer_bottom = zlevels[:, 1:]  # shape (N, Z-1)

    # positive thickness of each layer (assuming zlevels is decreasing)
    valid_layers = ~np.isnan(zlevels[:, :-1]) & ~np.isnan(zlevels[:, 1:])
    diff = (layer_top - layer_bottom)  # shape (N, Z-1)
    diff[~valid_layers] = 0.0  # layer thickness

    # prepare output
    result = np.full(N, np.nan)

    # quick invalid checks: requested range entirely above surface or below bed
    too_high = e_bot > zlevels[:, 0]  # lowest requested elev above surface
    too_low = e_top < zlevels[:, -1]  # highest requested elev below bed
    valid_domain = ~(too_high | too_low)

    if not np.any(valid_domain):
        return result

    # find idx1: first layer where e_top falls into/above layer_bottom
    mask1 = e_top[:, None] >= layer_bottom
    idx1 = np.where(mask1.any(axis=1), mask1.argmax(axis=1), -1)  # -1 means above all layers

    # find idx2: first layer where e_bot falls into/above layer_bottom
    mask2 = e_bot[:, None] >= layer_bottom
    idx2 = np.where(mask2.any(axis=1), mask2.argmax(axis=1), (Z - 2))  # default bottom-most layer index

    # ensure idx2 >= idx1
    idx2 = np.maximum(idx1, idx2)

    rows = np.arange(N)
    cols = np.arange(Z - 1)  # layer indices

    # boolean include mask for whole layers (including boundaries)
    include = (cols[None, :] >= idx1[:, None]) & (cols[None, :] <= idx2[:, None])

    # Only rows that actually have a starting layer (idx1 >= 0) are adjusted
    start_valid = idx1 >= 0
    if np.any(start_valid):
        r = rows[start_valid]
        c = idx1[start_valid]
        # thickness of upper partial layer
        diff[r, c] = np.minimum(e_top[start_valid] - layer_bottom[r, c], diff[r, c])

    # For lower boundary: only rows with a valid include and idx2 >= 0
    end_valid = (idx2 >= 0) & valid_domain
    if np.any(end_valid):
        r = rows[end_valid]
        c = idx2[end_valid]
        # thickness of lower partial layer
        partial = layer_top[r, c] - e_bot[end_valid]
        # ensure we don't exceed the full layer thickness
        diff[r, c] = np.minimum(partial, diff[r, c])

    # guard against tiny negative numeric values
    diff_adj = np.maximum(diff, 0.0)
    diff_adj[~valid_layers] = 0.0

    weights = diff_adj * include
    numerator = (weights * np.nan_to_num(values, nan=0.)).sum(axis=1)
    denominator = weights.sum(axis=1)

    ok = (denominator > 0) & valid_domain
    result[ok] = numerator[ok] / denominator[ok]

    return result

def sigma(fracs: list[float], zlevels: np.ndarray, values: np.ndarray) -> np.ndarray:
    if zlevels.ndim == 1:
        zlevels = zlevels.reshape(1, -1)
    fracs = np.array(fracs).reshape(-1, 2)
    column_depth = np.nanmax(zlevels, axis=1) - np.nanmin(zlevels, axis=1)
    depths = column_depth.reshape(-1, 1) * fracs
    return depth(depths, zlevels, values, from_top=False)
