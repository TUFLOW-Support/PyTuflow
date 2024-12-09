import json
from pathlib import Path

from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name

with (Path(__file__).parents[1] / 'data' / 'ts_labels.json').open() as f:
    TPC_INTERNAL_NAMES = json.load(f)


def map_standard_data_types_to_tpc_internal() -> dict:
    d = {}
    for domain in ['1d_labels', 'rl_labels', 'po_labels']:
        for key in TPC_INTERNAL_NAMES[domain]:
            stnd = get_standard_data_type_name(key)
            d[stnd] = key
    return d
