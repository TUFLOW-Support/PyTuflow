"""Tests for the recipe system: RecipeManager.get_recipe, _merge_recipe, and CLI --recipe flag."""
import json
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project_dir(tmp_path):
    return tmp_path / 'fv_project'


@pytest.fixture
def recipe_file(tmp_path):
    """A standalone recipe JSON file on disk."""
    data = {
        "display_name": "File Recipe",
        "description": "Loaded from a file path.",
        "variables": {"output_interval": "900."},
        "features": ["outputnc"],
    }
    p = tmp_path / 'my_recipe.json'
    p.write_text(json.dumps(data))
    return p


# ---------------------------------------------------------------------------
# RecipeManager.get_recipe — three input forms
# ---------------------------------------------------------------------------

class TestGetRecipeInputForms:
    def test_load_by_name_bundled_fv(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        recipe = mgr.get_recipe('2d_hd')
        assert 'features' in recipe
        assert 'display_name' in recipe

    def test_load_by_name_bundled_hpc(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('hpc')
        recipe = mgr.get_recipe('basic_2d')
        assert 'features' in recipe

    def test_load_by_file_path(self, recipe_file):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        recipe = mgr.get_recipe(str(recipe_file))
        assert recipe['variables']['output_interval'] == '900.'
        assert 'outputnc' in recipe['features']

    def test_load_by_json_string(self):
        from pytuflow.project.template.manager import TemplateManager
        inline = json.dumps({
            "display_name": "Inline",
            "variables": {"output_interval": "600."},
            "features": ["outputnc"],
        })
        mgr = TemplateManager('fv')
        recipe = mgr.get_recipe(inline)
        assert recipe['variables']['output_interval'] == '600.'

    def test_load_invalid_json_string_raises(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        with pytest.raises(ValueError, match='Invalid recipe JSON'):
            mgr.get_recipe('{not valid json')

    def test_load_nonexistent_name_raises(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        with pytest.raises(FileNotFoundError, match='water_quality'):
            mgr.get_recipe('water_quality')

    def test_load_wrong_engine_raises(self):
        """2d_hd is fv-only; looking it up under hpc should raise."""
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('hpc')
        with pytest.raises(FileNotFoundError, match='2d_hd'):
            mgr.get_recipe('2d_hd')

    def test_user_cache_overrides_bundled(self):
        from pytuflow.project.template.manager import TemplateManager, CACHE_ROOT
        cache_dir = CACHE_ROOT / 'recipes' / 'fv'
        cache_dir.mkdir(parents=True, exist_ok=True)
        custom = {"display_name": "Custom", "variables": {"output_interval": "9999."},
                  "features": []}
        override = cache_dir / '2d_hd.json'
        override.write_text(json.dumps(custom))
        try:
            recipe = TemplateManager('fv').get_recipe('2d_hd')
            assert recipe['variables']['output_interval'] == '9999.'
        finally:
            override.unlink(missing_ok=True)

    def test_user_cache_new_name_discovered(self):
        from pytuflow.project.template.manager import TemplateManager, CACHE_ROOT
        cache_dir = CACHE_ROOT / 'recipes' / 'fv'
        cache_dir.mkdir(parents=True, exist_ok=True)
        custom = {"display_name": "My Recipe", "variables": {}, "features": []}
        new_recipe = cache_dir / 'my_new_recipe.json'
        new_recipe.write_text(json.dumps(custom))
        try:
            recipe = TemplateManager('fv').get_recipe('my_new_recipe')
            assert recipe['display_name'] == 'My Recipe'
        finally:
            new_recipe.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# list_recipes
# ---------------------------------------------------------------------------

class TestListRecipes:
    def test_list_fv_contains_2d_hd(self):
        from pytuflow.project.template.manager import TemplateManager
        names = [r[0] for r in TemplateManager('fv').list_recipes()]
        assert '2d_hd' in names

    def test_list_hpc_contains_basic_2d(self):
        from pytuflow.project.template.manager import TemplateManager
        names = [r[0] for r in TemplateManager('hpc').list_recipes()]
        assert 'basic_2d' in names

    def test_list_returns_three_tuple(self):
        from pytuflow.project.template.manager import TemplateManager
        for name, display_name, description in TemplateManager('fv').list_recipes():
            assert name and display_name  # description may be empty

    def test_list_unknown_engine_empty(self):
        from pytuflow.project.template.manager import TemplateManager
        assert TemplateManager('__none__').list_recipes() == []


# ---------------------------------------------------------------------------
# _merge_recipe helper
# ---------------------------------------------------------------------------

class TestMergeRecipe:
    def _merge(self, recipe, cli_features, cli_kwargs):
        from pytuflow.project.__main__ import _merge_recipe
        return _merge_recipe(recipe, cli_features, cli_kwargs)

    def test_recipe_features_preserved_when_no_cli(self):
        recipe = {'features': ['outputnc', 'tutorial'], 'variables': {}}
        features, _ = self._merge(recipe, [], {})
        assert features == ['outputnc', 'tutorial']

    def test_cli_plain_string_overwrites_same_name(self):
        recipe = {'features': ['outputnc', 'tutorial'], 'variables': {}}
        features, _ = self._merge(recipe, ['outputnc'], {})
        assert features.count('outputnc') == 1

    def test_cli_plain_string_not_in_recipe_appended(self):
        recipe = {'features': ['tutorial'], 'variables': {}}
        features, _ = self._merge(recipe, ['outputnc'], {})
        assert 'outputnc' in features
        assert 'tutorial' in features

    def test_cli_dict_feature_is_additive(self):
        """Dict-style CLI features are always appended — never replace recipe entry."""
        recipe = {'features': ['outputnc'], 'variables': {}}
        cli_dict = {'name': 'outputnc', 'suffix': 'AD'}
        features, _ = self._merge(recipe, [cli_dict], {})
        # original 'outputnc' string still present AND the dict is added
        assert 'outputnc' in features
        assert cli_dict in features
        assert features.count('outputnc') == 1   # string not duplicated

    def test_recipe_variables_are_base(self):
        recipe = {'features': [], 'variables': {'output_interval': '3600.'}}
        _, vars_ = self._merge(recipe, [], {})
        assert vars_['output_interval'] == '3600.'

    def test_cli_kwarg_overwrites_recipe_variable(self):
        recipe = {'features': [], 'variables': {'output_interval': '3600.'}}
        _, vars_ = self._merge(recipe, [], {'output_interval': '600.'})
        assert vars_['output_interval'] == '600.'

    def test_cli_kwarg_adds_new_variable(self):
        recipe = {'features': [], 'variables': {}}
        _, vars_ = self._merge(recipe, [], {'cell_size': '5'})
        assert vars_['cell_size'] == '5'

    def test_recipe_dict_feature_replaced_by_cli_plain(self):
        """A plain CLI string replaces even a dict recipe entry with the same name."""
        recipe_dict = {'name': 'outputnc', 'suffix': 'HD'}
        recipe = {'features': [recipe_dict], 'variables': {}}
        features, _ = self._merge(recipe, ['outputnc'], {})
        # The dict is gone; plain string 'outputnc' takes its place
        assert 'outputnc' in features
        assert recipe_dict not in features
        assert features.count('outputnc') == 1


# ---------------------------------------------------------------------------
# Integration: FVProject.create() via recipe
# ---------------------------------------------------------------------------

class TestCreateWithRecipe:
    def test_recipe_by_name_creates_project(self, project_dir):
        from pytuflow.project.fv.project import FVProject
        from pytuflow.project.template.manager import TemplateManager
        recipe = TemplateManager('fv').get_recipe('2d_hd')
        features, variables = recipe.get('features', []), recipe.get('variables', {})
        p = FVProject(name='mymodel', output_dir=project_dir,
                      crs='EPSG:32760', features=features, **variables)
        assert p.validate() == []
        p.create()
        assert (project_dir / 'runs' / 'mymodel_001.fvc').exists()

    def test_recipe_features_appear_in_fvc(self, project_dir):
        from pytuflow.project.fv.project import FVProject
        from pytuflow.project.template.manager import TemplateManager
        from pytuflow import FVC
        import re
        recipe = TemplateManager('fv').get_recipe('2d_hd')
        FVProject(name='mymodel', output_dir=project_dir, crs='EPSG:32760',
                  features=recipe.get('features', []),
                  **recipe.get('variables', {})).create()
        fvc = FVC(project_dir / 'runs' / 'mymodel_001.fvc')
        assert fvc.find_input(filter_by='^Output == netcdf$', regex=True,
                              regex_flags=re.IGNORECASE), \
            "outputnc from recipe not found in FVC"

    def test_recipe_from_file_path(self, project_dir, recipe_file):
        from pytuflow.project.fv.project import FVProject
        from pytuflow.project.template.manager import TemplateManager
        recipe = TemplateManager('fv').get_recipe(str(recipe_file))
        FVProject(name='mymodel', output_dir=project_dir, crs='EPSG:32760',
                  features=recipe.get('features', []),
                  **recipe.get('variables', {})).create()
        assert (project_dir / 'runs' / 'mymodel_001.fvc').exists()

    def test_recipe_from_json_string(self, project_dir):
        from pytuflow.project.fv.project import FVProject
        from pytuflow.project.template.manager import TemplateManager
        inline = json.dumps({"variables": {}, "features": ["outputnc"]})
        recipe = TemplateManager('fv').get_recipe(inline)
        FVProject(name='mymodel', output_dir=project_dir, crs='EPSG:32760',
                  features=recipe.get('features', []),
                  **recipe.get('variables', {})).create()
        assert (project_dir / 'runs' / 'mymodel_001.fvc').exists()


# ---------------------------------------------------------------------------
# CLI: create --recipe flag
# ---------------------------------------------------------------------------

class TestCreateCLIWithRecipe:
    def _run(self, argv):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, '-m', 'pytuflow.project'] + argv,
            capture_output=True, text=True,
            cwd='/home/ellis/dev/PyTuflow',
        )
        return result.returncode, result.stdout, result.stderr

    def test_create_with_recipe_name(self, project_dir):
        rc, out, err = self._run([
            'create', '--engine', 'fv', '--name', 'test',
            '--output-dir', str(project_dir), '--crs', 'EPSG:32760',
            '--recipe', '2d_hd',
        ])
        assert rc == 0, err
        assert (project_dir / 'runs' / 'test_001.fvc').exists()

    def test_create_with_recipe_file_path(self, project_dir, recipe_file):
        rc, out, err = self._run([
            'create', '--engine', 'fv', '--name', 'test',
            '--output-dir', str(project_dir), '--crs', 'EPSG:32760',
            '--recipe', str(recipe_file),
        ])
        assert rc == 0, err
        assert (project_dir / 'runs' / 'test_001.fvc').exists()

    def test_create_with_recipe_json_string(self, project_dir):
        inline = json.dumps({"variables": {}, "features": ["outputnc"]})
        rc, out, err = self._run([
            'create', '--engine', 'fv', '--name', 'test',
            '--output-dir', str(project_dir), '--crs', 'EPSG:32760',
            '--recipe', inline,
        ])
        assert rc == 0, err
        assert (project_dir / 'runs' / 'test_001.fvc').exists()

    def test_create_cli_var_overwrites_recipe_var(self, project_dir):
        """--output-interval on CLI should overwrite recipe's output_interval."""
        recipe_data = json.dumps({
            "variables": {"output_interval": "3600."},
            "features": [],
        })
        rc, out, err = self._run([
            'create', '--engine', 'fv', '--name', 'test',
            '--output-dir', str(project_dir), '--crs', 'EPSG:32760',
            '--recipe', recipe_data,
            '--output-interval', '600.',
        ])
        assert rc == 0, err

    def test_create_dict_feature_additive(self, project_dir):
        """Dict --features entry is additive on top of recipe features."""
        recipe_data = json.dumps({
            "variables": {},
            "features": ["outputnc"],
        })
        rc, out, err = self._run([
            'create', '--engine', 'fv', '--name', 'test',
            '--output-dir', str(project_dir), '--crs', 'EPSG:32760',
            '--recipe', recipe_data,
            '--features', '{"name":"outputnc","suffix":"AD"}',
        ])
        assert rc == 0, err

    def test_create_unknown_recipe_name_exits_nonzero(self, project_dir):
        rc, out, err = self._run([
            'create', '--engine', 'fv', '--name', 'test',
            '--output-dir', str(project_dir), '--crs', 'EPSG:32760',
            '--recipe', 'nonexistent_recipe',
        ])
        assert rc == 1
        assert 'nonexistent_recipe' in err

    def test_create_recipe_wrong_engine_exits_nonzero(self, project_dir):
        rc, out, err = self._run([
            'create', '--engine', 'hpc', '--name', 'test',
            '--output-dir', str(project_dir), '--crs', 'EPSG:32760',
            '--recipe', '2d_hd',   # fv-only recipe
        ])
        assert rc == 1
        assert '2d_hd' in err

    def test_list_recipes_fv(self):
        rc, out, err = self._run(['list-recipes', '--engine', 'fv'])
        assert rc == 0, err
        assert '2d_hd' in out

    def test_list_recipes_hpc(self):
        rc, out, err = self._run(['list-recipes', '--engine', 'hpc'])
        assert rc == 0, err
        assert 'basic_2d' in out

    def test_create_without_recipe_still_works(self, project_dir):
        """Plain create without --recipe is unaffected."""
        rc, out, err = self._run([
            'create', '--engine', 'fv', '--name', 'test',
            '--output-dir', str(project_dir), '--crs', 'EPSG:32760',
        ])
        assert rc == 0, err
        assert (project_dir / 'runs' / 'test_001.fvc').exists()



