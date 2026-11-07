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

Scope and Limitations
---------------------

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

This is an input-existence preflight, not a model execution or a guarantee
of raster-content validity, hydraulic correctness or solver compatibility.
