import json
import shutil
from pathlib import Path

CACHE_ROOT = Path.home() / '.tuflow_model_files' / 'project_templates'


class TemplateManager:
    def __init__(self, engine_type: str = 'hpc'):
        self.engine_type = engine_type
        self._bundled_templates_dir = Path(__file__).parent.parent / 'data' / 'templates' / engine_type
        self._bundled_modules_dir = Path(__file__).parent.parent / 'data' / 'modules' / engine_type
        self._cache_dir = CACHE_ROOT / engine_type
        self._cache_modules_dir = CACHE_ROOT / 'modules' / engine_type

    def init_cache(self, force: bool = False) -> None:
        """Copy bundled templates and module configs to the user cache on first use."""
        needs_templates = not self._cache_dir.exists() or force
        needs_modules = not self._cache_modules_dir.exists() or force

        if needs_templates:
            if self._cache_dir.exists():
                shutil.rmtree(self._cache_dir)
            shutil.copytree(self._bundled_templates_dir, self._cache_dir)

        if needs_modules and self._bundled_modules_dir.exists():
            if self._cache_modules_dir.exists():
                shutil.rmtree(self._cache_modules_dir)
            shutil.copytree(self._bundled_modules_dir, self._cache_modules_dir)

    def get_template(self, relative_key: str) -> str:
        """Read template text from cache (initialising cache first if needed)."""
        self.init_cache()
        path = self._cache_dir / relative_key
        return path.read_text(encoding='utf-8')

    def get_module_config(self, module_name: str) -> dict:
        """Load a module's JSON config from cache, falling back to bundled."""
        self.init_cache()
        cached = self._cache_modules_dir / f'{module_name}.json'
        if cached.exists():
            with open(cached, encoding='utf-8') as f:
                return json.load(f)
        # Fallback to bundled if cache not populated for this module
        bundled = self._bundled_modules_dir / f'{module_name}.json'
        if bundled.exists():
            with open(bundled, encoding='utf-8') as f:
                return json.load(f)
        return {}

    def list_templates(self) -> list[str]:
        self.init_cache()
        result = []
        for p in sorted(self._cache_dir.rglob('*')):
            if p.is_file():
                result.append(str(p.relative_to(self._cache_dir)))
        return result

    def list_module_configs(self) -> list[str]:
        """Return list of cached module config names (without .json extension)."""
        self.init_cache()
        if not self._cache_modules_dir.exists():
            return []
        return [p.stem for p in sorted(self._cache_modules_dir.glob('*.json'))]

    def reset_cache(self) -> None:
        self.init_cache(force=True)
