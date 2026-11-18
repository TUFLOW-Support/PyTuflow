"""Focused tests for syntax-only TUFLOW input references."""
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import pytest

from pytuflow import TCF
from pytuflow._tmf.file_reference import make_file_reference
from pytuflow._tmf.parsers.command import Command
from pytuflow._tmf.settings import TCFConfig
from pytuflow._tmf.tfpathlib import TuflowPath


def config(tmp_path: Path) -> TCFConfig:
    return TCFConfig(control_file=tmp_path / 'model.tcf', init_from_tcf=False,
                     file_resolution='deferred')


def test_glob_and_layer_patterns_are_immutable(tmp_path):
    with patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')):
        cmd = Command('Read GIS Mat == gis/model_*.gpkg >> 2d_mat_*', config(tmp_path))
        ref = make_file_reference(next(cmd.parts()))
    assert ref.path_pattern.name == 'model_*.gpkg'
    assert ref.layer_pattern == '2d_mat_*'
    assert ref.requires_directory_scan
    assert ref.requires_layer_scan
    with pytest.raises(FrozenInstanceError):
        ref.origin = 'different'


def test_gpkg_all_does_not_open_database(tmp_path):
    with patch.object(Path, 'exists', side_effect=AssertionError('stat')):
        cmd = Command('Read GIS Code == gis/model.gpkg >> all', config(tmp_path))
    assert '>> all' in cmd.value_expanded_path


def test_bc_event_source_is_not_a_file(tmp_path):
    cmd = Command('BC Event Source == ~AEP~ | 05.00p', config(tmp_path))
    assert not cmd.is_value_a_file()


@pytest.mark.parametrize('mode', ['eager', 'deferred', 'batch'])
def test_nested_output_directory_variables_are_not_required_inputs(tmp_path, mode):
    """Destination-only nested placeholders cannot invalidate input projection."""
    tcf = tmp_path / 'model.tcf'
    (tmp_path / 'source.asc').touch()
    (tmp_path / 'model.ecf').write_text('1D Output Folder == ../<<OutputBase>>/<<OutputSuffix>>/1D\n', encoding='utf-8')
    tcf.write_text(
        'Set Variable version == v07\n'
        'ESTRY Control File == model.ecf\n'
        'Set Variable OutputBase == results/<<version>>/<<~s2~>>/<<~e1~>>\n'
        'Set Variable OutputRoot == ../<<OutputBase>>\n'
        '1D Output Folder == <<OutputRoot>>/<<OutputSuffix>>/1D\n'
        'Read Grid Zpts == source.asc\n', encoding='utf-8',
    )
    model = TCF(tcf)
    if mode == 'batch':
        result = model.collect_file_dependencies(('-s1 BASE -s2 EXG -e1 Q100',))
        assert result.passed, [run.error for run in result.runs]
        refs = result.runs[0].file_references
    else:
        run = model.context('-s1 BASE -s2 EXG -e1 Q100', file_resolution=mode)
        refs = tuple(ref for inp in run.find_input() for ref in inp.file_references)
    assert {ref.path_pattern.name for ref in refs} == {'source.asc', 'model.ecf'}


def test_deferred_context_does_not_glob_missing_input(tmp_path):
    fpath = tmp_path / 'model.tcf'
    fpath.write_text('Read GIS Code == gis/missing.shp\n', encoding='utf-8')
    tcf = TCF(fpath)
    with patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')):
        run = tcf.context(file_resolution='deferred')
        refs = [ref for inp in run.inputs for ref in inp.file_references]
    assert refs
    assert refs[0].path_pattern.name == 'missing.shp'
    assert not refs[0].requires_attribute_scan


def test_invalid_mode_rejected(tmp_path):
    fpath = tmp_path / 'model.tcf'
    fpath.write_text('Read GIS Code == gis/missing.shp\n', encoding='utf-8')
    with pytest.raises(ValueError, match='file_resolution'):
        TCF(fpath).context(file_resolution='unknown')


def test_literal_relative_input_reference_from_eager_config(tmp_path):
    from pytuflow._tmf.inp.file import FileInput

    cmd = Command('Read File == subdir/extra.trd',
                  TCFConfig(control_file=tmp_path / 'model.tcf', init_from_tcf=False))
    inp = FileInput(None, cmd, load_control_files=False)
    with patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')):
        ref = inp.file_references[0]
    assert ref.path_pattern == tmp_path / 'subdir' / 'extra.trd'
    assert not ref.requires_directory_scan
    assert not ref.requires_layer_scan


def test_variable_substitution_without_glob(tmp_path):
    cfg = config(tmp_path)
    cfg.variables = {'TEST': 'DEV'}
    with patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')):
        cmd = Command('Read GIS Code == gis/code_<<TEST>>.shp', cfg)
        ref = make_file_reference(next(cmd.parts()))
    assert ref.path_pattern.name == 'code_DEV.shp'
    assert not ref.unresolved_variables


def test_unresolved_variable_is_preserved_in_reference(tmp_path):
    cmd = Command('Read GIS Mat == gis/mat_<<MISSING>>.gpkg >> 2d_mat_*', config(tmp_path))
    ref = make_file_reference(next(cmd.parts()))
    assert ref.unresolved_variables == ('<<MISSING>>',)
    assert ref.layer_pattern == '2d_mat_*'
    assert ref.requires_directory_scan


