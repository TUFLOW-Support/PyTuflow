import json
from pathlib import Path
from typing import Any

from .defaults import FACTORY_DEFAULTS, FACTORY_FV_DEFAULTS, FACTORY_HPC_DEFAULTS

CACHE_ROOT = Path.home() / '.tuflow_model_files' / 'project_templates'


class Settings:

    def __init__(self, engine_type: str = 'hpc', **overrides):
        settings = {}
        settings.update(FACTORY_DEFAULTS)

        # Try loading user defaults.json (shared across engines)
        user_defaults = CACHE_ROOT / 'defaults.json'
        if user_defaults.exists():
            with open(user_defaults) as f:
                settings.update(json.load(f))

        # Engine-specific factory defaults
        if engine_type == 'hpc':
            settings.update(FACTORY_HPC_DEFAULTS)
            user_engine_defaults = CACHE_ROOT / 'hpc' / 'hpc_defaults.json'
        elif engine_type == 'fv':
            settings.update(FACTORY_FV_DEFAULTS)
            user_engine_defaults = CACHE_ROOT / 'fv' / 'fv_defaults.json'
        else:
            user_engine_defaults = None

        # Try loading user engine-specific defaults
        if user_engine_defaults and user_engine_defaults.exists():
            with open(user_engine_defaults) as f:
                settings.update(json.load(f))

        settings.update({k: v for k, v in overrides.items() if v is not None})

        self._settings = settings
        # Track which keys were explicitly passed so _compute_output_settings
        # can resolve the output_formats vs map_output_formats priority.
        self._override_keys = {k for k, v in overrides.items() if v is not None}

        if engine_type == 'hpc':
            self._compute_output_settings()

    def _compute_output_settings(self) -> None:
        """Derive ``map_output_formats`` and ``output_format_setting_lines`` from
        ``output_formats``.

        Priority (highest wins):
        * ``output_formats`` explicitly passed → use dict; derive format name list.
        * ``map_output_formats`` explicitly passed (legacy) → use list; no per-format settings.
        * Neither explicitly passed → use ``output_formats`` from defaults if present,
          otherwise fall back to ``map_output_formats`` list from defaults.

        The computed ``output_format_setting_lines`` is a multi-line string of
        ``<FMT> Map Output <Key> == <value>`` commands ready for insertion into
        the TCF template via ``${output_format_setting_lines}``.
        """
        explicit_output_formats = 'output_formats' in self._override_keys
        explicit_map_formats = 'map_output_formats' in self._override_keys

        if explicit_map_formats and not explicit_output_formats:
            # Legacy override: list of format names, no per-format settings.
            fmts = self._settings.get('map_output_formats', ['XMDF'])
            if isinstance(fmts, str):
                fmts = [fmts]
            self._settings['map_output_formats'] = fmts
            self._settings['output_formats'] = {fmt: {} for fmt in fmts}
            self._settings['output_format_setting_lines'] = ''
            self._settings['map_output_formats_str'] = ' '.join(fmts)
            return

        # Use output_formats dict (either from override or defaults).
        output_formats = self._settings.get('output_formats')
        if output_formats and isinstance(output_formats, dict):
            self._settings['map_output_formats'] = list(output_formats.keys())
        else:
            # Ultimate fallback: bare map_output_formats list from defaults.
            fmts = self._settings.get('map_output_formats', ['XMDF'])
            if isinstance(fmts, str):
                fmts = [fmts]
            output_formats = {fmt: {} for fmt in fmts}
            self._settings['map_output_formats'] = fmts
            self._settings['output_formats'] = output_formats

        # Build per-format setting lines.
        lines: list[str] = []
        for fmt, fmt_settings in output_formats.items():
            if not isinstance(fmt_settings, dict):
                continue
            interval = fmt_settings.get('interval')
            data_types = fmt_settings.get('data_types')
            if interval is not None:
                lines.append(f'{fmt} Map Output Interval == {interval}')
            if data_types:
                if isinstance(data_types, list):
                    data_types = ' '.join(str(t) for t in data_types)
                lines.append(f'{fmt} Map Output Data Types == {data_types}')

        self._settings['output_format_setting_lines'] = '\n'.join(lines)
        # Space-joined string for the single "Map Output Formats ==" command.
        self._settings['map_output_formats_str'] = ' '.join(
            self._settings['map_output_formats']
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
            elif isinstance(v, dict):
                continue  # skip nested dicts (e.g. output_formats)
            else:
                result[k] = str(v)
        return result
