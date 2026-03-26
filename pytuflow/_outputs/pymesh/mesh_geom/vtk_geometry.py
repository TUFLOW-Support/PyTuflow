import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd


class VTKGeometryMixin:

    @staticmethod
    def _flatten_cells(df: pd.DataFrame) -> np.ndarray:
        """Flatten rows of a DataFrame with columns ['nnode','n1','n2','n3','n4']
        into a single 1-D numpy array. For rows where n4 == -1 (triangles),
        only nnode,n1,n2,n3 are included (length 4); for quads include n4 (length 5).
        """
        arr = df[['nnode', 'n1', 'n2', 'n3', 'n4']].to_numpy()
        # length per row: 4 for triangles (n4 == -1) else 5
        lengths = np.where(arr[:, 4] == -1, 4, 5)
        offsets = np.concatenate(([0], np.cumsum(lengths)[:-1]))
        total = lengths.sum()
        out = np.empty(total, dtype=arr.dtype)

        # assign first 4 fields for all rows (nnode, n1, n2, n3)
        for pos in range(4):
            out[offsets + pos] = arr[:, pos]

        # assign n4 only for quads
        quad_mask = arr[:, 4] != -1
        out[offsets[quad_mask] + 4] = arr[quad_mask, 4]

        return out
