from __future__ import annotations

from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, ClassVar

from ..abc.project import BaseProject
from ..template.engine import TemplateEngine
from ..template.manager import TemplateManager
from ..config.settings import Settings
from .utils import _create_projection_file, _normalize_rendered, _variables_from_cf_path, _parse_filter

if TYPE_CHECKING:
    pass


class BaseEngineProject(BaseProject):
    """Common base for HPC and FV project generators.

    Subclasses set class-level attributes to customise behaviour without
    duplicating the create / insert workflow.

    Class attributes
    ----------------
    ENGINE_TYPE : str
        Engine identifier used by :class:`TemplateManager` (``'hpc'`` or ``'fv'``).
    MAIN_CF_EXT : str
        File extension for the primary control file (``'tcf'`` or ``'fvc'``).
    MAIN_CF_SUBDIR : str
        Subdirectory of the project root that contains the primary control file.
    MAIN_CF_CLASS : str
        pytuflow class name used to load the primary control file (e.g. ``'TCF'``).
    BASE_TEMPLATES : list[tuple[str, str]]
        ``(template_key, output_rel)`` pairs always rendered during ``create()``.
    OUTPUT_DIRS : list[str]
        Directories created relative to ``output_dir`` during ``create()``.
    EMPTIES_KEY : str
        Engine key passed to :class:`TuflowEmptyFiles` (empty string disables empties).
    SUPPORTED_GIS_FORMATS : frozenset[str]
        Allowed uppercase GIS format names; validated in :meth:`validate`.
    """

    ENGINE_TYPE: ClassVar[str] = ''
    MAIN_CF_EXT: ClassVar[str] = ''
    MAIN_CF_SUBDIR: ClassVar[str] = 'runs'
    MAIN_CF_CLASS: ClassVar[str] = ''
    OUTPUT_DIRS: ClassVar[list[str]] = []
    EMPTIES_KEY: ClassVar[str] = ''
    SUPPORTED_GIS_FORMATS: ClassVar[frozenset[str]] = frozenset({'SHP', 'MIF', 'GPKG'})
    BASE_TEMPLATES: ClassVar[list[tuple[str, str]]] = []
    CF_TYPE_MAP: ClassVar = {}

    def __init__(
        self,
        name: str,
        output_dir: str | Path,
        features: list[str] | None = None,
        *,
        crs: str,
        create_empties: bool = True,
        **kwargs,
    ):
        self.name = name
        self.output_dir = Path(output_dir)
        # Each element is either a plain feature name (str) or a dict with
        # 'name' key plus per-instance variable overrides.
        self.feature_names: list[str | dict] = list(features or [])
        self.create_empties = create_empties
        self.crs = crs

        # Normalize gis_format to uppercase (SHP, MIF, GPKG)
        if 'gis_format' in kwargs and kwargs['gis_format'] is not None:
            kwargs['gis_format'] = kwargs['gis_format'].upper()

        overrides = {k: v for k, v in {'model_name': name, **kwargs}.items() if v is not None}
        self.settings = Settings(engine_type=self.ENGINE_TYPE, **overrides)
        self._engine = TemplateEngine()
        self._manager = TemplateManager(self.ENGINE_TYPE)

    # ------------------------------------------------------------------
    # BaseProject interface
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Validates the class inputs. Should be run prior to running :meth:`~pytuflow.HPCProject.create`.
        
        Returns
        -------
        list[str]
            List of error messages.
        """
        errors = []
        if not self.name:
            errors.append("'name' must be provided")
        if not self.output_dir:
            errors.append("'output_dir' must be provided")
        gis_format = self.settings._settings.get('gis_format', 'SHP').upper()
        if gis_format not in self.SUPPORTED_GIS_FORMATS:
            errors.append(
                f"GIS format '{gis_format}' is not supported for {self.ENGINE_TYPE.upper()}. "
                f"Supported formats: {sorted(self.SUPPORTED_GIS_FORMATS)}"
            )
        return errors

    def create(self) -> Path:
        """The execuation step when creating a project. This method copies template files, fills in variables, and
        parses the control files and follows directives.
        
        Returns
        -------
        Path
            Path to the output directory where the model was created.
        """
        errors = self.validate()
        if errors:
            raise ValueError('\n'.join(errors))

        variables = dict(self.settings._settings)
        variables['model_name'] = self.name
        # Build active_features list of plain names for template ##IF## directives
        active_features = [
            entry.get('name', '') if isinstance(entry, dict) else entry
            for entry in self.feature_names
        ]

        feature_pairs = self._get_feature_instances()
        features = [f for f, _ in feature_pairs]
        feature_configs = {f.NAME: f._get_config() for f in features}

        # Create output directories
        for d in self.OUTPUT_DIRS:
            (self.output_dir / d).mkdir(parents=True, exist_ok=True)

        # Create empty GIS files (unless explicitly disabled or no key configured)
        if self.create_empties and self.EMPTIES_KEY:
            from ..template.empties import TuflowEmptyFiles
            gis_format = variables.get('gis_format', 'SHP')
            empties_dir = self.output_dir / 'model' / 'gis' / 'empty'
            empties_dir.mkdir(parents=True, exist_ok=True)
            TuflowEmptyFiles(self.EMPTIES_KEY, gis_format, self.crs).write_empties(empties_dir)

        # Create projection / spatial database file under model/gis/
        gis_dir = self.output_dir / 'model' / 'gis'
        gis_dir.mkdir(parents=True, exist_ok=True)
        _create_projection_file(
            gis_dir,
            variables.get('gis_format', 'SHP'),
            self.name,
            variables.get('iter', '001'),
            self.crs,
        )

        # Render and write base templates
        main_cf_path = None
        for template_key, output_rel in self.BASE_TEMPLATES:
            rendered_out = Template(output_rel).safe_substitute(variables)
            text = self._manager.get_template(template_key)
            rendered_text = self._engine.render(text, variables, active_features, feature_configs)
            rendered_text = _normalize_rendered(rendered_text)
            out_path = self.output_dir / rendered_out
            out_path.write_text(rendered_text, encoding='utf-8')
            if (
                template_key.startswith(f'{self.MAIN_CF_SUBDIR}/')
                and template_key.endswith(f'.{self.MAIN_CF_EXT}')
            ):
                main_cf_path = out_path

        # Render and write feature template files
        for feature, _overrides in feature_pairs:
            for template_key, output_rel in feature.get_template_files(variables):
                rendered_out = Template(output_rel).safe_substitute(variables)
                text = self._manager.get_template(template_key)
                rendered_text = self._engine.render(text, variables, active_features, feature_configs)
                rendered_text = _normalize_rendered(rendered_text)
                out_path = self.output_dir / rendered_out
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(rendered_text, encoding='utf-8')

        # Apply features to control files
        if main_cf_path is not None:
            import pytuflow
            main_cf = getattr(pytuflow, self.MAIN_CF_CLASS)(main_cf_path)
            secondary_cfs = self._load_secondary_cfs(main_cf, features)
            control_files = {self.MAIN_CF_EXT: main_cf, **secondary_cfs}

            for feature, overrides in feature_pairs:
                merged_vars = {**variables, **overrides} if overrides else variables
                feature.apply_to_control_files(control_files, merged_vars)

            main_cf.write('inplace')
            for cf in secondary_cfs.values():
                if getattr(cf, 'dirty', False):
                    cf.write('inplace')

        return self.output_dir

    @classmethod
    def insert_feature_into(
        cls,
        feature_name: str | dict,
        cf_path: str | Path,
        **kwargs,
    ):
        """Inserts a feature into an existing project.

        Parameters
        ----------
        feature_name : str | dict
            Name of the feature to insert, or a dict with ``'name'`` plus
            per-instance variable overrides (only meaningful for features
            with ``allow_multiple: true`` blocks).
        cf_path : str | Path
            Path to the control file to insert the feature into. This should
            either be a TCF or FVC, not an ancillary CF such as TGC or FVWQ.
        """
        # Normalise feature_name → (name, overrides)
        if isinstance(feature_name, dict):
            name = feature_name.get('name', '')
            instance_overrides = {k: v for k, v in feature_name.items() if k != 'name'}
        else:
            name = feature_name
            instance_overrides = {}

        import pytuflow
        cf_path = Path(cf_path)
        project_dir = cf_path.parent.parent  # runs/ → project root

        registry = cls.get_available_features()
        if name not in registry:
            raise ValueError(
                f"Unknown feature '{name}'. Available: {list(registry.keys())}"
            )

        feature_cls = registry[name]
        feature = feature_cls()
        feature_config = feature._get_config()

        variables = _variables_from_cf_path(cf_path, **kwargs)
        settings = Settings(
            engine_type=cls.ENGINE_TYPE,
            model_name=variables.get('model_name', ''),
            **{k: v for k, v in kwargs.items() if v},
        )
        variables = dict(settings._settings)
        if 'model_name' in kwargs:
            variables['model_name'] = kwargs['model_name']

        # Merge per-instance overrides last so they win over global vars
        if instance_overrides:
            variables = {**variables, **instance_overrides}

        engine = TemplateEngine()
        manager = TemplateManager(cls.ENGINE_TYPE)
        feature_configs = {name: feature_config}

        for template_key, output_rel in feature.get_template_files(variables):
            rendered_out = Template(output_rel).safe_substitute(variables)
            out_path = project_dir / rendered_out
            if not out_path.exists():
                text = manager.get_template(template_key)
                rendered_text = engine.render(text, variables, [name], feature_configs)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(rendered_text, encoding='utf-8')

        main_cf = getattr(pytuflow, cls.MAIN_CF_CLASS)(cf_path)
        secondary_cfs = cls._load_secondary_cfs(main_cf, [feature])
        control_files = {cls.MAIN_CF_EXT: main_cf, **secondary_cfs}

        feature.apply_to_control_files(control_files, variables)

        main_cf.write('inplace')
        for cf in secondary_cfs.values():
            if getattr(cf, 'dirty', False):
                cf.write('inplace')

    # ------------------------------------------------------------------
    # feature registry
    # ------------------------------------------------------------------

    @classmethod
    def get_available_features(cls) -> dict[str, type]:
        """Discover all available features for this engine from JSON files.

        Returns
        -------
        dict[str, type]
            A dictionary of the available features with using the feature
            name as the key and the feature class as the value.
        """
        base_cls = cls._get_feature_base_class()
        manager = TemplateManager(cls.ENGINE_TYPE)
        result = {}
        for name, display_name in manager.list_feature_configs():
            dyn_cls = type(
                f'{name.title()}feature',
                (base_cls,),
                {'NAME': name, 'DISPLAY_NAME': display_name},
            )
            result[name] = dyn_cls
        return result

    @classmethod
    def _get_feature_base_class(cls):
        raise NotImplementedError(
            f"{cls.__name__} must implement _get_feature_base_class()"
        )

    # ------------------------------------------------------------------
    # Internal helpers (overridable by subclasses)
    # ------------------------------------------------------------------

    def _get_feature_instances(self) -> list[tuple]:
        """Return sorted ``(feature_instance, per_instance_overrides)`` pairs.

        Each element of :attr:`feature_names` is either a plain ``str`` (no
        overrides) or a ``dict`` with a ``'name'`` key plus any per-instance
        variable overrides.  Dicts are only meaningful for features whose
        blocks have ``allow_multiple: true`` — for other features the overrides
        are passed through but ``_apply_block`` will still respect the normal
        existence / duplicate checks.
        """
        registry = self.get_available_features()
        instances = []
        for entry in self.feature_names:
            if isinstance(entry, dict):
                name = entry.get('name', '')
                overrides = {k: v for k, v in entry.items() if k != 'name'}
            else:
                name = entry
                overrides = {}
            if name not in registry:
                raise ValueError(
                    f"Unknown feature '{name}'. Available: {list(registry.keys())}"
                )
            instances.append((registry[name](), overrides))
        instances.sort(key=lambda pair: pair[0]._get_config().get('sort_order', 50))
        return instances

    @classmethod
    def _load_secondary_cfs(cls, tcf, features) -> dict:
        """Load secondary CFs (TGC, TBC, etc.) referenced in the TCF."""
        import pytuflow as pt

        needed_types = cls._needed_cf_types(features)

        result = pt.AppendDict()
        for cf_type in needed_types:
            if cf_type not in cls.CF_TYPE_MAP:
                continue
            lhs = cls.CF_TYPE_MAP[cf_type]['lhs']
            pattern, is_regex, flags = _parse_filter(lhs)
            inps = tcf.find_input(lhs=pattern, recursive='similar', regex=is_regex, regex_flags=flags)
            if not inps:
                continue
            for inp in inps:
                if inp.cf:
                    result[cf_type] = inp.cf
        return result

    @classmethod
    def _needed_cf_types(cls, features) -> set[str]:
        """Collect all non-primary target_cf values across all features' command blocks."""
        needed = set()
        for feature in features:
            config = feature._get_config()
            for block in config.get('command_blocks', []):
                target = block.get('target_cf', cls.MAIN_CF_EXT)
                if target != 'tcf':
                    needed.add(target)
        return needed
