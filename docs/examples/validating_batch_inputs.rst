.. _validating_batch_inputs:

Validating Inputs for Multiple TUFLOW Runs
=========================================

Use :func:`pytuflow.batch_validation.validate_batch_inputs` to check the
input files referenced by several scenario and event combinations before
running TUFLOW. The function does not execute TUFLOW or modify the model.

.. code-block:: python

    from pytuflow.batch_validation import validate_batch_inputs

    run_flags = [
        "-s1 Existing -e1 Q10",
        "-s1 Proposed -e1 Q100",
    ]

    report = validate_batch_inputs("runs/model.tcf", run_flags)

    if not report.passed:
        for issue in report.issues:
            print(
                issue.run_index,
                issue.status,
                issue.kind,
                issue.path,
                issue.layer,
                issue.detail,
            )

Pass the actual simulation flags you intend to use. The validator does not
generate scenario/event combinations or determine whether they should be run.
``run_index`` is the zero-based position of the corresponding entry in
``run_flags``.

Using a Parsed Model
--------------------

When an application has already loaded the model, pass its
:class:`~pytuflow.TCF` instance to avoid reopening its control files:

.. code-block:: python

    from pytuflow import TCF
    from pytuflow.batch_validation import validate_batch_inputs

    model = TCF("runs/model.tcf")
    report = validate_batch_inputs(model, ["-s1 Existing -e1 Q10"])

The result's ``dependencies`` attribute contains immutable per-run
reference records, including the original command and source-file ownership.
``validation`` holds the physical inspection report. The ``issues``
property contains only missing, unsupported or unresolved findings.

Collecting References Without Physical Inspection
-------------------------------------------------

To inspect which file paths a run refers to without checking that the files
or GIS layers exist, use the separate collection method:

.. code-block:: python

    runs = model.collect_file_dependencies(["-s1 Existing -e1 Q10"])

    for run in runs.runs:
        if run.error:
            print(run.flags, run.error)
            continue
        for reference in run.file_references:
            print(reference.path_pattern, reference.layer_pattern)

The initial ``TCF`` load parses control files and may read input databases.
After that parsing, ``collect_file_dependencies()`` collects syntactic
references using the parsed model; it does not physically inspect source
files or GIS attributes. Physical checks are performed only when explicitly
requested through ``validate_batch_inputs()`` or
:func:`pytuflow.validation.validate_dependencies`.

Inspection Options
------------------

The default batch validator checks input files, selected GeoPackage layers,
ordinary boundary-condition CSV columns and recognised GIS attribute-linked
source files. Set optional inspection limits when necessary:

.. code-block:: python

    from pytuflow.validation import ValidationOptions

    options = ValidationOptions(
        check_files=True,
        check_gpkg_layers=True,
        check_bc_csv_headers=True,
        io_workers=4,
        maximum_directory_entries=50_000,
    )
    report = validate_batch_inputs(model, run_flags, options=options)

Filename case matching follows the case policy used to load the TCF. When
explicitly provided, an inspection policy cannot conflict with the loaded
model's case setting.

Optional raster-header validation
---------------------------------

Raster header and CRS checks are **on by default**. Their switches are
independent: turning off raster header checks while leaving CRS on still
opens a raster to read its CRS. Disable both to avoid these metadata opens.
Use the same options type for direct and batch physical validation:

.. code-block:: python

    from pytuflow.validation import ValidationOptions, validate_dependencies

    options = ValidationOptions(
        check_raster_metadata=True,  # Default.
        check_crs=True,              # Default.
        maximum_raster_subdatasets=64,
    )
    report = validate_batch_inputs(model, run_flags, options=options)

    # Alternatively, inspect a dependency projection directly.
    dependencies = model.collect_file_dependencies(run_flags)
    direct_report = validate_dependencies(
        dependencies, options=options, model=model,
    )

    for warning in report.warnings:
        print(warning.run_index, warning.path, warning.layer, warning.detail)

    for issue in report.issues:
        print(issue.run_index, issue.kind, issue.path, issue.detail)

    for issue in report.issues:
        if issue.kind == "raster_metadata":
            print(issue.run_index, issue.path, issue.layer, issue.detail)

    print(report.validation.raster_sources_examined)
    print(report.validation.raster_subdatasets_opened)

