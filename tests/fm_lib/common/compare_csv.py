from pathlib import Path

import numpy as np
import pandas as pd


def compare_csv(csv1: Path, csv2: Path):
    with csv1.open() as f1:
        with csv2.open() as f2:
            # header
            for _ in range(2):
                h1 = f1.readline()
                h2 = f2.readline()
                assert h1 == h2, f'compare_csv(csv1, csv2): {csv1} header does not equal {csv2} header:\ncsv1: {h1.strip()}\ncsv2: {h2.strip()}'
            # values
            df1 = pd.read_csv(f1, header=None)
            df2 = pd.read_csv(f2, header=None)
            assert df1.shape == df2.shape, f'compare_csv(csv1, csv2): {csv1} shape does not equal {csv2} shape:\ncsv1: {df1.shape}\ncsv2: {df2.shape}'
            assert np.allclose(df1, df2, equal_nan=True), f'compare_csv(csv1, csv2): {csv1} content differs from {csv2}'
