from pathlib import Path
import json
import warnings

from ..._tmf import TuflowPath


_EMPTIES_DIR = Path(__file__).parents[1] / 'data' / 'empties'

# Maps single-char geometry code (used in TUFLOW file naming) to open_gis geometry type string.
_GEOM_CHAR_MAP = {'P': 'Point', 'L': 'LineString', 'R': 'Polygon'}

_SHP_MAX_FIELD_LEN = 10


def _shorten_field_names(schema: list[dict]) -> list[dict]:
    """Return a copy of schema with field names truncated to 10 characters for SHP compatibility.

    Collisions are resolved by appending ``_N`` (using 8 prefix chars + suffix)."""
    result = []
    seen: dict[str, int] = {}
    for field in schema:
        name = field['name']
        short = name[:_SHP_MAX_FIELD_LEN]
        if short in seen:
            count = seen[short] = seen[short] + 1
            short = f"{name[:8]}_{count}"[:_SHP_MAX_FIELD_LEN]
        else:
            seen[short] = 0
        result.append({**field, 'name': short})
    return result


def _load_empties_json(engine: str) -> dict:
    """Load the empties JSON for *engine* and normalise to ``{"types": [...], "schemas": [...]}``.

    Handles both the legacy flat-list format (schemas only) and the current
    dict format that carries an explicit ``types`` list alongside schemas.
    """
    path = _EMPTIES_DIR / f'{engine}_empties.json'
    try:
        with path.open() as f:
            data = json.load(f)
    except Exception:
        return {'types': [], 'schemas': []}

    if isinstance(data, list):
        # Legacy format — flat list of schema objects, no type metadata
        return {'types': [], 'schemas': data}
    return data


class TuflowEmptyFiles:

    def __init__(self, engine: str, gis_format: str, projection_wkt: str | None = None):
        data = _load_empties_json(engine)
        self.empty_types = [
            TuflowEmptyType(engine, t['name'], t['geom'], gis_format, projection_wkt)
            for t in data.get('types', [])
        ]

    def write_empties(self, dir_path: str):
        for empty_type in self.empty_types:
            empty_type.write_empty(dir_path)


class TuflowEmptyType:

    def __init__(self, engine: str, name: str, geom: str, gis_format: str, projection_wkt: str | None = None):
        self.engine = engine
        self.name = name
        # Normalize geom: flatten any multi-char elements into individual chars, e.g. ['PL'] → ['P', 'L']
        self.geom = [g for g in geom]
        self.gis_format = gis_format.lower()
        self.projection_wkt = projection_wkt

    def count(self):
        return len(self.geom)

    def get_schema(self, name: str) -> list[dict] | None:
        data = _load_empties_json(self.engine)
        schemas_list = data.get('schemas', [])
        if not schemas_list:
            return None
        empty_schemas = {x['name']: x for x in schemas_list}
        empty_schema = empty_schemas.get(name)
        if not empty_schema:
            return None
        schema = empty_schema['schema']
        if empty_schema.get('base_schema'):
            base_schema = self.get_schema(empty_schema['base_schema'])
            if not base_schema:
                return schema
            if empty_schema.get('extend_by') == 'append':
                base_schema.extend(schema)
            elif empty_schema.get('extend_by') == 'replace':
                names = [x['name'] for x in base_schema]
                for sch in schema:
                    field_name = sch['name']
                    if field_name in names:
                        i = names.index(field_name)
                        base_schema[i] = sch
            else:
                return schema
            schema = base_schema
        return schema
            

    def write_empty(self, dir_path):
        schema = self.get_schema(self.name)
        if schema is None:
            raise KeyError(f'Error: schema not found for {self.name}_empty')

        if 'pts' in self.name:
            table_name = f'{self.name[:-4]}_empty_pts'
        else:
            table_name = f'{self.name}_empty'

        uris = []
        if self.gis_format == 'mif':
            geom_type = _GEOM_CHAR_MAP.get(self.geom[0], 'Point')
            uris = [(f'{dir_path / table_name}.mif >> {table_name}', geom_type)]
        elif self.gis_format == 'gpkg':
            for g in self.geom:
                geom_type = _GEOM_CHAR_MAP.get(g, 'Point')
                uris.append((f'{dir_path / table_name}.gpkg >> {table_name}_{g}', geom_type))
        elif self.gis_format == 'shp':
            for g in self.geom:
                geom_type = _GEOM_CHAR_MAP.get(g, 'Point')
                uris.append((f'{dir_path / table_name}_{g}.shp >> {table_name}_{g}', geom_type))
        else:
            raise NotImplementedError(f'Unrecognised GIS format: {self.gis_format}')

        for uri, geom_type in uris:
            effective_schema = _shorten_field_names(schema) if self.gis_format == 'shp' else schema
            self.create_empty(uri, geom_type, effective_schema, self.projection_wkt)

    @staticmethod
    def create_empty(uri: str, geom_type: str, schema: list[dict], projection_wkt: str | None):
        p = TuflowPath(uri)
        with warnings.catch_warnings():
            # No-CRS warning is expected when projection_wkt is None (intentionally unprojected).
            warnings.filterwarnings('ignore', message=".*crs.*was not provided.*", category=UserWarning)
            with p.open_gis('w', geom_type, projection_wkt) as gis:
                for field in schema:
                    # Strip prec=-1 sentinel (means "not applicable") before passing to create_field
                    f = {k: v for k, v in field.items() if not (k == 'prec' and v == -1)}
                    gis.create_field(**f)
