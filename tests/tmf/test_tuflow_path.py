from pathlib import Path
import sys

# so can be run from tmf repo or from pytuflow repo
# sys.path.append(str(Path(__file__).parents[1]))
from ...pytuflow._tmf import TuflowPath


def test_tuflow_path():
    # Test that TuflowPath can be instantiated
    path = TuflowPath('tests/tmf/test_datasets/1d_domain_scope.tcf')
    assert isinstance(path, TuflowPath)
    assert path.exists()
    assert path.is_file()
    assert path.suffix == '.tcf'
    assert path.stem == '1d_domain_scope'
    assert path.name == '1d_domain_scope.tcf'
    assert path.parent.name == 'test_datasets'
    assert path.lyrname is None


def test_tuflow_path_gpkg():
    # Test that TuflowPath can be instantiated with a .gpkg file without a layername
    path = TuflowPath('tests/tmf/test_datasets/projection.gpkg')
    assert path.exists()
    assert path.dbpath == Path('tests/tmf/test_datasets/projection.gpkg')
    assert path.lyrname == 'projection'
    assert path.stem == 'projection'
    assert path.suffix == '.gpkg'
    assert path.name == 'projection.gpkg'
    assert path.is_file()


def test_tuflow_path_gpkg_layername():
    # Test that TuflowPath can be instantiated with a .gpkg file with a layername
    path = TuflowPath('tests/tmf/test_datasets/M02_001.gpkg >> 2d_code_M01_001_')
    assert path.exists()
    assert path.dbpath == Path('tests/tmf/test_datasets/M02_001.gpkg')
    assert path.lyrname == '2d_code_M01_001_'
    assert path.stem == 'M02_001'
    assert path.suffix == '.gpkg'
    assert path.name == 'M02_001.gpkg'
    assert path.is_file()


def test_tuflow_path_gpkg_layername_qgis_uri():
    # Test that TuflowPath can be instantiated with a .gpkg file with a layername using QGIS uri format
    path = TuflowPath('tests/tmf/test_datasets/M02_001.gpkg|layername=2d_code_M01_001_')
    assert path.exists()
    assert path.dbpath == Path('tests/tmf/test_datasets/M02_001.gpkg')
    assert path.lyrname == '2d_code_M01_001_'
    assert path.stem == 'M02_001'
    assert path.suffix == '.gpkg'
    assert path.name == 'M02_001.gpkg'
    assert path.is_file()


def test_tuflow_path_nc_grid():
    # Test that TuflowPath can be instantiated with a .nc file
    path = TuflowPath('tests/tmf/test_datasets/EG00_001.nc')
    assert path.exists()
    assert path.is_file()
    assert path.suffix == '.nc'
    assert path.stem == 'EG00_001'
    assert path.name == 'EG00_001.nc'
    assert path.lyrname is None


def test_tuflow_path_nc_grid_lyrname():
    # Test that TuflowPath can be instantiated with a .nc file with a layer name (GDAL and QGIS uri format)
    path = TuflowPath('NETCDF:"tests/tmf/test_datasets/EG00_001.nc":water_level')
    assert path.exists()
    assert path.is_file()
    assert path.suffix == '.nc'
    assert path.stem == 'EG00_001'
    assert path.name == 'EG00_001.nc'
    assert path.lyrname == 'water_level'


def test_relative_to():
    # Test that TuflowPath can be made relative to another path
    path = TuflowPath('tests/tmf/test_datasets/1d_domain_scope.tcf')
    relative_path = path.relative_to(Path('tests/tmf'))
    assert relative_path == Path('test_datasets/1d_domain_scope.tcf')


def test_relative_to_gpkg():
    # Test that TuflowPath can be made relative to another path when there isn'tj a layer name
    path = TuflowPath('tests/tmf/test_datasets/projection.gpkg')
    relative_path = path.relative_to(Path('tests/tmf'))
    assert relative_path == Path('test_datasets/projection.gpkg')


def test_relative_to_gpkg_layername():
    # Test that TuflowPath can be made relative to another path when there is a layer name
    path = TuflowPath('tests/tmf/test_datasets/M02_001.gpkg >> 2d_code_M01_001_')
    relative_path = path.relative_to(Path('tests/tmf'))
    assert relative_path == TuflowPath('test_datasets/M02_001.gpkg >> 2d_code_M01_001_')


def test_glob():
    # Test that TuflowPath can be used with glob to find files
    path = TuflowPath('tests/tmf/test_datasets')
    files = list(path.glob('1d_domain_scope_*.tcf'))
    assert len(files) == 1
    assert files[0] == TuflowPath('tests/tmf/test_datasets/1d_domain_scope_reversed.tcf')


def test_glob_gpkg():
    # Test that TuflowPath can be used with glob to find .gpkg files
    path = TuflowPath('tests/tmf/test_datasets')
    files = list(path.glob('proj*.gpkg'))
    assert len(files) == 1
    assert files[0] == TuflowPath('tests/tmf/test_datasets/projection.gpkg')


def test_glob_gpkg_layernames():
    # Test that TuflowPath can be used with glob to find .gpkg files with layer names
    path = TuflowPath('tests/tmf/test_datasets')
    files = list(path.glob('M02_00*.gpkg >> 2d_code_M01_001_R'))
    assert len(files) == 1
    assert files[0] == TuflowPath('tests/tmf/test_datasets/M02_001.gpkg >> 2d_code_M01_001_R')

    files = list(path.glob('M02_001.gpkg >> 2d_code*'))
    assert len(files) == 1
    assert files[0] == TuflowPath('tests/tmf/test_datasets/M02_001.gpkg >> 2d_code_M01_001_R')


def test_glob_gpkg_layernames_only():
    # Test that TuflowPath can be used with glob to find all layers inside a gpkg
    path = TuflowPath('tests/tmf/test_datasets/M02_001.gpkg')
    files = list(path.glob('>> *'))
    assert len(files) == 9


def test_case_insensitive_path():
    # test TuflowPath.init_case_insensitive_path() works
    p = TuflowPath('tests/tmf') // 'Test_Datasets/1D_Domain_scope.tcf'
    assert p.exists()


def test_case_insensitive_path_gpkg():
    path = TuflowPath('tests/tmf') // 'test_datasets/M02_001.gpkg >> 2d_code_M01_001_'
    assert path.exists()
