"""CLI for pytuflow.project.

Usage:
    python -m pytuflow.project create --engine hpc|fv --name NAME --output-dir DIR --crs EPSG:XXXX
                                       [--recipe NAME|PATH|JSON]
                                       [--features M1 M2 ...] [--<variable> VALUE ...]
    python -m pytuflow.project insert --cf CF_PATH --feature FEATURE_NAME [--engine hpc|fv]
    python -m pytuflow.project init-templates [--engine hpc|fv] [--force]
    python -m pytuflow.project list-features [--engine hpc|fv]
    python -m pytuflow.project list-recipes [--engine hpc|fv]

When --recipe is given it sets the base features and variables.  Any --<variable>
flag on the CLI overwrites the same-named variable from the recipe.  Plain-string
--features entries overwrite the same feature name from the recipe; dict-style
--features entries (e.g. '{"name":"outputnc","suffix":"AD"}') are additive.

Dynamic variables (--<variable>) are discovered from defaults.json / hpc_defaults.json /
fv_defaults.json and can be extended by the user without modifying this file.
"""
import argparse
import json
import sys


# Fixed args that are NOT driven by defaults.json
_FIXED_ARGS = {'name', 'output_dir', 'output-dir', 'crs', 'features', 'recipe',
               'create_empties', 'engine'}


def _get_engine_defaults(engine: str) -> tuple[dict, dict]:
    """Return (shared_defaults, engine_defaults) for the given engine."""
    from .template.manager import TemplateManager
    manager = TemplateManager(engine)
    return manager.get_defaults()


def _add_dynamic_args(parser, engine: str = 'hpc') -> list[str]:
    """Add one --arg per variable in the factory defaults.

    Returns a list of dest names for all dynamic args added.
    """
    shared_defaults, engine_defaults = _get_engine_defaults(engine)

    dests = []
    defaults = shared_defaults.copy()
    defaults.update(engine_defaults)
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


def _parse_features_list(raw: list[str]) -> list[str | dict]:
    """Parse each element of ``--features``.

    Plain strings are kept as-is.  Anything that parses as a JSON object
    (``{...}``) is returned as a dict.
    """
    result = []
    for item in raw:
        stripped = item.strip()
        if stripped.startswith('{'):
            try:
                result.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                print(f"Invalid feature JSON '{stripped}': {e}", file=sys.stderr)
                sys.exit(1)
        else:
            result.append(stripped)
    return result


def _merge_recipe(
    recipe: dict,
    cli_features: list,
    cli_kwargs: dict,
) -> tuple[list, dict]:
    """Merge recipe base with CLI overrides.

    Rules:
    - Recipe variables are the base; CLI kwargs overwrite them by key.
    - Plain-string CLI features overwrite the same-named feature from the recipe.
    - Dict CLI features (allow_multiple style) are additive — appended after recipe features.

    Returns ``(merged_features, merged_vars)``.
    """
    recipe_features: list = list(recipe.get('features', []))
    recipe_vars: dict = dict(recipe.get('variables', {}))

    # Split CLI features into plain-string overrides and dict additives
    cli_plain = {f for f in cli_features if isinstance(f, str)}
    cli_dicts = [f for f in cli_features if isinstance(f, dict)]

    # Plain-string CLI features: replace same name in recipe list; any not in recipe are appended
    merged_features = []
    replaced = set()
    for rf in recipe_features:
        name = rf if isinstance(rf, str) else rf.get('name', '')
        if name in cli_plain:
            merged_features.append(name)   # CLI version (plain string) wins
            replaced.add(name)
        else:
            merged_features.append(rf)
    # Append plain-string CLI features not already in recipe
    for f in cli_features:
        if isinstance(f, str) and f not in replaced:
            merged_features.append(f)
    # Additive dict features always go at the end
    merged_features.extend(cli_dicts)

    # Variables: recipe base, CLI overwrites
    merged_vars = {**recipe_vars, **cli_kwargs}

    return merged_features, merged_vars


