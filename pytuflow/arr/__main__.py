r"""CLI for pytuflow.arr.

Usage:
    pytuflow-arr config1.json [config2.json ...]

Each JSON config file describes a single site/catchment (see ``arr_config_schema.md`` in
the repository root for the schema). When multiple config files are given, they are
processed in order and their TUFLOW outputs (event file, bc_dbase, rainfall loss trd,
etc) are appended into a single set of output files rather than being overwritten by
each subsequent config.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from .api_client import ArrApiClient, ArrApiResponse
from .config import ArrConfig
from .engine import ArrEngine
from .exceptions import ArrError
from .working_data import write_working_data
from .writers import write_outputs

logger = logging.getLogger('pytuflow.arr')


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%H:%M:%S',
        force=True,
    )


def _load_response(client: ArrApiClient, config: ArrConfig) -> ArrApiResponse:
    """Returns the ARR Data Hub response for ``config``'s site - loaded from a local
    JSON file (``response_json``, e.g. a prior run's
    ``working_data/<site>_ARR_response.json`` output) if set, instead of issuing a live
    API request."""
    if config.response_json:
        logger.info("Loading ARR Data Hub response for site '%s' from local file '%s'",
                    config.site.name, config.response_json)
        try:
            with open(config.response_json, encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ArrError(f"response_json file '{config.response_json}' is not valid JSON: {e}") from e
        return ArrApiResponse(data)
    return client.fetch(config)


def run(config_paths: Sequence[str]) -> int:
    """Loads and processes each config file in turn, returning a process exit code."""
    client = ArrApiClient()
    for i, config_path in enumerate(config_paths):
        append = i > 0
        try:
            config = ArrConfig.from_file(config_path)
        except ArrError as e:
            logger.error("Failed to load config '%s': %s", config_path, e)
            return 1
        logger.info("Processing site '%s' from '%s' (append=%s)", config.site.name, config_path, append)
        try:
            response = _load_response(client, config)
        except ArrError as e:
            logger.error("Failed to fetch ARR Data Hub data for '%s': %s", config_path, e)
            return 1
        logger.info("Fetched ARR Data Hub data for site '%s' (%s)", config.site.name, response.title)
        try:
            engine = ArrEngine(config, response)
            results = engine.run()
        except ArrError as e:
            logger.error("Failed to assemble events for '%s': %s", config_path, e)
            return 1
        logger.info("Assembled %d event(s) for site '%s'", len(results), config.site.name)
        try:
            write_working_data(config, response, engine)
        except ArrError as e:
            logger.error("Failed to write working data for '%s': %s", config_path, e)
            return 1
        try:
            write_outputs(config, results, append=append)
        except ArrError as e:
            logger.error("Failed to write outputs for '%s': %s", config_path, e)
            return 1
    return 0


def main(argv: Sequence[str] = None) -> None:
    parser = argparse.ArgumentParser(
        prog='pytuflow-arr',
        description='Convert ARR Data Hub rainfall/loss data into TUFLOW input files.',
    )
    parser.add_argument('config', nargs='+', help='One or more JSON config files to process, in order.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose (debug) logging.')
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    for config_path in args.config:
        if not Path(config_path).exists():
            parser.error(f"Config file not found: {config_path}")

    sys.exit(run(args.config))


if __name__ == '__main__':
    main()
