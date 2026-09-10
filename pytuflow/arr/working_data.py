"""Writes supporting "working data" files alongside the standard TUFLOW outputs, for
transparency/QA of the ARR Data Hub request and the intermediate calculations used to
assemble each event.

The raw ARR Data Hub JSON response is always saved (one per additional
``temporal_patterns.additional_tp`` region too, if any are configured - each is a
genuinely separate ARR Data Hub API request/response). Everything else (the areal
design IFD table, the ARF table, the burst initial loss table, the extrapolated
short-duration losses table, and the raw point/areal temporal pattern increment CSVs,
including for any additional TP regions) is only saved when ``output.verbose`` is
``true``, since these are only useful for debugging/QA and are otherwise redundant with
the ``rf_inflow``/loss control files that are always written.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .api_client import ArrApiResponse
from .config import ArrConfig
from .engine import ArrEngine

logger = logging.getLogger('pytuflow.arr')

#: Subfolder (under ``output.path``) that working data files are written to.
WORKING_DATA_FOLDER = 'working_data'


def write_working_data(config: ArrConfig, response: ArrApiResponse, engine: ArrEngine) -> None:
    """Writes the ARR Data Hub JSON response (always, plus one per additional
    ``temporal_patterns.additional_tp`` region) and, if ``config.output.verbose``
    is set, the areal design IFD table, ARF table, burst initial loss table,
    extrapolated short-duration losses table (if any losses were extrapolated), and raw
    point/areal temporal pattern increment CSVs (including for any additional TP
    regions), into a ``working_data`` subfolder of ``config.output.path``.
    """
    site = str(config.site.name).strip()
    out_path = Path(config.output.path) / WORKING_DATA_FOLDER
    out_path.mkdir(parents=True, exist_ok=True)

    json_path = out_path / f'{site}_ARR_response.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(response.raw, f, indent=2)
    logger.info("Wrote ARR Data Hub response to '%s'", json_path)

    for region_name, info in engine.additional_tp_responses.items():
        region_token = ''.join(ch for ch in region_name if ch.isalnum())
        region_json_path = out_path / f'{site}_ARR_response_{region_token}.json'
        with open(region_json_path, 'w', encoding='utf-8') as f:
            json.dump(info['raw'], f, indent=2)
        logger.info("Wrote additional temporal pattern region '%s' ARR Data Hub response to '%s'",
                    region_name, region_json_path)

    if not config.output.verbose:
        return

    for scenario_label, table in engine.depth_areal_tables.items():
        suffix = f'_{scenario_label}' if scenario_label else ''
        path = out_path / f'{site}_IFD_after_ARF{suffix}.csv'
        table.to_csv(path, index_label='Duration (min)')
        logger.info("Wrote areal design IFD table to '%s'", path)

    for scenario_label, table in engine.arf_tables.items():
        suffix = f'_{scenario_label}' if scenario_label else ''
        path = out_path / f'{site}_ARF{suffix}.csv'
        table.to_csv(path, index_label='Duration (min)')
        logger.info("Wrote ARF table to '%s'", path)

    for scenario_label, table in engine.burst_loss_table.items():
        if table is None:
            continue
        suffix = f'_{scenario_label}' if scenario_label else ''
        path = out_path / f'{site}_burst_initial_loss{suffix}.csv'
        table.to_csv(path, index_label='Duration (min)')
        logger.info("Wrote burst initial loss table to '%s'", path)

    if engine.extrapolated_loss_table:
        for scenario_label, table in engine.extrapolated_loss_table.items():
            if table.empty:
                continue
            suffix = f'_{scenario_label}' if scenario_label else ''
            path = out_path / f'{site}_extrapolated_losses{suffix}.csv'
            table.to_csv(path, index_label='Duration (min)')
            logger.info("Wrote extrapolated short-duration losses table to '%s'", path)

    tp_set = engine._tp_set
    if tp_set is not None:
        if tp_set.point_tp_csv:
            path = out_path / f'{site}_PointTP_Increments.csv'
            path.write_text(tp_set.point_tp_csv, encoding='utf-8')
            logger.info("Wrote point temporal pattern increments to '%s'", path)
        if tp_set.areal_tp_csv:
            path = out_path / f'{site}_ArealTP_Increments.csv'
            path.write_text(tp_set.areal_tp_csv, encoding='utf-8')
            logger.info("Wrote areal temporal pattern increments to '%s'", path)

    for region_name, info in engine.additional_tp_responses.items():
        region_token = ''.join(ch for ch in region_name if ch.isalnum())
        path = out_path / f'{site}_PointTP_Increments_{region_token}.csv'
        path.write_text(info['csv'], encoding='utf-8')
        logger.info("Wrote additional temporal pattern region '%s' point temporal pattern increments to '%s'",
                    region_name, path)
