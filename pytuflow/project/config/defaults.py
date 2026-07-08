FACTORY_DEFAULTS = {
    "iter": "001",
    "gis_format": "SHP",
    "gis_projection_command": "! Projection == <path/to/projection>  ! TODO",
    "hardware": "GPU"
}

FACTORY_HPC_DEFAULTS = {
    "cell_size": "<cell size>  ! TODO populate with appropriate value",
    "map_output_formats": ["XMDF"],
    "engine": "HPC",
    "model_domain_origin": "0, 0",
    "model_domain_angle": "0",
    "model_domain_size": "<X, Y>  ! TODO",
}