def test_non_source_commands_excluded(tmp_path):
    from pytuflow._tmf.inp.file import FileInput
    cmd = Command('Write GIS == checks/debug.gpkg', config(tmp_path))
    inp = FileInput(None, cmd, load_control_files=False)
    assert inp.file_references == ()


def test_database_reference_requests_deferred_inspection(tmp_path):
    cmd = Command('BC Database == bc_dbase.csv', config(tmp_path))
    ref = make_file_reference(next(cmd.parts()))
    assert ref.path_pattern.name == 'bc_dbase.csv'
    assert ref.requires_database_scan
    assert not ref.requires_layer_scan


def test_plain_gis_file_does_not_require_attribute_scan(tmp_path):
    cmd = Command('Read GIS Code == gis/2d_code_001.shp', config(tmp_path))
    ref = make_file_reference(next(cmd.parts()))
    assert not ref.requires_attribute_scan
    assert not ref.requires_database_scan


def test_1d_gis_file_marks_attribute_dependencies(tmp_path):
    cmd = Command('Read GIS Network == gis/1d_nwk_001.shp', config(tmp_path))
    ref = make_file_reference(next(cmd.parts()))
    assert ref.requires_attribute_scan


def test_nested_control_file_owns_reference_path(tmp_path):
    from pytuflow._tmf.context import Context
    from pytuflow._tmf.inp.gis import GisInput

    owner = tmp_path / 'model' / 'geometry.tgc'
    cfg = TCFConfig(control_file=tmp_path / 'main.tcf', init_from_tcf=False)
    source = GisInput(None, Command('Read GIS Code == ../gis/2d_code.shp',
                                    cfg, parent=owner), load_control_files=False)
    ctx = Context(config=cfg)
    ctx.file_resolution = 'deferred'
    run = source.context(context=ctx)
    # Preserve lexical '..' rather than dereference a possible junction/symlink.
    assert run.file_references[0].path_pattern == owner.parent / '../gis/2d_code.shp'


def test_context_after_parse_has_no_filesystem_or_gis_io(tmp_path):
    """Deferred contexts cannot enumerate, stat or open model dependencies."""
    fpath = tmp_path / 'model.tcf'
    fpath.write_text(
        'Read GIS Code == gis/code_*.gpkg >> 2d_code_*\n'
        'Read GRID Zpts == grids/missing_*.tif\n'
        'BC Database == bc_dbase.csv\n',
        encoding='utf-8',
    )
    tcf = TCF(fpath)  # Parsing is deliberately excluded from the I/O contract.
    forbidden = AssertionError('deferred context unexpectedly touched filesystem')
    with (
        patch.object(TuflowPath, 'glob', side_effect=forbidden),
        patch.object(Path, 'stat', side_effect=forbidden),
        patch.object(Path, 'open', side_effect=forbidden),
        patch.object(Path, 'resolve', side_effect=forbidden),
        patch('os.scandir', side_effect=forbidden),
        patch('sqlite3.connect', side_effect=forbidden),
        patch.object(TuflowPath, 'open_gis', side_effect=forbidden),
        patch.object(TuflowPath, '_gpkg_layers', side_effect=forbidden),
    ):
        run = tcf.context(file_resolution='deferred')
        # Use the exact recursive traversal consumed by downstream preflight.
        refs = tuple(ref for inp in run.find_input() for ref in inp.file_references)
    assert any(ref.requires_layer_scan for ref in refs)
    assert any(ref.requires_directory_scan for ref in refs)
    assert any(ref.requires_database_scan for ref in refs)


def test_deferred_eager_parity_for_literal_existing_path(tmp_path):
    gis = tmp_path / 'gis'
    gis.mkdir()
    (gis / '2d_code.shp').touch()
    fpath = tmp_path / 'model.tcf'
    fpath.write_text('Read GIS Code == gis/2d_code.shp\n', encoding='utf-8')
    tcf = TCF(fpath)
    eager = tcf.context()
    eager_files = {
        str(path) for inp in eager.inputs for path in inp.files
        if str(path).lower().endswith('.shp')
    }
    deferred = tcf.context(file_resolution='deferred')
    deferred_files = {
        str(ref.path_pattern) for inp in deferred.inputs
        for ref in inp.file_references if ref.path_pattern.suffix.lower() == '.shp'
    }
    assert eager_files == deferred_files


def test_nested_tgc_references_preserve_owning_directory(tmp_path):
    model = tmp_path / 'model'
    geom = tmp_path / 'geom'
    model.mkdir()
    geom.mkdir()
    control = model / 'main.tcf'
    tgc = geom / 'geometry.tgc'
    tgc.write_text('Read GIS Code == ../gis/2d_code.shp\n', encoding='utf-8')
    control.write_text('Geometry Control File == ../geom/geometry.tgc\n', encoding='utf-8')
    tcf = TCF(control)
    run = tcf.context(file_resolution='deferred')
    nested = [
        cf for inp in run.inputs for cf in inp.cf if getattr(cf, 'fpath', None) == tgc
    ]
    assert nested, 'Nested TGC run context was not constructed'
    refs = tuple(ref for cf in nested for inp in cf.inputs for ref in inp.file_references)
    assert any('2d_code.shp' in str(ref.path_pattern) for ref in refs)
    # Preserve '..' in the emitted path; compare only its lexical location.
    import os
    assert all(os.path.normpath(ref.base_directory) == os.path.normpath(geom) for ref in refs)


