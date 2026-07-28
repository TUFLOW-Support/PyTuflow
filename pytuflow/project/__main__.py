"""CLI for pytuflow.project.

Usage:
    python -m pytuflow.project create --name NAME --output-dir DIR --crs EPSG:XXXX
                                       [--engine hpc|fv] [--features M1 M2 ...] [--<variable> VALUE ...]
    python -m pytuflow.project insert --tcf TCF_PATH --feature feature_NAME
    python -m pytuflow.project init-templates [--engine hpc|fv] [--force]
    python -m pytuflow.project list-features [--engine hpc|fv]

Dynamic variables (--<variable>) are discovered from defaults.json / hpc_defaults.json / fv_defaults.json
and can be extended by the user without modifying this file.
"""
import argparse
import json
import sys


# Fixed args that are NOT driven by defaults.json
_FIXED_ARGS = {'name', 'output_dir', 'output-dir', 'crs', 'features', 'create_empties', 'engine'}


def _get_engine_defaults(engine: str) -> tuple[dict, dict]:
    """Return (shared_defaults, engine_defaults) for the given engine."""
    from .config.defaults import FACTORY_DEFAULTS, FACTORY_HPC_DEFAULTS, FACTORY_FV_DEFAULTS
    if engine == 'fv':
        return FACTORY_DEFAULTS, FACTORY_FV_DEFAULTS
    return FACTORY_DEFAULTS, FACTORY_HPC_DEFAULTS


def _add_dynamic_args(parser, engine: str = 'hpc') -> list[str]:
    """Add one --arg per variable in the factory defaults.

    Returns a list of dest names for all dynamic args added.
    """
    shared_defaults, engine_defaults = _get_engine_defaults(engine)

    dests = []
    for defaults in (shared_defaults, engine_defaults):
        for key, value in defaults.items():
            if key.startswith('_') or key in _FIXED_ARGS:
                continue
            flag = f'--{key.replace("_", "-")}'
            dest = key
            if isinstance(value, dict):
                parser.add_argument(
                    flag, dest=dest, default=None, metavar='JSON',
                    help=f'{key} as a JSON object',
                )
            elif isinstance(value, list):
                parser.add_argument(flag, dest=dest, nargs='*', default=None)
            else:
                parser.add_argument(flag, dest=dest, default=None)
            dests.append(dest)
    return dests


def cmd_create(args, dynamic_dests: list[str]):
    engine = getattr(args, 'engine', 'hpc') or 'hpc'
    shared_defaults, engine_defaults = _get_engine_defaults(engine)
    all_defaults = {**shared_defaults, **engine_defaults}

    kwargs = {}
    for dest in dynamic_dests:
        val = getattr(args, dest, None)
        if val is None:
            continue
        if isinstance(all_defaults.get(dest), dict):
            try:
                val = json.loads(val)
            except json.JSONDecodeError as e:
                print(f"Invalid --{dest.replace('_', '-')} JSON: {e}", file=sys.stderr)
                sys.exit(1)
        kwargs[dest] = val

    if engine == 'fv':
        from .fv.project import FVProject as ProjectClass
    else:
        from .hpc.project import HPCProject as ProjectClass

    project = ProjectClass(
        name=args.name,
        output_dir=args.output_dir,
        features=args.features or [],
        crs=args.crs,
        **kwargs,
    )
    errors = project.validate()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        sys.exit(1)
    out = project.create()
    print(f"Project created: {out}")


def cmd_insert(args):
    engine = getattr(args, 'engine', 'hpc') or 'hpc'
    if engine == 'fv':
        from .fv.project import FVProject as ProjectClass
    else:
        from .hpc.project import HPCProject as ProjectClass
    ProjectClass.insert_feature_into(args.feature, args.cf)
    print(f"feature '{args.feature}' inserted into {args.cf}")


def cmd_init_templates(args):
    from .template.manager import TemplateManager
    engine = getattr(args, 'engine', 'hpc') or 'hpc'
    manager = TemplateManager(engine)
    manager.init_cache(force=getattr(args, 'force', False))
    print(f"Templates initialised at {manager._cache_dir}")


def cmd_list_features(args):
    engine = getattr(args, 'engine', 'hpc') or 'hpc'
    if engine == 'fv':
        from .fv.project import get_available_features
    else:
        from .hpc.project import get_available_features
    registry = get_available_features()
    if not registry:
        print(f"  (no {engine.upper()} features found)")
        return
    for name, cls in registry.items():
        print(f"  {name:12s}  {cls.DISPLAY_NAME}")


def main():
    parser = argparse.ArgumentParser(prog='python -m pytuflow.project')
    sub = parser.add_subparsers(dest='command')

    # create — fixed args + dynamic args from defaults
    p_create = sub.add_parser('create', help='Create a new project skeleton')
    p_create.add_argument('--engine', required=True, choices=['hpc', 'fv'],
                          help='TUFLOW engine type (default: hpc)')
    p_create.add_argument('--name', required=True, help='Model name')
    p_create.add_argument('--output-dir', required=True, dest='output_dir', help='Output directory')
    p_create.add_argument('--crs', required=True, help='Coordinate reference system (e.g. EPSG:32760)')
    p_create.add_argument('--features', nargs='*', default=[], help='Optional features to include')
    # We parse --engine first to determine which dynamic args to add.  For the
    # common case (hpc) we add HPC defaults; fv users pass --engine fv first.
    # To keep things simple, always add HPC defaults (they're ignored for FV).
    dynamic_dests = _add_dynamic_args(p_create, engine='hpc')
    # Also add FV-only args (those not already in HPC defaults)
    from .config.defaults import FACTORY_FV_DEFAULTS, FACTORY_HPC_DEFAULTS
    _fv_only_keys = set(FACTORY_FV_DEFAULTS) - set(FACTORY_HPC_DEFAULTS)
    from .config.defaults import FACTORY_DEFAULTS
    _fv_only_keys -= set(FACTORY_DEFAULTS) | _FIXED_ARGS
    for key in sorted(_fv_only_keys):
        value = FACTORY_FV_DEFAULTS[key]
        flag = f'--{key.replace("_", "-")}'
        if isinstance(value, dict):
            p_create.add_argument(flag, dest=key, default=None, metavar='JSON')
        elif isinstance(value, list):
            p_create.add_argument(flag, dest=key, nargs='*', default=None)
        else:
            p_create.add_argument(flag, dest=key, default=None)
        if key not in dynamic_dests:
            dynamic_dests.append(key)

    # insert
    p_insert = sub.add_parser('insert', help='Insert a feature into an existing project')
    p_insert.add_argument('--engine', default='hpc', choices=['hpc', 'fv'],
                          help='TUFLOW engine type (default: hpc)')
    p_insert.add_argument('--cf', required=True, help='Path to main control file (TCF or FVC)')
    p_insert.add_argument('--feature', required=True, help='feature name to insert')

    # init-templates
    p_init = sub.add_parser('init-templates', help='Initialise user template cache')
    p_init.add_argument('--engine', default='hpc', choices=['hpc', 'fv'])
    p_init.add_argument('--force', action='store_true', help='Overwrite existing cache')

    # list-features
    p_list = sub.add_parser('list-features', help='List available features')
    p_list.add_argument('--engine', default='hpc', choices=['hpc', 'fv'])

    args = parser.parse_args()

    if args.command == 'create':
        cmd_create(args, dynamic_dests)
    elif args.command == 'insert':
        cmd_insert(args)
    elif args.command == 'init-templates':
        cmd_init_templates(args)
    elif args.command == 'list-features':
        cmd_list_features(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
