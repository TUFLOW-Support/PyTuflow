from __future__ import annotations

import re
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING

from ..abc.project import BaseProject
from ..config.settings import Settings
from ..hpc.modules._base import _normalize_slashes
from ..template.engine import TemplateEngine
from ..template.manager import TemplateManager

if TYPE_CHECKING:
    pass

# Registry of available HPC modules
_MODULE_REGISTRY: dict[str, type] = {}

# Maps CF type key → TCF command lhs that references it, and the pytuflow class to use.
_CF_TYPE_MAP: dict[str, dict] = {
    'tgc': {'lhs': 'geometry control file', 'class': 'TGC'},
    'tbc': {'lhs': 'bc control file', 'class': 'TBC'},
    'ecf': {'lhs': 'estry control file', 'class': 'ECF'},
    'qcf': {'lhs': 'quadtree control file', 'class': 'QCF'},
    'adcf': {'lhs': 'ad control file', 'class': 'ADCF'},
}


def _register_modules():
    from .modules.estry import EstryModule
    from .modules.quadtree import QuadtreeModule
    from .modules.soils import SoilsModule
    from .modules.ad import ADModule
    from .modules.toc import TOCModule
    from .modules.rf import RFModule
    from .modules.events import EventsModule
    from .modules.sgs import SGSModule
    from .modules.po import POModule
    from .modules.tutorial import TutorialModule
    _MODULE_REGISTRY.update({
        'estry': EstryModule,
        'quadtree': QuadtreeModule,
        'soils': SoilsModule,
        'ad': ADModule,
        'toc': TOCModule,
        'rf': RFModule,
        'events': EventsModule,
        'sgs': SGSModule,
        'po': POModule,
        'tutorial': TutorialModule,
    })


def get_available_modules() -> dict[str, type]:
    if not _MODULE_REGISTRY:
        _register_modules()
    return dict(_MODULE_REGISTRY)


# Base templates that are always created
_BASE_TEMPLATES = [
    ('runs/${model_name}_${iter}.tcf', 'runs/${model_name}_${iter}.tcf'),
    ('model/${model_name}_${iter}.tgc', 'model/${model_name}_${iter}.tgc'),
    ('model/${model_name}_${iter}.tbc', 'model/${model_name}_${iter}.tbc'),
    ('bc_dbase/bc_dbase.csv', 'bc_dbase/bc_dbase.csv'),
    ('model/${model_name}_mat.csv', 'model/${model_name}_mat.csv'),
]