def test_440_synthetic_scenario_contexts_are_probe_free(tmp_path, capsys):
    """A repeated ensemble remains syntactic after the one-time model parse."""
    import time
    import tracemalloc

    tcf_path = tmp_path / 'ensemble.tcf'
    tcf_path.write_text(
        'IF Scenario == DEV\n'
        '    Read GIS Code == gis/2d_code_DEV.shp\n'
        'ELSE\n'
        '    Read GIS Code == gis/2d_code_EXG.shp\n'
        'END IF\n',
        encoding='utf-8',
    )
    tcf = TCF(tcf_path)
    counts = {'glob': 0}
    def no_glob(*args, **kwargs):
        counts['glob'] += 1
        raise AssertionError('Deferred contexts must not expand globs')
    tracemalloc.start()
    start = time.perf_counter()
    with (
        patch.object(TuflowPath, 'glob', side_effect=no_glob),
        patch.object(Path, 'stat', side_effect=AssertionError('stat')),
    ):
        for i in range(440):
            scenario = 'DEV' if i % 2 else 'EXG'
            run = tcf.context(f'-s1 {scenario}', file_resolution='deferred')
            paths = {
                ref.path_pattern.name for inp in run.inputs for ref in inp.file_references
            }
            assert f'2d_code_{scenario}.shp' in paths
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert counts['glob'] == 0
    print(f'440 deferred synthetic contexts: {elapsed:.3f}s, peak={peak / (1024 * 1024):.1f}MiB')


@pytest.mark.parametrize('scenario', ['DEV', 'EXG'])
def test_scenario_specific_eager_deferred_file_parity(tmp_path, scenario):
    gis = tmp_path / 'gis'
    gis.mkdir()
    for name in ('DEV', 'EXG'):
        (gis / f'2d_code_{name}.shp').touch()
    tcf_path = tmp_path / 'model.tcf'
    tcf_path.write_text(
        'IF Scenario == DEV\n'
        '    Read GIS Code == gis/2d_code_DEV.shp\n'
        'ELSE\n'
        '    Read GIS Code == gis/2d_code_EXG.shp\n'
        'END IF\n',
        encoding='utf-8',
    )
    tcf = TCF(tcf_path)
    eager = tcf.context(f'-s1 {scenario}')
    eager_paths = {
        str(file) for inp in eager.inputs for file in inp.files
        if str(file).endswith('.shp')
    }
    deferred = tcf.context(f'-s1 {scenario}', file_resolution='deferred')
    deferred_paths = {
        str(ref.path_pattern) for inp in deferred.inputs
        for ref in inp.file_references if str(ref.path_pattern).endswith('.shp')
    }
    assert eager_paths == deferred_paths
    assert {Path(file).name for file in deferred_paths} == {f'2d_code_{scenario}.shp'}


def test_wildcard_deferred_pattern_materialises_to_eager_dependencies(tmp_path):
    gis = tmp_path / 'gis'
    gis.mkdir()
    expected = {gis / '2d_code_001.shp', gis / '2d_code_002.shp'}
    for source in expected:
        source.touch()
    tcf_path = tmp_path / 'model.tcf'
    tcf_path.write_text('Read GIS Code == gis/2d_code_*.shp\n', encoding='utf-8')
    tcf = TCF(tcf_path)
    eager_paths = {
        Path(file) for inp in tcf.context().inputs for file in inp.files
        if str(file).endswith('.shp')
    }
    run = tcf.context(file_resolution='deferred')
    patterns = [
        ref.path_pattern for inp in run.inputs for ref in inp.file_references
        if ref.path_pattern.suffix.lower() == '.shp'
    ]
    assert len(patterns) == 1
    assert '*' in patterns[0].name
    resolved = set(patterns[0].parent.glob(patterns[0].name))
    assert eager_paths == resolved == expected


def test_event_command_deferred_reconstruction_preserves_event_name(tmp_path):
    from pytuflow._tmf.context import Context
    from pytuflow._tmf.inp.event import EventInput
    from pytuflow._tmf.parsers.command import EventCommand

    cfg = config(tmp_path)
    command = EventCommand('BC Event Source == ~AEP~ | 05.00p', cfg)
    command.event_name = 'Q100'
    original = EventInput(None, command)
    context = Context(config=cfg)
    context.file_resolution = 'deferred'
    run = original.context(context=context)
    assert run._command.event_name == 'Q100'
    assert run.file_references == ()


