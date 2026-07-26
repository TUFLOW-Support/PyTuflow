FACTORY_DEFAULTS = {
    "iter": "001",
    "gis_format": "SHP",
    "hardware": "GPU"
}

FACTORY_HPC_DEFAULTS = {
    "cell_size": "<cell size>  ! TODO populate with appropriate value",
    "output_formats": {
        "XMDF": {
            "data_types": ["h", "v", "d", "q"],
            "interval": 3600
        },
        "TIF": {
            "data_types": ["h", "v", "d"],
            "interval": 0
        }
    },
    "engine": "HPC",
    "model_domain_origin": "0, 0",
    "model_domain_angle": "0",
    "model_domain_size": "<X, Y>  ! TODO",
}

FACTORY_FV_DEFAULTS = {
    "spherical": "0",
    "latitude": "0.0",
}
