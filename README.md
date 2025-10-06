# PyTuflow

![](docs/assets/TUFLOW.png)

**PyTUFLOW** is a library that acts as an API for your TUFLOW model. It allows easy interaction with the model results,
contains a number of useful utilities for building TUFLOW models, and contains some useful parsers for files within the
TUFLOW eco-system.

## Documentation

The documentation for PyTUFLOW can be found at: https://docs.tuflow.com/pytuflow/

## Installation

You can install PyTUFLOW using pip.

```bash
pip install pytuflow
```

## Dependencies

Most dependencies are automatically installed when you install pytuflow. There are a few additional dependencies
that are not automatically installed, but are very useful as they will extend the functionality of pytuflow. These
are:

- **netCDF4**: This is required for reading any netCDF files, for example, the ``NC`` time-series output format, or
  the ``NC`` map output format. It also allows for reading of the ``XMDF`` header information.
- **GDAL**: This is required for reading GIS files, which extends the :class:`GisInput<pytuflow.GisInput>` class and
  allows the use of GIS files as locations to extract data from map outputs.
- **shapely**: Needed for extracting section data from map output formats.
- **QGIS**: Currently QGIS is required for extracting data from `XMDF`, `NCMesh`,
  and `CATCHJson` output formats. We hope to remove this dependency in the future,
  but for now, it is required for these particular output formats. It isn't required for using ``pytuflow`` in general.

One of the trickiest libraries to install is GDAL. For Windows, you can download pre-compiled binaries from
here: https://github.com/cgohlke/geospatial-wheels/releases.

For QGIS, there are some broad instructions on how to set up a [QGIS environment](https://docs.tuflow.com/pytuflow/examples/working_with_tuflow_outputs/#qgis-environment) in the output examples.

## Quickstart

The best place to get started is the [Load and Run a TUFLOW Model](https://docs.tuflow.com/pytuflow/examples/tcf_load_and_run/) example, or to browse through the other
[Examples](https://docs.tuflow.com/pytuflow/examples/).

## Development

The code base can be cloned from GitHub:

```bash
git clone https://github.com/TUFLOW-Support/PyTuflow.git --recurse-submodules
```

Dependencies can be installed using the `requirements-dev.txt` file:

```bash
pip install -r requirements-dev.txt
```

GDAL python bindings will also need to be installed separately. Version 3.8 or later is preferred.

### Building the Docs

To build the documentation, navigate to the `docs` folder and run:

```bash
# from the pytuflow project root directory
cd docs
.\make.bat dirhtml
```

To serve the documentation locally, you can use (on Windows):

```bash
.\serve.ps1
```

### Running Tests

PyTUFLOW uses `unittest` and `pytest` for testing depending on which module is being tested.

To run tests for the `time series` output classes:

```bash
# from the pytuflow project root directory
python -m unittest tests.test_time_series
```

To run tests for the `map output` classes, you will need to run within a QGIS Python environment:

```bash
# from the pytuflow project root directory
python -m unittest tests.test_map_output
```

To run the `tmf` tests on Windows:

```bash
# from the pytuflow project root directory
cd pytuflow/_tmf
pytest tests/unit_tests/
```

To run the `fm_to_estry` unit tests:

```bash
# from the pytuflow project root directory
cd pytuflow/_fm_to_estry
python -m unittest discover -s tests/unit_tests
```

To run the `fm_to_estry` integration tests:

```bash
# from the pytuflow project root directory
cd pytuflow/_fm_to_estry
python -m unittest discover -s tests/integration_tests
```

### Building the Package

```bash
# from the pytuflow project root directory
python -m build --wheel
```

## LICENCE

MIT LICENCE (see `LICENSE` file for details).