@pytest.mark.parametrize('state', ['build', 'eager_run'])
def test_eager_event_file_references_preserve_metadata_without_io(tmp_path, state):
    """File-reference access preserves EventCommand source and event metadata."""
    from pytuflow._tmf.inp.inp_build_state import InputBuildState
    from pytuflow._tmf.parsers.block import DefineBlock
    from pytuflow._tmf.parsers.command import EventCommand

    cfg = TCFConfig(control_file=tmp_path / 'model.tcf', init_from_tcf=False)
    owner = tmp_path / 'events' / 'model.tef'
    command = EventCommand('Read Grid Zpts == terrain.asc', cfg, owner, 0)
    command.event_name = 'Q100'
    command.define_blocks = [DefineBlock('EVENT DEFINE', 'Q100')]
    original = InputBuildState(None, command)
    inp = original if state == 'build' else original.context()
    parts = EventCommand.parts
    observed = []

    def checked_parts(clone):
        observed.append((clone.event_name, clone.parent, clone.part_index, clone.define_blocks))
        yield from parts(clone)

    with (
        patch.object(EventCommand, 'parts', checked_parts),
        patch.object(Path, 'open', side_effect=AssertionError('file opened')),
        patch.object(Path, 'stat', side_effect=AssertionError('stat')),
        patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')),
        patch('sqlite3.connect', side_effect=AssertionError('SQLite')),
    ):
        refs = inp.file_references
    assert len(refs) == 1
    assert refs[0].path_pattern.name == 'terrain.asc'
    assert observed == [('Q100', owner, 0, command.define_blocks)]
    assert command.config.file_resolution == 'eager'
    assert inp._command.config.file_resolution == 'eager'


def test_deferred_gpkg_all_materialises_when_files_requested(tmp_path):
    import sqlite3

    from pytuflow._tmf.inp.gis import GisInput

    gpkg = tmp_path / 'input.gpkg'
    with sqlite3.connect(gpkg) as database:
        database.execute('CREATE TABLE gpkg_contents (table_name TEXT)')
        database.executemany(
            'INSERT INTO gpkg_contents (table_name) VALUES (?)',
            [('2d_code_L',), ('2d_code_P',)],
        )
    cmd = Command('Read GIS Code == input.gpkg >> all', config(tmp_path))
    inp = GisInput(None, cmd, load_control_files=False)
    refs = inp.file_references
    assert len(refs) == 1
    assert refs[0].layer_pattern == 'all'
    files = inp.files
    assert {f.lyrname for f in files} == {'2d_code_L', '2d_code_P'}


@pytest.mark.parametrize(
    ('event', 'expected_source'),
    [('Q100', '100yr_001.csv'), ('QPMF', 'PMFyr_001.csv')],
)
def test_event_file_and_bc_sources_remain_event_specific(tmp_path, event, expected_source):
    """A TEF's BC Event Source is an assignment, not a required file."""
    tcf_path = tmp_path / 'model.tcf'
    tef_path = tmp_path / 'events.tef'
    bc_path = tmp_path / 'bc_dbase.csv'
    tcf_path.write_text(
        'Event File == events.tef\nBC Database == bc_dbase.csv\n', encoding='utf-8',
    )
    tef_path.write_text(
        'Define Event == Q100\n'
        '    BC Event Source == _event_ | 100yr\n'
        'End Define\n'
        'Define Event == QPMF\n'
        '    BC Event Source == _event_ | PMFyr\n'
        'End Define\n',
        encoding='utf-8',
    )
    bc_path.write_text(
        'Name,Source,Column 1,Column 2,Add Col 1,Mult Col 2,Add Col 2,Column 3,Column 4\n'
        'FC01,_event__001.csv,inflow_time_hr,inflow,,,,,\n',
        encoding='utf-8',
    )
    tcf = TCF(tcf_path)
    with patch.object(TuflowPath, 'glob', side_effect=AssertionError('no glob')):
        run = tcf.context(f'-e1 {event}', file_resolution='deferred')
        references = [
            ref for inp in run.find_input() for ref in inp.file_references
        ]
    assert any(ref.path_pattern.name == 'bc_dbase.csv' for ref in references)
    assert not any('BC Event Source' in ref.origin for ref in references)
    # Eager mode still exposes a loaded database; deferred uses cached rows.
    assert tcf.context(f'-e1 {event}').bc_dbase().df.loc['FC01']['Source'] == expected_source
    # This explicit cached-row projection must not touch files or GIS either.
    with (
        patch.object(Path, 'open', side_effect=AssertionError('open')),
        patch.object(Path, 'stat', side_effect=AssertionError('stat')),
        patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')),
        patch('sqlite3.connect', side_effect=AssertionError('SQLite')),
    ):
        sources = run.deferred_database_sources()
    assert len(sources) == 1
    assert sources[0].database_kind == 'bc'
    assert sources[0].entry_name == 'FC01'
    assert sources[0].database_path == bc_path
    assert sources[0].path_pattern == tmp_path / expected_source


    database_inputs = run.find_input(lhs='BC Database')
    assert len(database_inputs) == 1
    secondary = database_inputs[0].database_source_references
    assert {ref.path_pattern.name for ref in secondary} == {expected_source}
    assert all(ref.origin.startswith('bc database row') for ref in secondary)


@pytest.mark.parametrize('mode', ['eager', 'deferred'])
def test_multipart_material_file_materialises_without_treating_multiplier_as_path(tmp_path, mode):
    from pytuflow._tmf.inp.mat import MatDatabaseInput

    material = tmp_path / 'materials.csv'
    material.write_text('Material, Manning\\n1,0.03\\n', encoding='utf-8')
    cfg = config(tmp_path)
    cfg.file_resolution = mode
    command = Command('Read Materials File == materials.csv | 0.8', cfg)
    input_ = MatDatabaseInput(None, command, load_control_files=False)
    assert input_.multiplier == pytest.approx(0.8)
    assert input_.files == [material]
    assert not input_.has_missing_files