The batch validator first checks primary files and GIS layers to discover
attribute-linked sources, then checks raster headers, CSV selectors and CRS
metadata **only in its final physical pass**. A short-lived invocation cache
reuses primary file-status, wildcard/case-resolution and selected GeoPackage
layer findings in the final pass. Newly discovered files and new metadata
requests are still inspected. The cache is discarded on return; a subsequent
validation rechecks edited sources. File and directory counters describe
deduplicated inspection work across both physical passes.

Each existing raster path is opened once per call, even when shared by many
runs or commands. One header finding is retained for each affected source
declaration and run. Missing files keep their ordinary ``missing`` file
finding; no raster open or duplicate header failure is added. Failed run
contexts and unresolved wildcards are not inspected. ``raster_sources_examined`` counts unique source
root-open attempts after the ordinary file check; the separate
``raster_subdatasets_opened`` counts additional NetCDF subdataset open attempts.
The separate ``crs_sources_examined`` counter counts unique existing spatial
paths inspected for CRS metadata. Counts are per invocation; no cache is
retained between validations.

Supported raster inputs are selected primarily by TUFLOW parser command roles,
including grid portions of mixed raster/vector commands and the grids selected
by ``Read Grid RF`` CSV indexes. Recognised raster suffixes in supported GIS
attribute-linked file references are also checked; unknown or extensionless
linked grid formats remain file-existence checks only. Rasterio/GDAL drivers
must support the format. Common supported header formats include GeoTIFF
(``.tif``, ``.tiff``), ESRI ASCII Grid (``.asc``), ESRI floating grids
(``.flt`` with its ``.hdr``), ERDAS IMG (``.img``), GDAL VRT (``.vrt``) and
NetCDF (``.nc``, ``.nc4``, ``.cdf``). Available driver support depends on the
installed Rasterio/GDAL build. No QGIS runtime or additional dependency is
required. Source files and sidecars are never intentionally modified.

For NetCDF, a root dataset with positive width, height and band count passes.
When the root is only a container, a no-selector check opens advertised
subdatasets until it finds one usable raster (up to the configured limit). A
``present`` finding in this case confirms **container-level** usability only;
it does not certify a particular unnamed rainfall variable. When the parser
provides an explicit ``>> variable`` selection, the checker instead requires
an exact, case-sensitive NetCDF variable match and verifies **that specific**
variable's header. A single-variable container may expose its raster as root
bands without advertising subdatasets; an explicit selector is still opened
by its exact variable name, rather than borrowing unrelated root bands.
This supports parser-resolved ``>> variable`` selectors
and ``NETCDF:\"file.nc\":variable`` paths. An unrelated valid variable cannot satisfy the request.
Missing, ambiguous, unreadable or zero-band selected variables are
``unresolved``. A bandless NetCDF container may legitimately have no root
geotransform; its specific Rasterio ``NotGeoreferencedWarning`` is filtered
during NetCDF header inspection only, so strict Python warning policies do not
abort valid subdataset inspection. Raster opens coordinate access to this
short-lived filter so other raster workers do not inherit it; the filter is
removed before metadata processing or handle closure. Missing CRS metadata is reported through
the separate CRS warning policy. Other raster warnings are not broadly
suppressed. Unsupported variable-selector syntax or an advertised
subdataset count exceeding ``maximum_raster_subdatasets`` (default 64) is
``unsupported``. No arbitrary dataset-level fallback is applied to a named
variable. Only simple GDAL NetCDF variable names are supported, not arbitrary
GDAL virtual filename expressions or more complex variable selectors.

All raster opens use Rasterio in read-only mode, disable GDAL persistent
auxiliary metadata, and close their handles. No pixel reads, statistics or
overviews are performed. Header validity cannot certify pixel-block
readability, CRS suitability, coverage, cell alignment, NoData distribution,
rainfall chronology or numerical/hydraulic correctness.


CRS consistency and warnings
----------------------------

With ``check_crs=True``, input raster and vector CRSs are compared with the
selected TCF ``GIS Projection``, or the selected ``TIF Projection`` if no GIS
projection is available. References follow each run's active scenario/event
commands, not the last projection encountered while initially parsing all
scopes. Projection files reuse the same inspected metadata; ``.prj`` sources
are bounded CRS text reads, not vector-feature reads.
Conflicting TCF GIS and TIF projections warn.

**Independently of these optional CRS checks**, reading a TCF with no GIS
Projection or TIF Projection declaration logs a general warning through the
standard ``pytuflow`` logger. This happens when the TCF configuration is
parsed, once after nested includes and any overrides are considered. It also
happens when ``check_crs=False`` or the validation API is not called. An
explicitly declared but unreadable projection keeps its existing extraction
warning instead of being incorrectly labelled as omitted.

