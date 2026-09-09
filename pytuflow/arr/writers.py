"""TUFLOW output writers for :mod:`pytuflow.arr`.

Writes the standard TUFLOW ARR input files from a list of
:class:`~pytuflow.arr.engine.EventResult`:

* ``Event_File.tef`` - defines the ``~AEP~``/``~ARI~``, ``~DUR~``, ``~TP~`` (and
  ``~CC~``, if climate change is enabled) event variables.
* ``bc_dbase.csv`` - one row per site, referencing the rf_inflow rainfall CSV/ts1 files.
* ``rf_inflow/<site>_RF_<aep><dur>.<csv|ts1>`` - one rainfall hyetograph file per
  AEP x duration (x climate change scenario) combination, with one column per selected
  temporal pattern.
* ``soils.tsoilf`` / ``rainfall_losses.trd`` - initial/continuing loss control files
  (``tsoilf`` when ``losses.tuflow_loss_method == 'infiltration'``, a TUFLOW ``.trd`` read
  file of ``Set Variable`` statements otherwise), driven by ``<<IL_name>>``/``<<CL_name>>``
  scalars defined per AEP/duration (/CC scenario) combination.

Multiple sites/catchments can be appended into the same output folder by calling
:func:`write_outputs` repeatedly with ``append=True`` for the second and subsequent
sites - matching the legacy script's ``catch_no`` multi-catchment behaviour, but
simplified: this rewrite does not attempt to merge per-catchment IF-statement blocks in
the ``.trd``/control files as compactly as legacy did; each site gets its own IF/ELSE IF
branch keyed on its AEP/duration event names, appended sequentially.
"""

from __future__ import annotations

import csv as csv_module
import logging
from pathlib import Path
from typing import Optional

from .config import ArrConfig
from .exceptions import ArrError

logger = logging.getLogger('pytuflow.arr')


def format_aep(aep_name: str, output_notation: str) -> str:
    """Formats an AEP/ARI/EY magnitude label into a TUFLOW event-name-safe token, e.g.
    ``'1%'`` -> ``'01p'``, ``'0.5EY'`` -> ``'0.5e'``, ``'1 in 200'`` -> ``'200y'``.

    This is a simpler, fixed-width-free scheme than the legacy script's elaborate
    per-run padding-width tables (which varied formatting based on which other AEPs were
    present in the same run) - deliberately simplified since file/event names no longer
    need to match the legacy naming convention exactly.
    """
    aep_name = str(aep_name).strip()
    if aep_name.endswith('EY'):
        return f'{aep_name[:-2]}e'
    if aep_name.endswith('%'):
        value = float(aep_name[:-1])
        if value == int(value):
            return f'{int(value):02d}p'
        return f'{value:.2f}p'
    if aep_name.lower().startswith('1 in'):
        return f'{aep_name[4:].strip()}y'
    raise ArrError(f"Unrecognised AEP/ARI/EY magnitude: '{aep_name}'")


def format_duration(duration: float) -> str:
    """Formats a duration in minutes as a TUFLOW event-name-safe token, e.g. ``1440`` ->
    ``'1440m'``."""
    duration = float(duration)
    if duration == int(duration):
        return f'{int(duration)}m'
    return f'{duration:g}m'


def site_name_token(name: str) -> str:
    return str(name).strip()


def write_tef(path: Path, config: ArrConfig, results: list, append: bool = False) -> None:
    """Writes (or appends to) ``Event_File.tef``."""
    aep_names = sorted({r.aep_name for r in results}, key=lambda a: [r.aep_name for r in results].index(a))
    durations = sorted({r.duration for r in results})
    tp_count = max((len(r.patterns) for r in results), default=0)
    cc_scenarios = sorted({r.cc_scenario for r in results if r.cc_scenario is not None})
    out_notation = config.events.output_notation

    mode = 'a' if append and path.exists() else 'w'
    with open(path, mode, encoding='utf-8') as f:
        if mode == 'w':
            f.write('!EVENT MAGNITUDES\n')
            var = '~ARI~' if out_notation == 'ari' else '~AEP~'
            for aep in aep_names:
                token = format_aep(aep, out_notation)
                f.write(f'Define Event == {token}\n')
                f.write(f'    BC Event Source == {var} | {token}\n')
                f.write('End Define\n\n')

            f.write('!EVENT DURATIONS\n')
            for dur in durations:
                token = format_duration(dur)
                f.write(f'Define Event == {token}\n')
                f.write(f'    BC Event Source == ~DUR~ | {token}\n')
                f.write('End Define\n\n')

            f.write('!EVENT TEMPORAL PATTERNS\n')
            for i in range(1, tp_count + 1):
                f.write(f'Define Event == tp{i:02d}\n')
                f.write(f'    BC Event Source == ~TP~ | TP{i:02d}\n')
                f.write('End Define\n\n')

            if cc_scenarios:
                f.write('!CLIMATE CHANGE SCENARIOS\n')
                for scenario in cc_scenarios:
                    f.write(f'Define Event == {scenario}\n')
                    f.write(f'    BC Event Source == ~CC~ | {scenario}\n')
                    f.write('End Define\n\n')


