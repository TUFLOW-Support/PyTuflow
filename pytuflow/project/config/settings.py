import json
from pathlib import Path
from typing import Any

from .defaults import FACTORY_DEFAULTS, FACTORY_HPC_DEFAULTS

CACHE_ROOT = Path.home() / '.tuflow_model_files' / 'project_templates'


class Settings:
    
    def __init__(self, **overrides):
        settings = {}
        settings.update(FACTORY_DEFAULTS)

        # Try loading user defaults.json
        user_defaults = CACHE_ROOT / 'defaults.json'
        if user_defaults.exists():
            with open(user_defaults) as f:
                settings.update(json.load(f))

        settings.update(FACTORY_HPC_DEFAULTS)

        # Try loading user hpc_defaults.json
        user_hpc_defaults = CACHE_ROOT / 'hpc' / 'hpc_defaults.json'
        if user_hpc_defaults.exists():
            with open(user_hpc_defaults) as f:
                settings.update(json.load(f))

        settings.update({k: v for k, v in overrides.items() if v is not None})

        self._settings = settings

        # Compute output_commands from map_output_formats (kept for legacy string use)
        fmts = self._settings.get('map_output_formats', ['XMDF'])
        if isinstance(fmts, str):
            fmts = [fmts]
        self._settings['output_commands'] = '\n'.join(
            f'Map Output Format == {fmt}' for fmt in fmts
        )

    def __getattr__(self, name: str) -> Any:
        try:
            return self._settings[name]
        except KeyError:
            raise AttributeError(f"Settings has no attribute '{name}'")

    def get(self, name: str, default=None) -> Any:
        return self._settings.get(name, default)

    def as_dict(self) -> dict:
        """Return a string-safe copy of settings (lists joined, all values str)."""
        result = {}
        for k, v in self._settings.items():
            if isinstance(v, list):
                result[k] = ', '.join(str(i) for i in v)
            else:
                result[k] = str(v)
        return result