When a selected run has **no active GIS Projection or TIF Projection
declaration**, validation emits one advisory ``crs`` warning for that run
referencing the TCF, **even when all of its spatial input CRSs agree**. The
selected spatial inputs are still compared with the first input having a
usable CRS. This is a comparison baseline, not a guessed TCF projection.
If a projection was declared but is invalid or cannot be resolved, the
existing invalid-projection warning is used instead of duplicating it.
No missing-projection warning is generated when ``check_crs=False``.

With direct ``validate_dependencies()``, the missing-TCF-projection warning
requires either the parsed ``model`` or active command provenance identifying
a TCF run; an anonymous projection alone cannot establish whether a TCF
projection was omitted.

Missing, invalid and different CRS metadata produce ``crs`` findings with
``severity="warning"``. They do not affect ``passed`` and are excluded
from ``BatchValidationResult.issues``. They are returned by
``ValidationReport.warnings`` and ``BatchValidationResult.warnings`` with
the run, owning control file, command and concrete path/layer. Their
physical status remains ``unresolved`` rather than falsely marked present.
With the direct ``validate_dependencies()`` API, pass ``model=model`` to
take its expected CRS from the parsed TCF. Without a model, selected
spatial sources are compared with one another.

Raster CRS is read during the same Rasterio header open. GeoPackage CRS
uses PyTUFLOW's pinned read-only SQLite helper; Shapefile and MapInfo
metadata uses Pyogrio ``read_info()`` without reading features. Pyogrio
is already a required dependency of mandatory GeoPandas, so no new
PyTUFLOW dependency is needed. PROJ compares CRS equivalence, not literal
WKT text. Inline MapInfo ``MI Projection == CoordSys ...``
declarations are normalised with PyTUFLOW's existing ``mi_projection()``
helper before CRS comparison. This requires the native GDAL/OSR Python
bindings for that particular syntax; if those bindings are unavailable,
preflight reports an advisory CRS warning instead of falsely accepting
a reference or failing with an exception. Unsupported/extensionless sources
may have no identifiable raster or vector role and cannot be certified by
these metadata checks.

No grid alignment, resolution suitability, extent, coordinate
transformation, raster pixel data or vector geometry is inspected.
Warm local disk timings do not establish network/cold-storage cost.
To compare costs, benchmark all four combinations of ``check_crs``
and ``check_raster_metadata``. Both default to True pending local
performance acceptance; set both to False for existence-focused checks.

Scope and Limitations
---------------------

Named ``1d_bc`` HT, HQ, QT and QH features select the corresponding active BC
database rows using their third (Name) attribute. Only selected source files and
CSV selectors are inspected; unrelated database rows are not required inputs.
The 1D HQ ``Name=slope=<positive finite number>`` form generates its curve
internally and does not name a database row. A legacy 1D ``T`` Flags value ignores
the feature. Unsupported 1D boundary types, absent Names and malformed slopes
remain unresolved; the 2D BC schema and automatic HQ rules are unchanged.

``Read GIS RF Triangle`` (and its MI/MID/ROWCOL read aliases) supplies rainfall
triangulation geometry. TUFLOW does not use its attributes, so blank Name values
are valid and do not trigger a BC lookup. The required triangle file, companion
files and any selected GeoPackage layer are still checked. Rainfall point
commands retain their ordinary named BC source and CSV/header validation.
These semantics follow `TUFLOW 1D boundaries, Tables 8.3 and 8.4
<https://docs.tuflow.com/classic-hpc/manual/2026.3/07-Boundaries-and-Initial-Conditions.html>`_
and the `official rainfall control examples
<https://wiki.tuflow.com/TUFLOW_Rainfall_Control_File_Examples>`_.

Validation checks the existence of selected input files, GIS layers,
recognised attribute-linked sources and supported CSV column selectors.
It deduplicates physical checks while retaining results for each requested
run and source command. Unsupported GIS schemas or inputs that cannot be
safely resolved are reported rather than accepted. Inline ``Read File``
declarations remain required inputs even if they expand to no commands or
the included TRD is deleted after the model is loaded.

GeoPackages are inspected read-only. Active or uncheckpointed SQLite
journals, unstable aliases and uncertain physical identities cannot be
certified until the source files are stable.

This is an input-existence preflight with an optional raster-header check,
not a model execution or a guarantee of raster-content validity, hydraulic
correctness or solver compatibility.
