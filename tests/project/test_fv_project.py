"""Tests for FVProject create and module framework."""
import pytest
from pathlib import Path

from pytuflow.project.fv.project import FVProject, get_available_modules


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path / 'fv_project'


@pytest.fixture
def basic_project(project_dir):
    return FVProject(
        name='mymodel',
        output_dir=project_dir,
        crs='EPSG:32760',
        gis_format='SHP',
        create_empties=False,
    )


class TestFVProjectValidation:
    def test_valid_project_no_errors(self, basic_project):
        assert basic_project.validate() == []

    def test_empty_name_raises(self, project_dir):
        p = FVProject(name='', output_dir=project_dir, crs='EPSG:32760')
        errors = p.validate()
        assert any('name' in e for e in errors)

    def test_gpkg_not_supported(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='GPKG')
        errors = p.validate()
        assert any('GPKG' in e for e in errors)

    def test_shp_supported(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='SHP')
        assert p.validate() == []

    def test_mif_supported(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='MIF')
        assert p.validate() == []

    def test_gpkg_raises_on_create(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='GPKG')
        with pytest.raises(ValueError, match='GPKG'):
            p.create()


class TestFVProjectCreate:
    def test_create_returns_output_dir(self, basic_project, project_dir):
        result = basic_project.create()
        assert result == project_dir

    def test_standard_directories_created(self, basic_project, project_dir):
        basic_project.create()
        for d in ['runs', 'model', 'model/geo', 'model/gis', 'bc_dbase', 'results', 'check', 'runs/log']:
            assert (project_dir / d).is_dir(), f"Missing directory: {d}"

    def test_fvc_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'runs' / 'mymodel_001.fvc').exists()

    def test_bc_dbase_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'bc_dbase' / 'bc_dbase.csv').exists()

    def test_fvc_contains_model_name(self, basic_project, project_dir):
        basic_project.create()
        # iter and model_name substitution: template filename was rendered
        assert (project_dir / 'runs' / 'mymodel_001.fvc').exists()

    def test_fvc_contains_gis_format(self, basic_project, project_dir):
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'GIS FORMAT == SHP' in fvc_text

    def test_fvc_shp_projection_present(self, basic_project, project_dir):
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'SHP Projection' in fvc_text

    def test_fvc_mi_projection_absent_for_shp(self, basic_project, project_dir):
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'MI Projection' not in fvc_text

    def test_fvc_mif_projection_present_for_mif(self, project_dir):
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', gis_format='MIF', create_empties=False,
        )
        p.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'MI Projection' in fvc_text
        assert 'SHP Projection' not in fvc_text

    def test_projection_file_created(self, basic_project, project_dir):
        basic_project.create()
        assert (project_dir / 'model' / 'gis' / 'projection.shp').exists()

    def test_no_gpkg_projection_file_for_shp(self, basic_project, project_dir):
        basic_project.create()
        gpkg_files = list((project_dir / 'model' / 'gis').glob('*.gpkg'))
        assert gpkg_files == []

    def test_fvc_slashes_normalized(self, basic_project, project_dir):
        import os
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        sep = os.sep
        if sep == '/':
            assert '\\' not in fvc_text
        else:
            assert '/' not in fvc_text.replace('\r\n', '\n')

    def test_no_map_output_formats_in_fvc(self, basic_project, project_dir):
        """FV outputs are modules — Map Output Formats command must not appear."""
        basic_project.create()
        fvc_text = (project_dir / 'runs' / 'mymodel_001.fvc').read_text()
        assert 'Map Output Formats' not in fvc_text


class TestFVProjectSettings:
    def test_fv_defaults_loaded(self, project_dir):
        """FV-specific defaults (spherical, latitude) should be available."""
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', create_empties=False)
        assert 'spherical' in p.settings._settings
        assert 'latitude' in p.settings._settings

    def test_hpc_defaults_not_loaded(self, project_dir):
        """HPC-specific defaults (cell_size, engine) should not appear in FV settings."""
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', create_empties=False)
        assert 'cell_size' not in p.settings._settings
        assert 'engine' not in p.settings._settings

    def test_no_output_formats_in_fv_settings(self, project_dir):
        """FV settings should not have output_formats / map_output_formats."""
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', create_empties=False)
        assert 'map_output_formats' not in p.settings._settings
        assert 'output_formats' not in p.settings._settings

    def test_gis_format_normalized_uppercase(self, project_dir):
        p = FVProject(name='m', output_dir=project_dir, crs='EPSG:32760', gis_format='shp')
        assert p.settings._settings['gis_format'] == 'SHP'


class TestFVAvailableModules:
    def test_get_available_modules_returns_dict(self):
        modules = get_available_modules()
        assert isinstance(modules, dict)

    def test_modules_are_fv_engine_type(self):
        from pytuflow.project.fv.modules._base import FVBaseModule
        modules = get_available_modules()
        for name, cls in modules.items():
            instance = cls()
            assert instance.ENGINE_TYPE == 'fv', f"{name} has wrong ENGINE_TYPE"


class TestFVProjectIter:
    def test_custom_iter(self, project_dir):
        p = FVProject(
            name='mymodel', output_dir=project_dir,
            crs='EPSG:32760', iter='002', create_empties=False,
        )
        p.create()
        assert (project_dir / 'runs' / 'mymodel_002.fvc').exists()