def test_deferred_material_database_reports_source_without_rechecking_disk(tmp_path):
    tcf_path = tmp_path / 'model.tcf'
    materials = tmp_path / 'materials.csv'
    tcf_path.write_text('Read Materials File == materials.csv | 0.8\n', encoding='utf-8')
    materials.write_text('Material ID,Manning\'s n\n1,0.03\n', encoding='utf-8')
    model = TCF(tcf_path)
    with (
        patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')),
        patch.object(Path, 'stat', side_effect=AssertionError('stat')),
        patch.object(Path, 'open', side_effect=AssertionError('open')),
    ):
        run = model.context(file_resolution='deferred')
        mat_input = run.find_input(lhs='Read Materials File')[0]
        refs = mat_input.file_references
        secondary = mat_input.database_source_references
    assert len(refs) == 1
    assert refs[0].database_kind == 'materials'
    assert secondary == ()


def test_deferred_material_database_without_secondary_sources(tmp_path):
    """The material CSV is a primary file, not a perpetual unresolved scan."""
    tcf_path = tmp_path / 'model.tcf'
    mat_path = tmp_path / 'materials.csv'
    tcf_path.write_text('Read Materials File == materials.csv | 0.8\n', encoding='utf-8')
    mat_path.write_text(
        "Material ID,Manning's n,Rainfall Losses,Land Use Hazard ID,SRF,Fraction Impervious\n"
        '1,0.03,0,0,0,0\n',
        encoding='utf-8',
    )
    run = TCF(tcf_path).context(file_resolution='deferred')
    assert run.deferred_database_sources() == ()
    assert run.find_input(lhs='Read Materials File')[0].bs.cf[0].loaded


def test_deferred_event_file_under_literal_event_named_parent(tmp_path):
    """An ancestor spelling like '_event_' is not an unresolved TEF variable."""
    parent = tmp_path / 'literal_event_example'
    parent.mkdir()
    tef = parent / 'events.tef'
    tcf = parent / 'model.tcf'
    tef.write_text(
        'Define Event == Q100\n'
        '    BC Event Source == _event_ | 100yr\n'
        'End Define\n',
        encoding='utf-8',
    )
    tcf.write_text('Event File == events.tef\n', encoding='utf-8')
    run = TCF(tcf).context('-e1 Q100', file_resolution='deferred')
    refs = [ref for inp in run.find_input() for ref in inp.file_references]
    assert any(ref.path_pattern.name == 'events.tef' for ref in refs)


@pytest.mark.parametrize('mode', ['eager', 'deferred'])
def test_nested_output_variables_are_assignments_not_input_files(tmp_path, mode):
    """Output-root variables do not create input files or GeoPackage layers."""
    tcf = tmp_path / 'model.tcf'
    source = tmp_path / '2d_code.shp'
    source.touch()
    tcf.write_text(
        'Set Variable OutputBase == results\n'
        'Set Variable OutputRoot == ..\\<<OutputBase>>\n'
        'Set Variable XMDFBase == exports/output.xmdf\n'
        'Output Folder == <<OutputRoot>>\n'
        'Read GIS Code == 2d_code.shp\n',
        encoding='utf-8',
    )
    run = TCF(tcf).context(file_resolution=mode)
    variables = run.find_input(lhs='Set Variable')
    assert variables
    if mode == 'deferred':
        assert all(not item.file_references for item in variables)
        read_refs = [ref.path_pattern for inp in run.find_input(lhs='Read GIS Code')
                     for ref in inp.file_references]
        assert read_refs == [source]
    else:
        assert all(not item.files for item in variables)


def test_deferred_wildcard_includes_loaded_nested_control_files(tmp_path):
    """Cached TRD children must not disappear when their owner uses a glob."""
    includes = tmp_path / 'includes'
    includes.mkdir()
    for part in ('one', 'two'):
        (includes / f'{part}.trd').write_text(
            f'Read GIS Code == ../gis/2d_code_{part}.shp\n', encoding='utf-8',
        )
    top = tmp_path / 'model.tcf'
    top.write_text('Read File == includes/*.trd\n', encoding='utf-8')
    model = TCF(top)
    with patch.object(TuflowPath, 'glob', side_effect=AssertionError('deferred glob')):
        run = model.context(file_resolution='deferred')
        refs = [
            ref.path_pattern.name for inp in run.find_input() for ref in inp.file_references
        ]
    assert '2d_code_one.shp' in refs, refs
    assert '2d_code_two.shp' in refs, refs



def test_deferred_case_insensitive_nested_file(tmp_path):
    """TUFLOW Linux -cs2 explicitly permits filename case aliases."""
    geom = tmp_path / 'Geom.TGC'
    geom.write_text('Read GIS Code == gis/2d_code.shp\n', encoding='utf-8')
    tcf = tmp_path / 'main.tcf'
    tcf.write_text('Geometry Control File == geom.tgc\n', encoding='utf-8')
    parsed = TCF(tcf, case_sensitivity=2)
    with patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')):
        run = parsed.context(file_resolution='deferred')
        paths = {ref.path_pattern.name for inp in run.find_input()
                 for ref in inp.file_references}
    assert '2d_code.shp' in paths, paths


