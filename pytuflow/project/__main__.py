"""CLI for pytuflow.project.

Usage:
    python -m pytuflow.project create --name NAME --output-dir DIR --crs EPSG:XXXX
                                       [--modules M1 M2 ...] [--<variable> VALUE ...]
    python -m pytuflow.project insert --tcf TCF_PATH --module MODULE_NAME
    python -m pytuflow.project init-templates [--force]
    python -m pytuflow.project list-modules

Dynamic variables (--<variable>) are discovered from defaults.json / hpc_defaults.json
and can be extended by the user without modifying this file.
"""
import argparse
import json
import sys


# Fixed args that are NOT driven by defaults.json
_FIXED_ARGS = {'name', 'output_dir', 'output-dir', 'crs', 'modules', 'create_empties'}


def _add_dynamic_args(parser) -> list[str]:
    """Add one --arg per variable in the factory defaults.

    Returns a list of dest names for all dynamic args added.
    """
    from .config.defaults import FACTORY_DEFAULTS, FACTORY_HPC_DEFAULTS

    dests = []
    for defaults in (FACTORY_DEFAULTS, FACTORY_HPC_DEFAULTS):
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
    from .hpc.project import HPCProject

    kwargs = {}
    for dest in dynamic_dests:
        val = getattr(args, dest, None)
        if val is None:
            continue
        # Detect if the arg was declared as JSON (dest corresponds to a dict default)
        from .config.defaults import FACTORY_DEFAULTS, FACTORY_HPC_DEFAULTS
        all_defaults = {**FACTORY_DEFAULTS, **FACTORY_HPC_DEFAULTS}
        if isinstance(all_defaults.get(dest), dict):
            try:
                val = json.loads(val)
            except json.JSONDecodeError as e:
                print(f"Invalid --{dest.replace('_', '-')} JSON: {e}", file=sys.stderr)
                sys.exit(1)
        kwargs[dest] = val

    project = HPCProject(
        name=args.name,
        output_dir=args.output_dir,
        modules=args.modules or [],
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
    from .hpc.project import HPCProject
    HPCProject.insert_module_into(args.module, args.tcf)
    print(f"Module '{args.module}' inserted into {args.tcf}")


def cmd_init_templates(args):
    from .template.manager import TemplateManager
    manager = TemplateManager('hpc')
    manager.init_cache(force=getattr(args, 'force', False))
    print(f"Templates initialised at {manager._cache_dir}")


def cmd_list_modules(args):
    from .hpc.project import get_available_modules
    registry = get_available_modules()
    for name, cls in registry.items():
        print(f"  {name:12s}  {cls.DISPLAY_NAME}")


def main():
    parser = argparse.ArgumentParser(prog='python -m pytuflow.project')
    sub = parser.add_subparsers(dest='command')

    # create — fixed args + dynamic args from defaults
    p_create = sub.add_parser('create', help='Create a new HPC project skeleton')
    p_create.add_argument('--name', required=True, help='Model name')
    p_create.add_argument('--output-dir', required=True, dest='output_dir', help='Output directory')
    p_create.add_argument('--crs', required=True, help='Coordinate reference system (e.g. EPSG:32760)')
    p_create.add_argument('--modules', nargs='*', default=[], help='Optional modules to include')
    dynamic_dests = _add_dynamic_args(p_create)

    # insert
    p_insert = sub.add_parser('insert', help='Insert a module into an existing project')
    p_insert.add_argument('--tcf', required=True, help='Path to TCF file')
    p_insert.add_argument('--module', required=True, help='Module name to insert')

    # init-templates
    p_init = sub.add_parser('init-templates', help='Initialise user template cache')
    p_init.add_argument('--force', action='store_true', help='Overwrite existing cache')

    # list-modules
    sub.add_parser('list-modules', help='List available modules')

    args = parser.parse_args()

    if args.command == 'create':
        cmd_create(args, dynamic_dests)
    elif args.command == 'insert':
        cmd_insert(args)
    elif args.command == 'init-templates':
        cmd_init_templates(args)
    elif args.command == 'list-modules':
        cmd_list_modules(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
