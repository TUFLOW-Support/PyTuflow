"""Tests for the recipe system: RecipeManager and create-recipe CLI."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def recipe_dir(tmp_path):
    """A temporary directory with a fake recipe JSON."""
    d = tmp_path / 'recipes' / 'fv'
    d.mkdir(parents=True)
    recipe = {
        "display_name": "Test Recipe",
        "description": "A recipe for testing.",
        "variables": {"output_interval": "1800."},
        "features": ["outputnc"],
    }
    (d / 'test_recipe.json').write_text(json.dumps(recipe))
    return tmp_path


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path / 'fv_project'


# ---------------------------------------------------------------------------
# RecipeManager unit tests
# ---------------------------------------------------------------------------

class TestRecipeManagerLoad:
    def test_load_bundled_recipe(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        recipe = mgr.get_recipe('flood_model')
        assert 'features' in recipe
        assert 'display_name' in recipe

    def test_load_bundled_hpc_recipe(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('hpc')
        recipe = mgr.get_recipe('basic_2d')
        assert 'features' in recipe

    def test_load_nonexistent_raises(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        with pytest.raises(FileNotFoundError, match='water_quality'):
            mgr.get_recipe('water_quality')

    def test_load_wrong_engine_raises(self):
        """flood_model is fv-only; looking it up under hpc should raise."""
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('hpc')
        with pytest.raises(FileNotFoundError, match='flood_model'):
            mgr.get_recipe('flood_model')

    def test_user_cache_overrides_bundled(self, tmp_path):
        from pytuflow.project.template.manager import TemplateManager, CACHE_ROOT
        cache_recipe_dir = CACHE_ROOT / 'recipes' / 'fv'
        cache_recipe_dir.mkdir(parents=True, exist_ok=True)
        custom = {"display_name": "Custom", "description": "user override",
                  "variables": {"output_interval": "9999."}, "features": []}
        (cache_recipe_dir / 'flood_model.json').write_text(json.dumps(custom))
        try:
            mgr = TemplateManager('fv')
            recipe = mgr.get_recipe('flood_model')
            assert recipe['variables']['output_interval'] == '9999.'
        finally:
            (cache_recipe_dir / 'flood_model.json').unlink(missing_ok=True)

    def test_user_cache_new_recipe_discovered(self, tmp_path):
        from pytuflow.project.template.manager import TemplateManager, CACHE_ROOT
        cache_recipe_dir = CACHE_ROOT / 'recipes' / 'fv'
        cache_recipe_dir.mkdir(parents=True, exist_ok=True)
        custom = {"display_name": "My Recipe", "description": "brand new",
                  "variables": {}, "features": []}
        (cache_recipe_dir / 'my_new_recipe.json').write_text(json.dumps(custom))
        try:
            mgr = TemplateManager('fv')
            recipe = mgr.get_recipe('my_new_recipe')
            assert recipe['display_name'] == 'My Recipe'
        finally:
            (cache_recipe_dir / 'my_new_recipe.json').unlink(missing_ok=True)


class TestRecipeManagerListRecipes:
    def test_list_recipes_fv(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        recipes = mgr.list_recipes()
        names = [r[0] for r in recipes]
        assert 'flood_model' in names

    def test_list_recipes_hpc(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('hpc')
        recipes = mgr.list_recipes()
        names = [r[0] for r in recipes]
        assert 'basic_2d' in names

    def test_list_recipes_returns_tuple_fields(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        recipes = mgr.list_recipes()
        for name, display_name, description in recipes:
            assert name
            assert display_name

    def test_list_recipes_empty_engine(self):
        """An engine with no recipes returns an empty list gracefully."""
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('__nonexistent_engine__')
        assert mgr.list_recipes() == []


class TestRecipeManagerInitCache:
    def test_init_cache_copies_bundled(self, tmp_path):
        from pytuflow.project.template.manager import TemplateManager, CACHE_ROOT
        mgr = TemplateManager('fv')
        mgr.init_cache(force=True)
        cached = CACHE_ROOT / 'recipes' / 'fv'
        assert cached.exists()
        assert any(cached.glob('*.json'))

    def test_init_cache_idempotent(self):
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        mgr.init_cache()
        mgr.init_cache()  # should not raise


# ---------------------------------------------------------------------------
# Integration: FVProject.create() using recipe variables and features
# ---------------------------------------------------------------------------

class TestCreateFromRecipe:
    def test_recipe_variables_applied(self, project_dir):
        from pytuflow.project.fv.project import FVProject
        from pytuflow.project.template.manager import TemplateManager
        mgr = TemplateManager('fv')
        recipe = mgr.get_recipe('flood_model')
        variables = recipe.get('variables', {})
        features = recipe.get('features', [])

        p = FVProject(
            name='mymodel',
            output_dir=project_dir,
            crs='EPSG:32760',
            features=features,
            **variables,
        )
        errors = p.validate()
        assert errors == []
        out = p.create()
        assert out is not None
        assert (project_dir / 'runs' / 'mymodel_001.fvc').exists()

    def test_recipe_features_inserted(self, project_dir):
        """outputnc in the flood_model recipe should appear in the FVC."""
        from pytuflow.project.fv.project import FVProject
        from pytuflow.project.template.manager import TemplateManager
        from pytuflow import FVC
        import re
        mgr = TemplateManager('fv')
        recipe = mgr.get_recipe('flood_model')
        variables = recipe.get('variables', {})
        features = recipe.get('features', [])

        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', features=features, **variables,
        )
        p.create()

        fvc = FVC(project_dir / 'runs' / 'mymodel_001.fvc')
        result = fvc.find_input(filter_by='^Output == netcdf$', regex=True,
                                regex_flags=re.IGNORECASE)
        assert result, "outputnc feature should have been applied from recipe"


# ---------------------------------------------------------------------------
# CLI: create-recipe subcommand
# ---------------------------------------------------------------------------

class TestCreateRecipeCLI:
    def _run(self, argv):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, '-m', 'pytuflow.project'] + argv,
            capture_output=True, text=True,
            cwd='/home/ellis/dev/PyTuflow',
        )
        return result.returncode, result.stdout, result.stderr

    def test_create_recipe_success(self, project_dir):
        rc, out, err = self._run([
            'create-from-recipe', '--recipe', 'flood_model',
            '--engine', 'fv',
            '--name', 'test',
            '--output-dir', str(project_dir),
            '--crs', 'EPSG:32760',
        ])
        assert rc == 0, err
        assert (project_dir / 'runs' / 'test_001.fvc').exists()

    def test_create_recipe_unknown_recipe_exits_nonzero(self, project_dir):
        rc, out, err = self._run([
            'create-from-recipe', '--recipe', 'nonexistent_recipe',
            '--engine', 'fv',
            '--name', 'test',
            '--output-dir', str(project_dir),
            '--crs', 'EPSG:32760',
        ])
        assert rc == 1
        assert 'nonexistent_recipe' in err

    def test_create_recipe_wrong_engine_exits_nonzero(self, project_dir):
        """flood_model is fv-only; requesting it for hpc should fail."""
        rc, out, err = self._run([
            'create-from-recipe', '--recipe', 'flood_model',
            '--engine', 'hpc',
            '--name', 'test',
            '--output-dir', str(project_dir),
            '--crs', 'EPSG:32760',
        ])
        assert rc == 1
        assert 'flood_model' in err

    def test_list_recipes_command(self):
        rc, out, err = self._run(['list-recipes', '--engine', 'fv'])
        assert rc == 0, err
        assert 'flood_model' in out

    def test_list_recipes_hpc(self):
        rc, out, err = self._run(['list-recipes', '--engine', 'hpc'])
        assert rc == 0, err
        assert 'basic_2d' in out