def test_deferred_recursive_geometry_bc_estry_sources_survive_cached_alias(tmp_path):
    """A parsed child under a UNC-style alias still supplies its GIS/grid inputs."""
    geom = tmp_path / 'geometry.tgc'
    bc = tmp_path / 'boundaries.tbc'
    estry = tmp_path / 'pipes.ecf'
    top = tmp_path / 'model.tcf'
    geom.write_text(
        'Read GIS Code == gis/2d_code_upstream.shp\n'
        'Read GRID Zpts == grids/terrain.tif\n', encoding='utf-8',
    )
    bc.write_text('Read GIS BC == gis/2d_bc_upstream.shp\n', encoding='utf-8')
    estry.write_text('Read GIS Network == gis/1d_nwk_upstream.shp\n', encoding='utf-8')
    top.write_text(
        'Geometry Control File == geometry.tgc\n'
        'BC Control File == boundaries.tbc\n'
        'ESTRY Control File == pipes.ecf\n', encoding='utf-8',
    )
    model = TCF(top)
    # Simulate a cached parse whose physical child paths have since been
    # canonicalised to a different drive/share. Do not read these fake paths.
    for inp in model.inputs:
        for child in inp.cf:
            child._fpath = tmp_path / 'other_share' / child.fpath.name
            # Preserve the lexical paths captured when the include was
            # initially parsed. Only the loaded object's fpath is an alias.
    with (
        patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')),
        patch('sqlite3.connect', side_effect=AssertionError('sqlite')),
        patch('os.scandir', side_effect=AssertionError('scan')),
    ):
        run = model.context(file_resolution='deferred')
        references = {
            ref.path_pattern.name for inp in run.find_input(recursive=True)
            for ref in inp.file_references
        }
    assert {'geometry.tgc', 'boundaries.tbc', 'pipes.ecf',
            '2d_code_upstream.shp', '2d_bc_upstream.shp',
            '1d_nwk_upstream.shp', 'terrain.tif'} <= references


def test_unmatched_cached_nested_file_must_fail_closed(tmp_path):
    """Do not certify a model when a nested file was not parsed."""
    top = tmp_path / 'model.tcf'
    child = tmp_path / 'geometry.tgc'
    child.write_text('Read GIS Code == gis/2d_code.shp\n', encoding='utf-8')
    top.write_text('Geometry Control File == geometry.tgc\n', encoding='utf-8')
    model = TCF(top)
    inp = model.find_input(lhs='Geometry Control File')[0]
    assert len(inp.cf) == 1
    inp.cf.clear()
    from pytuflow._tmf.abc.run_state import ResolveError
    with pytest.raises(ResolveError, match='Cached nested control-file index incomplete'):
        model.context(file_resolution='deferred')


@pytest.mark.parametrize('name', ['Read GIS PO', 'GPKG Projection'])
def test_deferred_gpkg_without_layer_uses_stem_named_default(tmp_path, name):
    """A missing default layer cannot pass preflight as a file-only check."""
    from pytuflow._tmf.file_reference import make_file_reference

    cmd = Command(f'{name} == gis/terrain_source.gpkg', config(tmp_path))
    refs = tuple(make_file_reference(part) for part in cmd.parts()
                 if part.is_value_a_file())
    assert len(refs) == 1
    assert refs[0].path_pattern.name == 'terrain_source.gpkg'
    assert refs[0].layer_pattern == 'terrain_source'
    assert refs[0].requires_layer_scan


def test_duplicate_cached_control_file_for_literal_reference_fails_closed(tmp_path):
    """A literal nested-control command must resolve to exactly one cached child."""
    from pytuflow._tmf.abc.run_state import ResolveError

    top = tmp_path / 'model.tcf'
    child = tmp_path / 'geometry.tgc'
    child.write_text('Read GIS Code == gis/code.shp\n', encoding='utf-8')
    top.write_text('Geometry Control File == geometry.tgc\n', encoding='utf-8')
    model = TCF(top)
    inp = model.find_input(lhs='Geometry Control File')[0]
    assert len(inp.cf) == 1
    inp.cf.append(inp.cf[0])
    inp._cf_loaded_paths.append(inp._cf_loaded_paths[0])
    with pytest.raises(ResolveError, match='Ambiguous cached child'):
        model.context(file_resolution='deferred')


def test_wrong_scenario_cached_control_does_not_match_same_filename(tmp_path):
    """Name-only fallback must not import geometry from an inactive folder."""
    from pytuflow._tmf.abc.run_state import ResolveError

    geom_dir = tmp_path / 'DEV'
    geom_dir.mkdir()
    (geom_dir / 'geometry.tgc').write_text(
        'Read GIS Code == gis/2d_code.shp\n', encoding='utf-8',
    )
    tcf = tmp_path / 'model.tcf'
    tcf.write_text('Geometry Control File == DEV/geometry.tgc\n', encoding='utf-8')
    model = TCF(tcf)
    inp = model.find_input(lhs='Geometry Control File')[0]
    assert len(inp._cf_loaded_paths) == 1
    inp._cf_loaded_paths[0] = tmp_path / 'EXG' / 'geometry.tgc'
    with pytest.raises(ResolveError, match='No cached nested control file'):
        model.context(file_resolution='deferred')