class HPCProject(BaseProject):

    def __init__(
        self,
        name: str,
        output_dir: str | Path,
        modules: list[str] | None = None,
        *,
        crs: str,
        iter: str | None = None,
        gis_format: str | None = None,
        cell_size: str | float | None = None,
        engine: str | None = None,
        hardware: str | None = None,
        map_output_formats: list[str] | None = None,
        output_formats: dict | None = None,
        create_empties: bool = True,
        **kwargs,
    ):
        self.name = name
        self.output_dir = Path(output_dir)
        self.module_names: list[str] = list(modules or [])
        self.create_empties = create_empties
        self.crs = crs

        # Normalize gis_format to uppercase (SHP, GPKG, MIF)
        if gis_format is not None:
            gis_format = gis_format.upper()

        overrides = {k: v for k, v in {
            'model_name': name,
            'iter': iter,
            'gis_format': gis_format,
            'cell_size': str(cell_size) if cell_size is not None else None,
            'map_output_formats': map_output_formats,
            'output_formats': output_formats,
            'engine': engine,
            'hardware': hardware,
            **kwargs,
        }.items() if v is not None}

        self.settings = Settings(**overrides)
        self._engine = TemplateEngine()
        self._manager = TemplateManager('hpc')

    def validate(self) -> list[str]:
        errors = []
        if not self.name:
            errors.append("'name' must be provided")
        if not self.output_dir:
            errors.append("'output_dir' must be provided")
        return errors

    def create(self) -> Path:
        errors = self.validate()
        if errors:
            raise ValueError('\n'.join(errors))

        variables = dict(self.settings._settings)
        variables['model_name'] = self.name
        active_modules = list(self.module_names)

        # Load and sort module instances (sort_order controls render + apply order)
        modules = self._get_module_instances()
        module_configs = {m.NAME: m._get_config() for m in modules}

        # Create output directories
        for d in ['runs', 'model', 'bc_dbase', 'results', 'check', 'runs/log']:
            (self.output_dir / d).mkdir(parents=True, exist_ok=True)

        # Create empty GIS files (unless explicitly disabled)
        if self.create_empties:
            from ..template.empties import TuflowEmptyFiles
            gis_format = variables.get('gis_format', 'SHP')
            empties_dir = self.output_dir / 'model' / 'gis' / 'empty'
            empties_dir.mkdir(parents=True, exist_ok=True)
            TuflowEmptyFiles('hpc', gis_format, self.crs).write_empties(empties_dir)

        # Create projection / spatial database file under model/gis/
        gis_dir = self.output_dir / 'model' / 'gis'
        gis_dir.mkdir(parents=True, exist_ok=True)
        _create_projection_file(gis_dir, variables.get('gis_format', 'SHP'), self.name, variables.get('iter', '001'), self.crs)

        # Render and write base templates (pass module configs so ##COMMANDS## resolves)
        tcf_path = None
        for template_key, output_rel in _BASE_TEMPLATES:
            rendered_out = Template(output_rel).safe_substitute(variables)
            text = self._manager.get_template(template_key)
            rendered_text = self._engine.render(text, variables, active_modules, module_configs)
            rendered_text = _normalize_rendered(rendered_text)
            out_path = self.output_dir / rendered_out
            out_path.write_text(rendered_text, encoding='utf-8')
            if template_key.startswith('runs/') and template_key.endswith('.tcf'):
                tcf_path = out_path

        # Render and write module template files
        for module in modules:
            for template_key, output_rel in module.get_template_files(variables):
                rendered_out = Template(output_rel).safe_substitute(variables)
                text = self._manager.get_template(template_key)
                rendered_text = self._engine.render(text, variables, active_modules, module_configs)
                rendered_text = _normalize_rendered(rendered_text)
                out_path = self.output_dir / rendered_out
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(rendered_text, encoding='utf-8')

        # Apply modules to control files (already-exists check makes this a no-op
        # for commands the template already rendered; handles fallback for insert)
        if tcf_path is not None:
            from pytuflow import TCF
            tcf = TCF(tcf_path)
            needed_types = _needed_cf_types(modules)
            secondary_cfs = _load_secondary_cfs(tcf, tcf_path, needed_types)
            control_files = {'tcf': tcf, **secondary_cfs}

            for module in modules:
                module.apply_to_control_files(control_files, variables)

            tcf.write('inplace')

        return self.output_dir

    def insert_module(self, module_name: str) -> None:
        variables = dict(self.settings._settings)
        variables['model_name'] = self.name

        tcf_rel = Template('runs/${model_name}_${iter}.tcf').safe_substitute(variables)
        tcf_path = self.output_dir / tcf_rel
        if not tcf_path.exists():
            raise FileNotFoundError(f"TCF not found: {tcf_path}")

        self.__class__.insert_module_into(module_name, tcf_path, **{
            'model_name': self.name,
            'iter': variables.get('iter', '001'),
        })
        if module_name not in self.module_names:
            self.module_names.append(module_name)

    @classmethod
    def insert_module_into(cls, module_name: str, tcf_path: str | Path, **kwargs) -> None:
        from pytuflow import TCF
        tcf_path = Path(tcf_path)
        project_dir = tcf_path.parent.parent  # runs/ -> project root

        registry = get_available_modules()
        if module_name not in registry:
            raise ValueError(
                f"Unknown module '{module_name}'. Available: {list(registry.keys())}"
            )

        module_cls = registry[module_name]
        module = module_cls()
        module_config = module._get_config()

        # Build variables from TCF path + overrides
        variables = _variables_from_tcf_path(tcf_path, **kwargs)
        settings = Settings(
            model_name=variables.get('model_name', ''),
            **{k: v for k, v in kwargs.items() if v},
        )
        variables = dict(settings._settings)
        if 'model_name' in kwargs:
            variables['model_name'] = kwargs['model_name']

        # Create module template files (pass module config so ##COMMANDS## resolves)
        engine = TemplateEngine()
        manager = TemplateManager('hpc')
        module_configs = {module_name: module_config}

        for template_key, output_rel in module.get_template_files(variables):
            rendered_out = Template(output_rel).safe_substitute(variables)
            out_path = project_dir / rendered_out
            if not out_path.exists():
                text = manager.get_template(template_key)
                rendered_text = engine.render(text, variables, [module_name], module_configs)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(rendered_text, encoding='utf-8')

        # Apply module to TCF and any secondary CFs
        tcf = TCF(tcf_path)
        needed_types = _needed_cf_types([module])
        secondary_cfs = _load_secondary_cfs(tcf, tcf_path, needed_types)
        control_files = {'tcf': tcf, **secondary_cfs}

        module.apply_to_control_files(control_files, variables)

        tcf.write('inplace')
        for cf in secondary_cfs.values():
            if cf.dirty:
                cf.write('inplace')

    def _get_module_instances(self):
        """Return module instances sorted by sort_order (ascending)."""
        registry = get_available_modules()
        instances = []
        for name in self.module_names:
            if name not in registry:
                raise ValueError(
                    f"Unknown module '{name}'. Available: {list(registry.keys())}"
                )
            instances.append(registry[name]())
        instances.sort(key=lambda m: m._get_config().get('sort_order', 50))
        return instances


