import json
import shutil
from pathlib import Path
import logging

CACHE_ROOT = Path.home() / '.tuflow_model_files' / 'project_templates'
_BUNDLED_DATA_DIR = Path(__file__).parent.parent / 'data'


logger = logging.getLogger('pytuflow')


class TemplateManager:
    def __init__(self, engine_type: str = 'hpc'):
        self.engine_type = engine_type
        self._bundled_templates_dir = _BUNDLED_DATA_DIR / 'templates' / engine_type
        self._bundled_features_dir = _BUNDLED_DATA_DIR / 'features' / engine_type
        self._bundled_defaults = _BUNDLED_DATA_DIR / 'defaults.json'
        self._bundled_hpc_defaults = _BUNDLED_DATA_DIR / 'hpc_defaults.json'
        self._bundled_fv_defaults = _BUNDLED_DATA_DIR / 'fv_defaults.json'
        self._bundled_rules = _BUNDLED_DATA_DIR / 'rules.json'
        self._cache_dir = CACHE_ROOT / engine_type
        self._cache_features_dir = CACHE_ROOT / 'features' / engine_type
        self._cache_defaults = CACHE_ROOT / 'defaults.json'
        self._cache_hpc_defaults = CACHE_ROOT / 'hpc_defaults.json'
        self._cache_fv_defaults = CACHE_ROOT / 'fv_defaults.json'
        self._cache_rules = CACHE_ROOT / 'rules.json'

    def init_cache(self, force: bool = False) -> None:
        """Copy bundled templates and feature configs to the user cache on first use."""
        needs_templates = not self._cache_dir.exists() or force
        needs_features = not self._cache_features_dir.exists() or force
        needs_defaults = not self._cache_defaults.exists() or force
        needs_hpc_defaults = not self._cache_hpc_defaults.exists() or force
        needs_fv_defaults = not self._cache_fv_defaults.exists() or force
        needs_rules = not self._cache_rules.exists() or force

        if needs_templates:
            if self._cache_dir.exists():
                shutil.rmtree(self._cache_dir)
            shutil.copytree(self._bundled_templates_dir, self._cache_dir)

        if needs_features and self._bundled_features_dir.exists():
            if self._cache_features_dir.exists():
                shutil.rmtree(self._cache_features_dir)
            shutil.copytree(self._bundled_features_dir, self._cache_features_dir)

        if needs_defaults:
            if self._cache_defaults.exists():
                self._cache_defaults.unlink()
            shutil.copy2(str(self._bundled_defaults), str(self._cache_defaults))

        if needs_hpc_defaults:
            if self._cache_hpc_defaults.exists():
                self._cache_hpc_defaults.unlink()
            shutil.copy2(str(self._bundled_hpc_defaults), str(self._cache_hpc_defaults))

        if needs_fv_defaults:
            if self._cache_fv_defaults.exists():
                self._cache_fv_defaults.unlink()
            shutil.copy2(str(self._bundled_fv_defaults), str(self._cache_fv_defaults))

        if needs_rules:
            if self._cache_rules.exists():
                self._cache_rules.unlink()
            shutil.copy2(str(self._bundled_rules), str(self._cache_rules))

    def get_template(self, relative_key: str) -> str:
        """Read template text from cache (initialising cache first if needed).

        If the bundled template is newer than the cached copy (e.g. after a
        package update), the cached copy is refreshed from the bundle so
        callers always get up-to-date defaults.
        """
        self.init_cache()
        cached_path = self._cache_dir / relative_key
        bundled_path = self._bundled_templates_dir / relative_key
        if (
            bundled_path.exists()
            and cached_path.exists()
            and bundled_path.stat().st_mtime > cached_path.stat().st_mtime
        ):
            shutil.copy2(bundled_path, cached_path)
        return cached_path.read_text(encoding='utf-8')

    def get_feature_config(self, feature_name: str) -> dict:
        """Load a feature's JSON config from cache, falling back to bundled."""
        self.init_cache()
        cached = self._cache_features_dir / f'{feature_name}.json'
        if cached.exists():
            with open(cached, encoding='utf-8') as f:
                return json.load(f)
        bundled = self._bundled_features_dir / f'{feature_name}.json'
        if bundled.exists():
            with open(bundled, encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_rules(self) -> dict:
        """Load the shared placement rules from the bundled rules.json.

        Returns a dict keyed by rule name, each value having a ``commands``
        list of LHS strings that define a logical section in a control file.
        Falls back to an empty dict if the file is missing.
        """
        self.init_cache()
        if self._cache_rules.exists():
            with open(self._cache_rules, encoding='utf-8') as f:
                return json.load(f)
        if self._bundled_rules.exists():
            with open(self._bundled_rules, encoding='utf-8') as f:
                return json.load(f)
        return {}

    def list_templates(self) -> list[str]:
        self.init_cache()
        result = []
        for p in sorted(self._cache_dir.rglob('*')):
            if p.is_file():
                result.append(str(p.relative_to(self._cache_dir)))
        return result

    def list_feature_configs(self) -> list[tuple[str, str]]:
        """Return list of cached feature config names (without .json extension)."""
        self.init_cache()
        if not self._cache_features_dir.exists():
            return []
        configs = []
        for file in sorted(self._cache_features_dir.glob('*.json')):
            try:
                with open(file, 'r') as f:
                    d = json.load(f)
                configs.append((file.stem, d['display_name']))
            except Exception:
                logger.warning(f'Found feature {file.name} but could not load it or find diplay_name')
                continue
        return configs

    def get_defaults(self) -> tuple[dict, dict]:
        self.init_cache()
        defaults = {}
        if self._cache_defaults.exists():
            with open(self._cache_defaults, 'r') as fo:
                defaults = json.load(fo)
        elif self._bundled_defaults.exists():
            with open(self._bundled_defaults, 'r') as fo:
                defaults = json.load(fo)

        engine_defaults = {}
        if self.engine_type == 'hpc':
            if self._cache_hpc_defaults.exists():
                with open(self._cache_hpc_defaults, 'r') as fo:
                    engine_defaults = json.load(fo)
            if self._bundled_hpc_defaults.exists():
                with open(self._bundled_hpc_defaults, 'r') as fo:
                    engine_defaults = json.load(fo)
        elif self.engine_type == 'fv':
            if self._cache_fv_defaults.exists():
                with open(self._cache_fv_defaults, 'r') as fo:
                    engine_defaults = json.load(fo)
            if self._bundled_fv_defaults.exists():
                with open(self._bundled_fv_defaults, 'r') as fo:
                    engine_defaults = json.load(fo)

        return defaults, engine_defaults
        
    def reset_cache(self) -> None:
        self.init_cache(force=True)