@pytest.mark.parametrize('pairs', [
    '0.05, 0.1',
    '0.05, 0.1, 0.1, 0.05',
])
def test_deferred_material_inline_depth_n_retain_primary_reference(tmp_path, pairs):
    """Depth/n pairs that eager parses create no secondary file references."""
    tcf = tmp_path / 'model.tcf'
    materials = tmp_path / 'materials.csv'
    tcf.write_text('Read Materials File == materials.csv | 0.8\n', encoding='utf-8')
    materials.write_text(
        "Material ID,Manning's n,Rainfall Losses\n"
        f'1,"{pairs}",0\n',
        encoding='utf-8',
    )
    model = TCF(tcf)
    eager = model.context()
    assert len(eager.find_input(lhs='Read Materials File')) == 1
    with (
        patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')),
        patch.object(Path, 'stat', side_effect=AssertionError('stat')),
        patch.object(Path, 'open', side_effect=AssertionError('open')),
    ):
        deferred = model.context(file_resolution='deferred')
        sources = deferred.deferred_database_sources()
    assert sources == ()
    assert [ref.path_pattern for ref in deferred.find_input(lhs='Read Materials File')[0].file_references] == [materials]


def test_deferred_material_external_source_matches_eager(tmp_path):
    """External material sources remain genuine file dependencies."""
    tcf = tmp_path / 'model.tcf'
    mat = tmp_path / 'materials.csv'
    secondary = tmp_path / 'external_material.csv'
    tcf.write_text('Read Materials File == materials.csv | 0.8\n', encoding='utf-8')
    mat.write_text("Material ID,Manning's n\n1,external_material.csv\n", encoding='utf-8')
    secondary.write_text('Depth,Manning n\n0,0.03\n', encoding='utf-8')
    run = TCF(tcf).context(file_resolution='deferred')
    files = {source.path_pattern for source in run.deferred_database_sources()}
    assert files == {secondary}


@pytest.mark.parametrize('method,values', [
    ('NONE', ''),
    ('ILCL', '12,1.2'),
    ('GA', 'Sandy Clay'),
    ('GA', '10,1.2,0.45'),
    ('HO', '10,2,1,0.1'),
    ('CO', '1.2,0.45'),
    ('SCS', '85,0.2'),
])
def test_deferred_soil_inline_methods_have_no_secondary_files(tmp_path, method, values):
    """Method-specific soil properties are inline parameters, not filenames."""
    tcf = tmp_path / 'model.tcf'
    soils = tmp_path / 'soils.tsoilf'
    tcf.write_text('Read Soil File == soils.tsoilf\n', encoding='utf-8')
    # TSOILF has no header; the first column is the soil ID.
    soils.write_text(f'1,{method},{values}\n', encoding='utf-8')
    model = TCF(tcf)
    run = model.context(file_resolution='deferred')
    ref = run.find_input(lhs='Read Soil File')[0].file_references
    assert len(ref) == 1
    assert ref[0].database_kind == 'soils'
    assert run.deferred_database_sources() == ()


@pytest.mark.parametrize('method,values', [
    ('ILCL', 'not-a-number,1.2'),
    ('HO', '10,,1,0.1'),
    ('SCS', '85,<<UNRESOLVED>>'),
    ('CUSTOM', 'some_file.csv'),
])
def test_deferred_soil_invalid_schema_fails_closed(tmp_path, method, values):
    """Unsupported soil rows cannot silently pass a dependency audit."""
    from pytuflow._tmf.deferred_database import DeferredDatabaseResolutionError
    tcf = tmp_path / 'model.tcf'
    soils = tmp_path / 'soils.tsoilf'
    tcf.write_text('Read Soil File == soils.tsoilf\n', encoding='utf-8')
    soils.write_text(f'1,{method},{values}\n', encoding='utf-8')
    model = TCF(tcf)
    with pytest.raises(DeferredDatabaseResolutionError):
        model.context(file_resolution='deferred').deferred_database_sources()


def test_deferred_malformed_inline_materials_fail_closed(tmp_path):
    """Unpaired or nonnumeric depth/n values must not be mistaken for files."""
    from pytuflow._tmf.deferred_database import DeferredDatabaseResolutionError
    tcf = tmp_path / 'model.tcf'
    mat = tmp_path / 'materials.csv'
    tcf.write_text('Read Materials File == materials.csv | 0.8\n', encoding='utf-8')
    mat.write_text(
        "Material ID,Manning's n\n"
        '1,"0.05, oops, 0.1, 0.05"\n', encoding='utf-8',
    )
    with pytest.raises(DeferredDatabaseResolutionError):
        TCF(tcf).context(file_resolution='deferred').deferred_database_sources()


def test_deferred_material_and_soil_variables_are_context_expanded(tmp_path):
    """Variables inside cached table cells have the active context's values."""
    tcf = tmp_path / 'model.tcf'
    mat = tmp_path / 'materials.csv'
    soils = tmp_path / 'soils.tsoilf'
    tcf.write_text(
        'Set Variable MaterialSource == roughness.csv\n'
        'Set Variable InitialLoss == 12\n'
        'Read Materials File == materials.csv | 0.8\n'
        'Read Soil File == soils.tsoilf\n',
        encoding='utf-8',
    )
    mat.write_text(
        "Material ID,Manning's n\n"
        '1,<<MaterialSource>>\n',
        encoding='utf-8',
    )
    soils.write_text('1,ILCL,<<InitialLoss>>,1.2\n', encoding='utf-8')
    run = TCF(tcf).context(file_resolution='deferred')
    sources = run.deferred_database_sources()
    assert len(sources) == 1
    assert sources[0].database_kind == 'materials'
    assert sources[0].path_pattern == tmp_path / 'roughness.csv'


