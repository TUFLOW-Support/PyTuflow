from pathlib import Path
import json
import warnings

from ..._tmf import TuflowPath


_HPC_EMPTY_SCHEMA_PATH = Path(__file__).parents[1] / 'data' / 'empties' / 'hpc_empties.json'

# Maps single-char geometry code (used in TUFLOW file naming) to open_gis geometry type string.
_GEOM_CHAR_MAP = {'P': 'Point', 'L': 'LineString', 'R': 'Polygon'}


class TuflowEmptyFiles:

    def __init__(self, engine: str, gis_format: str, projection_wkt: str | None = None):
        self.empty_types = [
            TuflowEmptyType(engine, '1d_nd', ['P'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_nwk', ['PL'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_nwke', ['PL'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_nwkb', ['PL'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_mh', ['P'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_bc', ['PR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_iwl', ['P'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_tab', ['PL'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_xs', ['L'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_na', ['P'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_WLL', ['LR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '1d_pit', ['P'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_po', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_lp', ['L'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_fc', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_glo', ['P'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_bc', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_code', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_mat', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_sa', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_rf', ['PR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_sa_rf', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_sa_tr', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_z__', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_zsh', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_zshr', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_ztin', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_vzsh', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_fcsh', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_lfcsh', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_lfcsh_pts', ['P'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_iwl', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_loc', ['LR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_oz', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_soil', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_gw', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '0d_rl', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_at', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_qnl', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_cwf', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_flc', ['R'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_obj', ['PR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_rec', ['PR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_wrf', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_bg', ['PLR'], gis_format, projection_wkt),
            TuflowEmptyType(engine, '2d_bg_pts', ['P'], gis_format, projection_wkt),
            TuflowEmptyType(engine, 'swmm_iu', ['P'], gis_format, projection_wkt),
        ]

    def write_empties(self, dir_path: str):
        for empty_type in self.empty_types:
            empty_type.write_empty(dir_path)


class TuflowEmptyType:

    def __init__(self, engine: str, name: str, geom: list[str], gis_format: str, projection_wkt: str | None = None):
        self.engine = engine
        self.name = name
        # Normalize geom: flatten any multi-char elements into individual chars, e.g. ['PL'] → ['P', 'L']
        self.geom = [c for item in geom for c in item]
        self.gis_format = gis_format.lower()
        self.projection_wkt = projection_wkt

    def count(self):
        return len(self.geom)

    def get_schema(self, name: str) -> list[dict] | None:
        schema_path = _HPC_EMPTY_SCHEMA_PATH if self.engine == 'hpc' else Path()
        try:
            with schema_path.open() as f:
                empty_schemas = json.load(f)
        except Exception:
            return None
        empty_schemas = {x['name']: x for x in empty_schemas}
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
            self.create_empty(uri, geom_type, schema, self.projection_wkt)

    @staticmethod
    def create_empty(uri: str, geom_type: str, schema: list[dict], projection_wkt: str | None):
        p = TuflowPath(uri)
        with warnings.catch_warnings():
            # No-CRS warning is expected when projection_wkt is None (intentionally unprojected).
            warnings.filterwarnings('ignore', message=".*crs.*was not provided.*", category=UserWarning)
            # SHP field name truncation is an inherent limitation; callers using SHP accept it.
            warnings.filterwarnings('ignore', message=".*Column names longer than 10 characters.*", category=UserWarning)
            with p.open_gis('w', geom_type, projection_wkt) as gis:
                for field in schema:
                    # Strip prec=-1 sentinel (means "not applicable") before passing to create_field
                    f = {k: v for k, v in field.items() if not (k == 'prec' and v == -1)}
                    gis.create_field(**f)
