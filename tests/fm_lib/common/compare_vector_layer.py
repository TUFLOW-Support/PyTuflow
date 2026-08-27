import numpy as np

from .gis import vector_geom_as_array, vector_attributes, VectorLayer


def compare_vector_layer(layer1: str, layer2: str):
    with VectorLayer(layer1) as v1:
        with VectorLayer(layer2) as v2:
            # crs

            # geometry
            ageom1 = vector_geom_as_array(v1.lyr)
            ageom2 = vector_geom_as_array(v2.lyr)
            assert ageom1.shape == ageom2.shape, f'compare_vector_layer(layer1, layer2): geometry array shape mis-match\nlayer1: {ageom1.shape}\nlayer2: {ageom2.shape}'
            assert np.allclose(ageom1, ageom2, equal_nan=True), f'compare_vector_layer(layer1, layer2): geometry array differences'

            # attributes
            attr1 = vector_attributes(v1.lyr)
            attr2 = vector_attributes(v2.lyr)
            assert attr1 == attr2, f'compare_vector_layer({layer1}, {layer2}): attributes do not match'