@pytest.mark.skipif(os.name != "nt", reason="Native Windows filesystems are case insensitive")
@pytest.mark.parametrize("case_sensitivity", [None, 0, 1, 2])
def test_windows_default_and_case_options_preserve_native_input_lookup(tmp_path, case_sensitivity):
    """No change to existing Windows eager materialisation or public defaults."""
    actual = tmp_path / "Materials.csv"
    actual.write_text("Material, Manning\n1,0.04\n", encoding="utf-8")
    tcf = tmp_path / "windows_case.tcf"
    tcf.write_text("Read Materials File == materials.CSV\n", encoding="utf-8")
    model = TCF(tcf) if case_sensitivity is None else TCF(tcf, case_sensitivity=case_sensitivity)
    material = model.find_input(lhs="Read Materials File")[0]
    assert not material.has_missing_files
    assert material.files


def test_spatial_database_layer_only_reference_uses_expanded_gpkg_without_io(
    tmp_path: Path,
) -> None:
    """A layer-only GIS value denotes the configured spatial GeoPackage."""
    cfg = config(tmp_path)
    cfg.set_spatial_database("gis/model.gpkg")
    command = Command("Read GIS Code == 2d_code", cfg)
    assert command.value == "2d_code"
    assert "model.gpkg >> 2d_code" in str(command.value_expanded_path)

    with (
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(Path, "open", side_effect=AssertionError("open")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
        patch("sqlite3.connect", side_effect=AssertionError("SQLite")),
    ):
        reference = make_file_reference(command)
    assert reference.path_pattern == tmp_path / "gis" / "model.gpkg"
    assert reference.layer_pattern == "2d_code"
    assert ">> 2d_code" in reference.expanded_value
    assert reference.requires_layer_scan
    assert not reference.requires_directory_scan
    assert not reference.unresolved_variables


def test_batch_preflight_spatial_database_layer_only_reference(tmp_path: Path) -> None:
    """Batch preflight validates the real GPKG and named layer, not a fake file."""
    import sqlite3

    from pytuflow.batch_validation import validate_batch_inputs

    gpkg = tmp_path / "model.gpkg"
    with sqlite3.connect(gpkg) as connection:
        connection.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        connection.execute("INSERT INTO gpkg_contents VALUES ('2d_code')")
        connection.commit()

    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "Spatial Database == model.gpkg\n"
        "Read GIS Code == 2d_code\n",
        encoding="utf-8",
    )
    model = TCF(tcf)
    flags = ["-s1 BASE"]
    syntactic = model.collect_file_dependencies(flags)
    assert syntactic.passed, [run.error for run in syntactic.runs]
    refs = [ref for ref in syntactic.runs[0].file_references
            if ref.layer_pattern == "2d_code"]
    assert len(refs) == 1
    assert refs[0].path_pattern == gpkg

    report = validate_batch_inputs(model, flags)
    assert report.passed, [(x.kind, x.status, x.path, x.detail)
                           for x in report.issues]
    assert any(x.kind == "layer" and x.status == "present"
               and x.path == gpkg and x.layer == "2d_code"
               for x in report.validation.findings)

    with sqlite3.connect(gpkg) as connection:
        connection.execute("DELETE FROM gpkg_contents")
        connection.commit()
    missing = validate_batch_inputs(model, flags)
    assert not missing.passed
    assert any(x.kind == "layer" and x.status == "missing"
               and x.path == gpkg for x in missing.issues)


def test_cached_windows_root_alias_requires_matching_directory_hierarchy() -> None:
    """Matching subpaths cannot establish that distinct roots are aliases."""
    from types import SimpleNamespace

    from pytuflow._tmf.abc.run_state import ResolveError
    from pytuflow._tmf.inp.cf import select_deferred_children

    requested = Path('Q:/models/Area/geom.tgc')
    for cached in (
        Path('R:/models/Area/geom.tgc'),
        Path(r'\\server\share\models\Area\geom.tgc'),
        Path('Q:/other/Area/geom.tgc'),
    ):
        build = SimpleNamespace(cf=[object()], _cf_loaded_paths=[cached],
                                config=SimpleNamespace(case_sensitivity=2), lhs='Geometry Control File')
        ref = SimpleNamespace(path_pattern=requested, unresolved_variables=())
        with pytest.raises(ResolveError, match='No cached nested control file'):
            select_deferred_children(build, [ref])


@pytest.mark.parametrize(('filename', 'pattern', 'expected'), [
    ('geom_A.tgc', 'geom_*', True),
    ('geom_A.TGC', 'geom_*.tgc', True),
    ('Geom_A.tgc', 'geom_*', False),
    ('geom_A.tgc', 'geom_?.*', True),
    ('geom_A.tgc', 'geom_*.csv', False),
])
def test_cached_cs1_wildcards_follow_full_filename_and_stem(
    monkeypatch, filename, pattern, expected,
):
    from types import SimpleNamespace

    from pytuflow._tmf import file_reference

    monkeypatch.setattr(file_reference, 'os', SimpleNamespace(name='posix'))
    assert file_reference._cached_filename_matches(filename, pattern, 1) is expected
