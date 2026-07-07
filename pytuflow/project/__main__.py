"""CLI for pytuflow.project.

Usage:
    python -m pytuflow.project create --name NAME --output-dir DIR [--modules M1 M2 ...]
                                       [--gis-format FMT] [--map-output-formats F1 F2 ...]
                                       [--cell-size N] [--iter ITER]
    python -m pytuflow.project insert --tcf TCF_PATH --module MODULE_NAME
    python -m pytuflow.project init-templates [--force]
    python -m pytuflow.project list-modules
"""
import argparse
import sys


def cmd_create(args):
    from .hpc.project import HPCProject
    project = HPCProject(
        name=args.name,
        output_dir=args.output_dir,
        modules=args.modules or [],
        iter=args.iter,
        gis_format=args.gis_format,
        cell_size=args.cell_size,
        map_output_formats=args.map_output_formats,
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

    # create
    p_create = sub.add_parser('create', help='Create a new HPC project skeleton')
    p_create.add_argument('--name', required=True, help='Model name')
    p_create.add_argument('--output-dir', required=True, dest='output_dir', help='Output directory')
    p_create.add_argument('--modules', nargs='*', default=[], help='Optional modules to include')
    p_create.add_argument('--gis-format', dest='gis_format', default=None)
    p_create.add_argument('--map-output-formats', dest='map_output_formats', nargs='*', default=None)
    p_create.add_argument('--cell-size', dest='cell_size', default=None)
    p_create.add_argument('--iter', default=None, help='Iteration string (e.g. 001)')

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
        cmd_create(args)
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