def write_bc_dbase(path: Path, config: ArrConfig, append: bool = False) -> None:
    """Writes (or appends a row to) ``bc_dbase.csv``."""
    out_form = config.output.format
    out_notation = config.events.output_notation.upper()
    site = site_name_token(config.site.name)
    time_col = 'Time (min)' if out_form == 'ts1' else 'Time (hour)'
    line = f'{site},rf_inflow\\{site}_RF_~{out_notation}~~DUR~.{out_form},{time_col}, ~TP~\n'

    mode = 'a' if append and path.exists() else 'w'
    with open(path, mode, encoding='utf-8') as f:
        if mode == 'w':
            f.write('Name,Source,Column 1,Column 2,Add Col 1,Mult Col 2,Add Col 2,Column 3,Column 4\n')
        f.write(line)


def write_rf_inflow(folder: Path, config: ArrConfig, result) -> Path:
    """Writes a single rainfall hyetograph file (csv or ts1) for one
    :class:`~pytuflow.arr.engine.EventResult`. Returns the file path written.

    If ``result.preburst`` is set (complete storm event), the preburst rainfall
    increments are prepended ahead of the design burst increments, each pattern column
    sharing the same (single) preburst prefix - matching the legacy script's complete
    storm output, where the preburst period is common to all temporal pattern
    realisations for that event."""
    folder.mkdir(parents=True, exist_ok=True)
    out_form = config.output.format
    out_notation = config.events.output_notation.upper()
    site = site_name_token(config.site.name)
    aep_token = format_aep(result.aep_name, config.events.output_notation)
    dur_token = format_duration(result.duration)
    suffix = f'_{result.cc_scenario}' if result.cc_scenario else ''
    fname = f'{site}_RF_{aep_token}{dur_token}{suffix}.{out_form}'
    fpath = folder / fname

    patterns = result.patterns
    if not patterns:
        raise ArrError(f"No temporal patterns available for {result.aep_name}/{result.duration}min - cannot write rf_inflow file.")
    timestep = patterns[0].timestep
    n_steps = len(patterns[0].increments)
    time_col = 'Time (min)' if out_form == 'ts1' else 'Time (hour)'
    time_divisor = 1.0 if out_form == 'ts1' else 60.0

    pb = result.preburst
    pb_timestep = pb.timestep if pb else None
    pb_n_steps = len(pb.increments) if pb else 0

    with open(fpath, 'w', encoding='utf-8', newline='') as f:
        f.write(f'! Written by pytuflow.arr based on {result.aep_band} temporal pattern\n')
        total_steps = pb_n_steps + n_steps
        if out_form == 'ts1':
            f.write(f'{len(patterns)}, {total_steps + 1}\n')
            f.write('Start_Index' + ', 1' * len(patterns) + '\n')
            f.write('End_Index' + f', {total_steps + 1}' * len(patterns) + '\n')
        writer = csv_module.writer(f)
        if out_form == 'csv':
            writer.writerow(['Event ID'] + [p.event_id for p in patterns])
        writer.writerow([time_col] + [f'TP{p.tp_number:02d}' for p in patterns])
        writer.writerow([0] + [0] * len(patterns))
        t = 0.0
        for i in range(pb_n_steps):
            t += pb_timestep / time_divisor
            row = [t] + [pb.increments[i] * pb.depth / 100.0 for _ in patterns]
            writer.writerow(row)
        for i in range(n_steps):
            t += timestep / time_divisor
            row = [t] + [p.increments[i] * result.depth_areal / 100.0 for p in patterns]
            writer.writerow(row)
        t += timestep / time_divisor
        writer.writerow([t] + [0] * len(patterns))
    return fpath