def _needed_cf_types(modules) -> set[str]:
    """Collect all non-TCF target_cf values across all modules' command blocks."""
    needed = set()
    for module in modules:
        config = module._get_config()
        for block in config.get('command_blocks', []):
            target = block.get('target_cf', 'tcf')
            if target != 'tcf':
                needed.add(target)
    return needed


def _load_secondary_cfs(tcf, tcf_path: Path, needed_types: set[str]) -> dict:
    """Load secondary CFs (TGC, TBC, etc.) referenced in the TCF."""
    import pytuflow as pt

    cf_classes = {k: getattr(pt, v['class']) for k, v in _CF_TYPE_MAP.items()}
    result = {}
    for cf_type in needed_types:
        if cf_type not in _CF_TYPE_MAP:
            continue
        lhs = _CF_TYPE_MAP[cf_type]['lhs']
        inps = tcf.find_input(lhs=lhs, recursive=False)
        if not inps:
            continue
        cf_rel = str(inps[0].rhs).replace('\\', '/')
        cf_path = (tcf_path.parent / cf_rel).resolve()
        if cf_path.exists():
            result[cf_type] = cf_classes[cf_type](cf_path)
    return result


def _variables_from_tcf_path(tcf_path: Path, **overrides) -> dict:
    """Try to infer model_name and iter from TCF filename."""
    stem = tcf_path.stem  # e.g. mymodel_001
    variables = {}
    m = re.match(r'^(.+)_(\d+)$', stem)
    if m:
        variables['model_name'] = m.group(1)
        variables['iter'] = m.group(2)
    else:
        variables['model_name'] = stem
        variables['iter'] = '001'
    variables.update({k: v for k, v in overrides.items() if v is not None})
    return variables


def _normalize_rendered(text: str) -> str:
    """Apply OS-native path separators to every line of a rendered template.

    Delegates to ``_normalize_slashes`` so the behaviour is identical to what
    ``_apply_block`` does when inserting module commands at runtime.
    """
    return '\n'.join(_normalize_slashes(line) for line in text.split('\n'))


def _create_projection_file(gis_dir: Path, gis_format: str, model_name: str, iter_: str, crs: str) -> None:
    """Create a projection / spatial-database reference file in *gis_dir*.

    * SHP → ``projection.shp`` (empty Point layer carrying the CRS)
    * MIF → ``projection.mif`` (same)
    * GPKG → ``{model_name}_{iter}.gpkg`` with a ``projection`` layer
    """
    import warnings
    from ..._tmf import TuflowPath

    fmt = gis_format.upper()
    if fmt == 'SHP':
        uri = f'{gis_dir / "projection.shp"} >> projection'
    elif fmt == 'MIF':
        uri = f'{gis_dir / "projection.mif"} >> projection'
    elif fmt == 'GPKG':
        uri = f'{gis_dir / f"{model_name}_{iter_}.gpkg"} >> projection'
    else:
        return  # unknown format — skip silently

    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message=".*Column names longer than 10 characters.*", category=UserWarning)
        p = TuflowPath(uri)
        with p.open_gis('w', 'Point', crs):
            pass  # no fields or features needed — CRS is embedded in the file
