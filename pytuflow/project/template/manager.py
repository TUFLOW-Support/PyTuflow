import shutil
from pathlib import Path

CACHE_ROOT = Path.home() / '.tuflow_model_files' / 'project_templates'


class TemplateManager:
    def __init__(self, engine_type: str = 'hpc'):
        self.engine_type = engine_type
        self._bundled_dir = Path(__file__).parent.parent / 'data' / 'templates' / engine_type
        self._cache_dir = CACHE_ROOT / engine_type

    def init_cache(self, force: bool = False) -> None:
        if self._cache_dir.exists() and not force:
            return
        if self._cache_dir.exists() and force:
            shutil.rmtree(self._cache_dir)
        shutil.copytree(self._bundled_dir, self._cache_dir)

    def get_template(self, relative_key: str) -> str:
        self.init_cache()
        path = self._cache_dir / relative_key
        return path.read_text(encoding='utf-8')

    def list_templates(self) -> list[str]:
        self.init_cache()
        result = []
        for p in sorted(self._cache_dir.rglob('*')):
            if p.is_file():
                result.append(str(p.relative_to(self._cache_dir)))
        return result

    def reset_cache(self) -> None:
        self.init_cache(force=True)
