"""Runtime smoke for the *installed* PyTUFLOW wheel, run outside its checkout.

Requires the ordinary PyTUFLOW runtime dependencies in the chosen environment.
Creates only a temporary TCF; it does not launch a solver or inspect user data.
"""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path
from tempfile import TemporaryDirectory

import pytuflow
from pytuflow import TCF
from pytuflow.batch_validation import validate_batch_inputs
from pytuflow.validation import ValidationOptions


def main() -> None:
    package_path = Path(pytuflow.__file__).resolve()
    environment = Path(sys.prefix).resolve()
    if not package_path.is_relative_to(environment):
        raise AssertionError(
            f"PyTUFLOW imported from {package_path}, outside {environment}"
        )

    installed = metadata.distribution("pytuflow")
    if installed.version != pytuflow.__version__:
        raise AssertionError(f"Installed version {installed.version} does not match imported package {pytuflow.__version__}")
    marker = Path(installed.locate_file("pytuflow/py.typed"))
    if not marker.is_file():
        raise AssertionError(f"Missing installed PEP 561 marker: {marker}")

    with TemporaryDirectory() as directory:
        model_file = Path(directory) / "model.tcf"
        model_file.write_text("Output Folder == output\n", encoding="utf-8")
        model = TCF(model_file, case_sensitivity=0)
        result = validate_batch_inputs(
            model,
            [{"s1": "Existing", "e1": "Q10"}],
            options=ValidationOptions(
                case_sensitivity=0,
                check_raster_metadata=False,
                check_crs=False,
            ),
        )
        if not result.passed or result.issues or result.validation.run_count != 1:
            raise AssertionError(
                f"Installed public validation smoke failed: {result.issues!r}"
            )

    print(f"Installed PyTUFLOW {installed.version}: {package_path}")
    print("PEP 561 marker and public validator smoke passed")


if __name__ == "__main__":
    main()
