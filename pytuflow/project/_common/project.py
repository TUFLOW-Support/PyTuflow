from __future__ import annotations

from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, ClassVar

from ..abc.project import BaseProject
from ..template.engine import TemplateEngine
from ..template.manager import TemplateManager
from ..config.settings import Settings
from .utils import _create_projection_file, _normalize_rendered, _variables_from_cf_path

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
    BASE_TEMPLATES: ClassVar[list[tuple[str, str]]] = []
    OUTPUT_DIRS: ClassVar[list[str]] = []
    EMPTIES_KEY: ClassVar[str] = ''
    SUPPORTED_GIS_FORMATS: ClassVar[frozenset[str]] = frozenset({'SHP', 'MIF', 'GPKG'})

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
        self.feature_names: list[str] = list(features or [])
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
        active_features = list(self.feature_names)

        features = self._get_feature_instances()
        feature_configs = {m.NAME: m._get_config() for m in features}

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
        for feature in features:
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
            secondary_cfs = self._load_secondary_cfs(main_cf, main_cf_path, features)
            control_files = {self.MAIN_CF_EXT: main_cf, **secondary_cfs}

            for feature in features:
                feature.apply_to_control_files(control_files, variables)

            main_cf.write('inplace')
            for cf in secondary_cfs.values():
                if getattr(cf, 'dirty', False):
                    cf.write('inplace')

        return self.output_dir

    @classmethod
    def insert_feature_into(cls, feature_name: str, cf_path: str | Path, **kwargs):
        """Inserts a feature into an existing project.
        
        Parameters
        ----------
        feature_name : str
            Name of the feature to insert
        cf_path : str | Path
            Path to the control file to insert the feature into. This should either a TCF or FVC,
            and not an ancillary control file such as the TGC or FVWQ.
        """
        import pytuflow
        cf_path = Path(cf_path)
        project_dir = cf_path.parent.parent  # runs/ → project root

        registry = cls.get_available_features()
        if feature_name not in registry:
            raise ValueError(
                f"Unknown feature '{feature_name}'. Available: {list(registry.keys())}"
            )

        feature_cls = registry[feature_name]
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

        engine = TemplateEngine()
        manager = TemplateManager(cls.ENGINE_TYPE)
        feature_configs = {feature_name: feature_config}

        for template_key, output_rel in feature.get_template_files(variables):
            rendered_out = Template(output_rel).safe_substitute(variables)
            out_path = project_dir / rendered_out
            if not out_path.exists():
                text = manager.get_template(template_key)
                rendered_text = engine.render(text, variables, [feature_name], feature_configs)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(rendered_text, encoding='utf-8')

        main_cf = getattr(pytuflow, cls.MAIN_CF_CLASS)(cf_path)
        secondary_cfs = cls._load_secondary_cfs_cls(main_cf, cf_path, [feature])
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
        for name in manager.list_feature_configs():
            dyn_cls = type(
                f'{name.title()}feature',
                (base_cls,),
                {'NAME': name, 'DISPLAY_NAME': name.replace('_', ' ').title()},
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

    def _get_feature_instances(self):
        """Return sorted feature instances (by sort_order ascending)."""
        registry = self.get_available_features()
        instances = []
        for name in self.feature_names:
            if name not in registry:
                raise ValueError(
                    f"Unknown feature '{name}'. Available: {list(registry.keys())}"
                )
            instances.append(registry[name]())
        instances.sort(key=lambda m: m._get_config().get('sort_order', 50))
        return instances

    def _load_secondary_cfs(self, main_cf, main_cf_path: Path, features) -> dict:
        """Load secondary control files referenced by *main_cf*.

        Override in subclasses that have secondary CFs (e.g. HPC has TGC/TBC).
        The default implementation returns an empty dict (no secondary CFs).
        """
        return {}

    @classmethod
    def _load_secondary_cfs_cls(cls, main_cf, main_cf_path: Path, features) -> dict:
        """Class-level variant of :meth:`_load_secondary_cfs` for use in
        :meth:`insert_feature_into`.  Override in subclasses as needed."""
        return {}
