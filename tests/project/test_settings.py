"""Tests for Settings class."""
import json
import pytest
from pathlib import Path

from pytuflow.project.config.settings import Settings
from pytuflow.project.config.defaults import FACTORY_DEFAULTS, FACTORY_HPC_DEFAULTS


class TestSettingsDefaults:
    def test_factory_defaults_present(self):
        s = Settings()
        assert s.iter == '001'
        assert s.gis_format == 'SHP'

    def test_hpc_defaults_present(self):
        s = Settings()
        assert s.map_output_formats == ['XMDF']

    def test_override_iter(self):
        s = Settings(iter='002')
        assert s.iter == '002'

    def test_override_gis_format(self):
        s = Settings(gis_format='GPKG')
        assert s.gis_format == 'GPKG'

    def test_override_map_output_formats(self):
        s = Settings(map_output_formats=['XMDF', 'SHP'])
        assert s.map_output_formats == ['XMDF', 'SHP']

    def test_none_override_ignored(self):
        s = Settings(iter=None)
        assert s.iter == '001'

    def test_output_commands_computed(self):
        s = Settings(map_output_formats=['XMDF', 'CSV'])
        assert 'Map Output Format == XMDF' in s.output_commands
        assert 'Map Output Format == CSV' in s.output_commands

    def test_output_commands_single(self):
        s = Settings()
        assert s.output_commands == 'Map Output Format == XMDF'


class TestSettingsAsDict:
    def test_returns_strings(self):
        s = Settings()
        d = s.as_dict()
        for v in d.values():
            assert isinstance(v, str)

    def test_list_joined(self):
        s = Settings(map_output_formats=['XMDF', 'CSV'])
        d = s.as_dict()
        assert d['map_output_formats'] == 'XMDF, CSV'

    def test_model_name_override(self):
        s = Settings(model_name='my_model')
        assert s.model_name == 'my_model'


class TestSettingsGetAttr:
    def test_missing_attr_raises(self):
        s = Settings()
        with pytest.raises(AttributeError):
            _ = s.nonexistent_key

    def test_get_with_default(self):
        s = Settings()
        assert s.get('nonexistent', 'fallback') == 'fallback'

    def test_get_existing(self):
        s = Settings()
        assert s.get('iter') == '001'


class TestSettingsUserDefaults:
    def test_user_defaults_json_loaded(self, tmp_path, monkeypatch):
        """User defaults.json should override factory defaults."""
        cache = tmp_path / 'project_templates'
        cache.mkdir(parents=True)
        (cache / 'defaults.json').write_text(json.dumps({'gis_format': 'GPKG'}))

        import pytuflow.project.config.settings as settings_mod
        monkeypatch.setattr(settings_mod, 'CACHE_ROOT', cache)

        s = Settings()
        assert s.gis_format == 'GPKG'

    def test_user_hpc_defaults_json_loaded(self, tmp_path, monkeypatch):
        """User hpc_defaults.json should override factory HPC defaults."""
        cache = tmp_path / 'project_templates'
        hpc_dir = cache / 'hpc'
        hpc_dir.mkdir(parents=True)
        (hpc_dir / 'hpc_defaults.json').write_text(
            json.dumps({'cell_size': '5'})
        )

        import pytuflow.project.config.settings as settings_mod
        monkeypatch.setattr(settings_mod, 'CACHE_ROOT', cache)

        s = Settings()
        assert s.cell_size == '5'