def cmd_create(args, dynamic_dests: list[str]):
    engine = getattr(args, 'engine', 'hpc') or 'hpc'
    shared_defaults, engine_defaults = _get_engine_defaults(engine)
    all_defaults = {**shared_defaults, **engine_defaults}

    # Collect explicitly supplied CLI variable overrides
    cli_kwargs = {}
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
        cli_kwargs[dest] = val

    cli_features = _parse_features_list(args.features or [])

    # Recipe base (optional)
    recipe_arg = getattr(args, 'recipe', None)
    if recipe_arg:
        from .template.manager import TemplateManager
        try:
            recipe = TemplateManager(engine).get_recipe(recipe_arg)
        except (FileNotFoundError, ValueError) as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        features, kwargs = _merge_recipe(recipe, cli_features, cli_kwargs)
    else:
        features, kwargs = cli_features, cli_kwargs

    if engine == 'fv':
        from .fv.project import FVProject as ProjectClass
    else:
        from .hpc.project import HPCProject as ProjectClass

    project = ProjectClass(
        name=args.name,
        output_dir=args.output_dir,
        features=features,
        crs=args.crs,
        **kwargs,
    )
    errors = project.validate()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        sys.exit(1)
    out = project.create()
    recipe_note = f" (recipe: {recipe_arg})" if recipe_arg else ""
    print(f"Project created{recipe_note}: {out}")


def cmd_insert(args, dynamic_dests: list[str]):
    engine = getattr(args, 'engine', 'hpc') or 'hpc'
    if engine == 'fv':
        from .fv.project import FVProject as ProjectClass
    else:
        from .hpc.project import HPCProject as ProjectClass

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

    feature_arg = _parse_features_list([args.feature])[0] if args.feature else args.feature
    ProjectClass.insert_feature_into(feature_arg, args.cf, **kwargs)
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


def cmd_list_recipes(args):
    engine = getattr(args, 'engine', 'hpc') or 'hpc'
    from .template.manager import TemplateManager
    manager = TemplateManager(engine)
    recipes = manager.list_recipes()
    if not recipes:
        print(f"  (no {engine.upper()} recipes found)")
        return
    for name, display_name, description in recipes:
        line = f"  {name:20s}  {display_name}"
        if description:
            line += f"  —  {description}"
        print(line)


def main():
    parser = argparse.ArgumentParser(prog='python -m pytuflow.project')
    sub = parser.add_subparsers(dest='command')

    # create — fixed args + dynamic args from defaults
    p_create = sub.add_parser('create', help='Create a new project skeleton')
    p_create.add_argument('--engine', required=True, choices=['hpc', 'fv'],
                          help='TUFLOW engine type')
    p_create.add_argument('--name', required=True, help='Model name')
    p_create.add_argument('--output-dir', required=True, dest='output_dir', help='Output directory')
    p_create.add_argument('--crs', required=True, help='Coordinate reference system (e.g. EPSG:32760)')
    p_create.add_argument('--features', nargs='*', default=[], help='Optional features to include')
    p_create.add_argument(
        '--recipe', default=None,
        help='Recipe name, path to a .json file, or inline JSON string to use as a base',
    )

    try:
        i = sys.argv.index('--engine')
        engine = sys.argv[i+1]
    except Exception:
        # --engine is mandatory; let argparser report the error later
        engine = ''

    create_dynamic_dests = _add_dynamic_args(p_create, engine=engine)

    # insert
    p_insert = sub.add_parser('insert', help='Insert a feature into an existing project')
    p_insert.add_argument('--engine', default='hpc', choices=['hpc', 'fv'],
                          help='TUFLOW engine type (default: hpc)')
    p_insert.add_argument('--cf', required=True, help='Path to main control file (TCF or FVC)')
    p_insert.add_argument('--feature', required=True, help='Feature name to insert')

    insert_dynamic_dests = _add_dynamic_args(p_insert, engine=engine)

    # init-templates
    p_init = sub.add_parser('init-templates', help='Initialise user template cache')
    p_init.add_argument('--engine', default='hpc', choices=['hpc', 'fv'])
    p_init.add_argument('--force', action='store_true', help='Overwrite existing cache')

    # list-features
    p_list = sub.add_parser('list-features', help='List available features')
    p_list.add_argument('--engine', default='hpc', choices=['hpc', 'fv'])

    # list-recipes
    p_list_recipes = sub.add_parser('list-recipes', help='List available recipes')
    p_list_recipes.add_argument('--engine', default='hpc', choices=['hpc', 'fv'])

    args = parser.parse_args()

    if args.command == 'create':
        cmd_create(args, create_dynamic_dests)
    elif args.command == 'insert':
        cmd_insert(args, insert_dynamic_dests)
    elif args.command == 'init-templates':
        cmd_init_templates(args)
    elif args.command == 'list-features':
        cmd_list_features(args)
    elif args.command == 'list-recipes':
        cmd_list_recipes(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
