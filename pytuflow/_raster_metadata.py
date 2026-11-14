"""Bounded read-only raster headers and optional CRS metadata.

Selected sources are checked only after ordinary file inspection. No pixels,
statistics, overviews, writable handles or persistent file caches are used.
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Collection
from pathlib import Path
from threading import Lock
from typing import Any, Literal, Protocol


class _RasterShape(Protocol):
    """The public Rasterio metadata surface used by this checker."""

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...

    @property
    def count(self) -> int: ...


RasterHeaderStatus = Literal["present", "unresolved", "unsupported"]
RasterHeaderOutcome = tuple[RasterHeaderStatus, str]
_NETCDF_SUFFIXES = frozenset({".nc", ".nc4", ".cdf"})
_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]*\Z")

# On Python 3.11-3.13, warnings.catch_warnings changes process-global filters.
# Coordinate every Rasterio open so a non-NetCDF worker cannot inherit another
# worker's temporary NetCDF filter. Metadata access and handle closure stay parallel.
_RASTER_OPEN_LOCK = Lock()


def inspect_raster_headers(
    path: Path,
    selectors: Collection[str | None],
    *,
    maximum_subdatasets: int,
    include_crs: bool = False,
) -> (
    tuple[dict[str | None, RasterHeaderOutcome], int]
    | tuple[dict[str | None, RasterHeaderOutcome], int, dict[str | None, str | None]]
):
    """Read one raster header and any selected NetCDF variable headers once.

    An explicit NetCDF selector must match the actual advertised variable,
    exactly and case-sensitively. An unselected NetCDF container with no
    usable root bands passes if any advertised subdataset is usable; this
    does not certify a particular unnamed rainfall variable.

    The ordinary two-value return is retained. With include_crs=True, the
    third value maps each *usable selected* raster to its CRS WKT or None.
    CRS access happens inside the same read-only dataset handle.
    """
    import rasterio
    from rasterio.errors import NotGeoreferencedWarning, RasterioError

    requested = set(selectors)
    if not requested or maximum_subdatasets < 1:
        raise ValueError("Raster requests and maximum_subdatasets must be positive")
    results: dict[str | None, RasterHeaderOutcome] = {}
    crs_values: dict[str | None, str | None] = {}
    subdataset_opens = 0
    is_netcdf = path.suffix.casefold() in _NETCDF_SUFFIXES
    errors = (OSError, RasterioError, RuntimeError, TypeError, ValueError)

    def usable(dataset: _RasterShape) -> bool:
        return dataset.width > 0 and dataset.height > 0 and dataset.count > 0

    def dataset_crs(dataset: object) -> str | None:
        if not include_crs:
            return None
        try:
            value = getattr(dataset, "crs", None)
            return value.to_wkt() if value is not None else None
        except errors:
            return None

    def finished() -> tuple[dict[str | None, RasterHeaderOutcome], int] | tuple[
        dict[str | None, RasterHeaderOutcome], int, dict[str | None, str | None]
    ]:
        if include_crs:
            return results, subdataset_opens, crs_values
        return results, subdataset_opens

    # A bandless NetCDF container can be a valid home for selected grid
    # subdatasets without having its own geotransform. Under warnings-as-errors,
    # Rasterio raises NotGeoreferencedWarning before those subdatasets can be
    # checked. Only suppress this *specific* expected warning for NetCDF; CRS
    # absence is reported separately by the public CRS validation stage.
    def open_dataset(name: str | Path) -> Any:
        """Limit the temporary filter to the open, including mixed-format workers."""
        with _RASTER_OPEN_LOCK:
            if not is_netcdf:
                return rasterio.open(name, mode="r")
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=(
                        r"^Dataset has no geotransform, gcps, or rpcs\. "
                        r"The identity matrix will be returned\.$"
                    ),
                    category=NotGeoreferencedWarning,
                )
                return rasterio.open(name, mode="r")

    # Prevent GDAL PAM metadata from generating an auxiliary sidecar.
    with rasterio.Env(GDAL_PAM_ENABLED="NO"):
        try:
            with open_dataset(path) as root:
                root_usable = usable(root)
                root_crs = dataset_crs(root) if root_usable else None
                subdatasets = (
                    tuple(root.subdatasets)
                    if is_netcdf and (
                        not root_usable or any(selector is not None for selector in requested)
                    )
                    else ()
                )
        except errors as exc:
            for selector in requested:
                results[selector] = ("unresolved", f"Cannot inspect raster header: {exc}")
            return finished()

        if not is_netcdf:
            for selector in requested:
                if selector is not None:
                    results[selector] = (
                        "unsupported",
                        "Raster variable selectors are supported only for NetCDF inputs",
                    )
                elif root_usable:
                    results[selector] = ("present", "")
                    crs_values[selector] = root_crs
                else:
                    results[selector] = (
                        "unresolved", "Raster has no usable dimensions or bands"
                    )
            return finished()

        if len(subdatasets) > maximum_subdatasets:
            for selector in requested:
                if selector is None and root_usable:
                    results[selector] = ("present", "")
                    crs_values[selector] = root_crs
                else:
                    results[selector] = (
                        "unsupported",
                        f"NetCDF advertises {len(subdatasets)} subdatasets, "
                        f"exceeding the limit of {maximum_subdatasets}",
                    )
            return finished()

        opened: dict[str, RasterHeaderOutcome] = {}
        sub_crs: dict[str, str | None] = {}

        def inspect_subdataset(name: str) -> RasterHeaderOutcome:
            nonlocal subdataset_opens
            if name not in opened:
                subdataset_opens += 1
                try:
                    with open_dataset(name) as dataset:
                        valid = usable(dataset)
                        opened[name] = (
                            ("present", "") if valid
                            else ("unresolved", "NetCDF subdataset has no usable dimensions or bands")
                        )
                        if valid:
                            sub_crs[name] = dataset_crs(dataset)
                except errors as exc:
                    opened[name] = (
                        "unresolved", f"Cannot inspect NetCDF subdataset: {exc}"
                    )
            return opened[name]

        for selector in sorted(s for s in requested if s is not None):
            if _VARIABLE.fullmatch(selector) is None:
                results[selector] = (
                    "unsupported", f"Unsupported NetCDF variable selector: {selector!r}"
                )
                continue
            matches = tuple(
                name for name in subdatasets
                if name.rsplit(":", maxsplit=1)[-1] == selector
            )
            if not matches and not subdatasets and root_usable:
                # GDAL exposes a single-variable NetCDF directly as root bands.
                # Open the explicitly named variable, rather than certifying
                # unrelated root bands or assuming a missing selector exists.
                matches = (f'NETCDF:"{path}":{selector}',)
            if len(matches) != 1:
                results[selector] = (
                    "unresolved",
                    f"Expected exactly one NetCDF subdataset for "
                    f"{selector!r}; found {len(matches)}",
                )
                continue
            results[selector] = inspect_subdataset(matches[0])
            if results[selector][0] == "present":
                crs_values[selector] = sub_crs.get(matches[0])

        if None in requested:
            if root_usable:
                results[None] = ("present", "")
                crs_values[None] = root_crs
            elif not subdatasets:
                results[None] = (
                    "unresolved",
                    "NetCDF container has no usable raster bands or subdatasets",
                )
            else:
                first_problem = ""
                for name in subdatasets:
                    status, detail = inspect_subdataset(name)
                    if status == "present":
                        results[None] = (
                            "present",
                            "NetCDF container has a usable raster subdataset; "
                            "no particular variable was selected or certified",
                        )
                        crs_values[None] = sub_crs.get(name)
                        break
                    if not first_problem:
                        first_problem = detail
                else:
                    results[None] = (
                        "unresolved",
                        f"No usable NetCDF raster subdataset: {first_problem}",
                    )

    return finished()