def write_losses(path: Path, config: ArrConfig, results: list, append: bool = False) -> None:
    """Writes (or appends to) the loss control file: ``soils.tsoilf`` (a single-line
    ``ILCL`` scalar entry referencing ``<<IL_name>>``/``<<CL_name>>``, when
    ``losses.tuflow_loss_method == 'infiltration'``) alongside a companion
    ``.trd`` read file (always written) that sets those ``IL_name``/``CL_name`` scalars
    per AEP/duration(/CC scenario) event combination.
    """
    site = site_name_token(config.site.name)
    losses_cfg = config.losses

    if losses_cfg.tuflow_loss_method == 'infiltration':
        tsoilf_path = path.parent / 'soils.tsoilf'
        mode = 'a' if append and tsoilf_path.exists() else 'w'
        soil_id = 1
        if mode == 'a':
            with open(tsoilf_path, encoding='utf-8') as existing:
                soil_id = sum(1 for line in existing if line.strip() and not line.startswith('!')) + 1
        with open(tsoilf_path, mode, encoding='utf-8') as f:
            if mode == 'w':
                f.write('! Soil ID, Method, IL, CL\n')
            f.write(f'{soil_id}, ILCL, <<IL_{site}>>, <<CL_{site}>>  ! Design ARR Losses For Catchment {site}\n')

    out_notation = config.events.output_notation
    cc_scenarios = sorted({r.cc_scenario for r in results if r.cc_scenario is not None})
    by_aep_dur: dict = {}
    for r in results:
        key = (format_aep(r.aep_name, out_notation), format_duration(r.duration))
        by_aep_dur.setdefault(key, {})[r.cc_scenario] = r

    trd_path = path.parent / ('soil_infiltration.trd' if losses_cfg.tuflow_loss_method == 'infiltration' else 'rainfall_losses.trd')
    mode = 'a' if append and trd_path.exists() else 'w'
    with open(trd_path, mode, encoding='utf-8') as f:
        if mode == 'w':
            f.write('! TUFLOW READ FILE - SET RAINFALL LOSS VARIABLES\n')
        aeps = sorted({k[0] for k in by_aep_dur})
        for ai, aep_token in enumerate(aeps):
            if1 = 'If' if ai == 0 else 'Else If'
            f.write(f'{if1} Event == {aep_token}\n')
            durs = sorted({k[1] for k in by_aep_dur if k[0] == aep_token})
            for di, dur_token in enumerate(durs):
                if2 = 'If' if di == 0 else 'Else If'
                f.write(f'    {if2} Event == {dur_token}\n')
                scenario_map = by_aep_dur[(aep_token, dur_token)]
                if cc_scenarios:
                    for ci, scenario in enumerate(cc_scenarios):
                        if3 = 'If' if ci == 0 else 'Else If'
                        r = scenario_map.get(scenario)
                        if r is None:
                            continue
                        f.write(f'        {if3} Event == {scenario}\n')
                        f.write(f'            Set Variable IL_{site} == {r.initial_loss:.1f}\n')
                        f.write(f'            Set Variable CL_{site} == {r.continuing_loss:.1f}\n')
                    f.write('        Else  ! no climate change\n')
                    r = scenario_map.get(None)
                    if r is not None:
                        f.write(f'            Set Variable IL_{site} == {r.initial_loss:.1f}\n')
                        f.write(f'            Set Variable CL_{site} == {r.continuing_loss:.1f}\n')
                    f.write('        End If\n')
                else:
                    r = scenario_map.get(None)
                    f.write(f'        Set Variable IL_{site} == {r.initial_loss:.1f}\n')
                    if not losses_cfg.use_global_continuing_loss:
                        f.write(f'        Set Variable CL_{site} == {r.continuing_loss:.1f}\n')
            f.write('    Else\n')
            f.write('        Pause == Event Not Recognised\n')
            f.write('    End If\n')
        f.write('Else\n')
        f.write('    Pause == Event Not Recognised\n')
        f.write('End If\n')


def write_outputs(config: ArrConfig, results: list, append: bool = False) -> None:
    """Writes all standard TUFLOW output files for a single site/config's assembled
    events into ``config.output.path``. Pass ``append=True`` when processing multiple
    site configs into the same output folder (all files except the per-event
    ``rf_inflow`` files, which are always written fresh, are appended to)."""
    out_path = Path(config.output.path)
    out_path.mkdir(parents=True, exist_ok=True)

    write_tef(out_path / 'Event_File.tef', config, results, append=append)
    write_bc_dbase(out_path / 'bc_dbase.csv', config, append=append)
    rf_folder = out_path / 'rf_inflow'
    for result in results:
        write_rf_inflow(rf_folder, config, result)
    write_losses(out_path / 'soils.tsoilf', config, results, append=append)
    logger.info("Wrote TUFLOW ARR outputs for site '%s' to '%s'", config.site.name, out_path)
