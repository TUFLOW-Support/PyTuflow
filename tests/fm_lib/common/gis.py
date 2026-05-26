from pathlib import Path

import math
import numpy as np
import geopandas as gpd
import pyogrio


def vector_geom_as_array(lyr: gpd.GeoDataFrame) -> np.ndarray:
    """Return geometry coordinates as a (n_features, max_npoints, 2) numpy array."""
    feats = []
    max_npoints = 0
    for geom in lyr.geometry:
        if geom is None:
            pts = []
        else:
            pts = list(geom.coords) if hasattr(geom, 'coords') else []
        max_npoints = max(len(pts), max_npoints)
        feats.append(pts)

    for i, pts in enumerate(feats):
        if len(pts) < max_npoints:
            feats[i] = list(pts) + [(np.nan, np.nan)] * (max_npoints - len(pts))

    return np.array(feats)


def vector_attributes(lyr: gpd.GeoDataFrame) -> list:
    """Return feature attributes as a list of lists, with floats rounded to 3 d.p."""
    result = []
    attr_cols = [c for c in lyr.columns if c != 'geometry']
    for _, row in lyr.iterrows():
        row_vals = []
        for col in attr_cols:
            val = row[col]
            if isinstance(val, float):
                # Normalize NaN to 0.0 to match OGR GetFieldAsDouble behaviour for NULL fields
                row_vals.append(0.0 if math.isnan(val) else round(val, 3))
            elif val is None or (hasattr(val, '__class__') and val.__class__.__name__ in ('NAType', 'NaTType')):
                row_vals.append('')
            else:
                row_vals.append(str(val) if not isinstance(val, str) else val)
        result.append(row_vals)
    return result


class VectorLayer:
    """Context manager for reading a vector layer using geopandas/pyogrio."""

    def __init__(self, fpath) -> None:
        self.fpath = str(fpath)
        self.lyrname = None
        if ' >> ' in self.fpath:
            self.dbpath, self.lyrname = self.fpath.split(' >> ', 1)
        else:
            self.dbpath = self.fpath
        self.lyr: gpd.GeoDataFrame = None

    def __repr__(self) -> str:
        return f'VectorLayer(fpath={self.fpath})'

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self):
        if self.lyrname is None:
            return
        self.lyr = gpd.read_file(self.dbpath, layer=self.lyrname)

    def close(self):
        self.lyr = None

    def layers(self):
        for name, _ in pyogrio.list_layers(self.dbpath):
            yield name
