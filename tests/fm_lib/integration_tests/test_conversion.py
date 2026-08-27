import unittest
from pathlib import Path
import pyproj

from pytuflow._fm.parsers.dat import DAT
from pytuflow._fm.parsers.gxy import GXY
from pytuflow._fm.utils.output_writer import OutputWriter
from pytuflow._fm.helpers.settings import get_fm2estry_settings
from ..common.compare_csv import compare_csv
from ..common.compare_txt import compare_txt
from ..common.compare_vector_layer import compare_vector_layer
from ..common.gis import VectorLayer


class Setup:

    def __init__(self, dat_path: Path) -> None:
        self.dat_path = dat_path
        self.gxy_path = dat_path.with_suffix('.gxy')
        self.name = dat_path.stem
        self.settings = get_fm2estry_settings()
        self.settings.__init__()  # reset settings to default values
        self.settings.crs = pyproj.CRS('EPSG:32760')
        self.settings.dat_fpath_ = self.dat_path
        self.settings.output_dir = Path('./tests/fm_lib/integration_tests/outputs_tmp') / self.name
        self.pre_conv_folder = Path('./tests/fm_lib/integration_tests/pre_converted') / self.name
        [x.unlink() for x in self.settings.output_dir.glob('**/*') if x.is_file()]


class Result:

    def __init__(self, folder: Path) -> None:
        self.pre_conv_folder = folder
        self.csvs = list(folder.glob('**/*.csv'))
        self.ecfs = list(folder.glob('**/*.ecf'))
        self.gis_files = list(folder.glob('**/*.gpkg'))
        self.gis_layers = []
        for gis_file in self.gis_files:
            with VectorLayer(gis_file) as v:
                self.gis_layers.extend([f'{gis_file} >> {x}' for x in v.layers()])


def run_conversion(setup):
    dat = DAT(setup.dat_path)
    gxy = GXY(setup.gxy_path)
    dat.add_gxy(gxy)
    output_writer = OutputWriter()
    for unit in dat.units:
        output = unit.convert()
        output_writer.write(output)
    output_writer.finalize()


def compare(result1, result2):
    assert len(result1.csvs) == len(result2.csvs), f'compare(result1, result2): number of csvs do not match\nresult1: {len(result1.csvs)}\nresult2: {len(result2.csvs)}'
    assert len(result1.gis_layers) == len(result2.gis_layers), f'compare(result1, result2): length of gis alyers do not match\nresult1: {len(result1.gis_layers)}\nresult2: {len(result2.gis_layers)}'
    for csv1, csv2 in zip(result1.csvs, result2.csvs):
        compare_csv(csv1, csv2)
    for ecf1, ecf2 in zip(result1.ecfs, result2.ecfs):
        compare_txt(ecf1, ecf2)
    for lyr1, lyr2 in zip(result1.gis_layers, result2.gis_layers):
        compare_vector_layer(lyr1, lyr2)


class TestConversion(unittest.TestCase):

    def test_convert_river_only(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Only.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_replicates(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_replicates.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_interpolates(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_interpolates.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_junctions(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Junctions.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_symmetrical_conduit(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Symmetrical_Conduit.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_asymmetrical_conduit(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Asymmetrical_Conduit.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_circular_conduit(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Circular_Conduit.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_rectangular_conduit(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Rectangular_Conduit.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_full_arch_conduit(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Full_Arch_Conduit.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_sprung_arch_conduit(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Sprung_Arch_Conduit.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_orifice(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Orifice.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_inverted_syphon(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Inverted_Syphon.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_outfall(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Outfall.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_flood_relief_arch(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Flood_Relief_Arch.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_broad_crested_weir(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Broad_Crested_Weir.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_crump_weir(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Crump_Weir.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_flat_v_weir(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Flat_V_Weir.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_flow_head_weir(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Flow_Head_Weir.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_gated_weir(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Gated_weir.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_notional_weir(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Notional_weir.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_labyrinth_weir(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Labyrinth_weir.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_sharp_crested_weir(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Sharp_Crested_weir.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_syphon(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Syphon.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_general_weir(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_General_weir.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_InLine_Spill(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_InLine_Spill.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_vertical_sluice(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Vertical.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_radial_sluice(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Radial.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_arch_bridge_irreg_basic(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Arch_Bridge.dat')
        setup = Setup(dat_path)
        setup.settings.arch_bridge_approach = 'I-CULV'
        setup.settings.output_dir = setup.settings.output_dir.parent / 'River_Sections_w_Arch_Bridge_Irregular_Basic'
        [x.unlink() for x in setup.settings.output_dir.glob('**/*') if x.is_file()]
        setup.pre_conv_folder = setup.pre_conv_folder.parent / 'River_Sections_w_Arch_Bridge_Irregular_Basic'
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_arch_bridge_barch_basic(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Arch_Bridge.dat')
        setup = Setup(dat_path)
        setup.settings.arch_bridge_approach = 'BARCH'
        setup.settings.output_dir = setup.settings.output_dir.parent / 'River_Sections_w_Arch_Bridge_BArch_Basic'
        [x.unlink() for x in setup.settings.output_dir.glob('**/*') if x.is_file()]
        setup.pre_conv_folder = setup.pre_conv_folder.parent / 'River_Sections_w_Arch_Bridge_BArch_Basic'
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_arch_bridge_irreg_2arches_as_one(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Arch_Bridge_2.dat')
        setup = Setup(dat_path)
        setup.settings.arch_bridge_approach = 'I-CULV'
        setup.settings.arch_bridge_culv_approach = 'SINGLE'
        setup.settings.output_dir = setup.settings.output_dir.parent / 'River_Sections_w_Arch_Bridge_Irregular_2Arches_as_one'
        [x.unlink() for x in setup.settings.output_dir.glob('**/*') if x.is_file()]
        setup.pre_conv_folder = setup.pre_conv_folder.parent / 'River_Sections_w_Arch_Bridge_Irregular_2Arches_as_one'
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_arch_bridge_irreg_2arches_as_multi(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Arch_Bridge_2.dat')
        setup = Setup(dat_path)
        setup.settings.arch_bridge_approach = 'I-CULV'
        setup.settings.arch_bridge_culv_approach = 'MULTI'
        setup.settings.output_dir = setup.settings.output_dir.parent / 'River_Sections_w_Arch_Bridge_Irregular_2Arches_as_multi'
        [x.unlink() for x in setup.settings.output_dir.glob('**/*') if x.is_file()]
        setup.pre_conv_folder = setup.pre_conv_folder.parent / 'River_Sections_w_Arch_Bridge_Irregular_2Arches_as_multi'
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_arch_bridge_wspill(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Arch_Bridge_wSpill.dat')
        setup = Setup(dat_path)
        setup.settings.arch_bridge_approach = 'BARCH'
        setup.settings.arch_bridge_culv_approach = 'MULTI'
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_pier_loss_bridge(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_Pier_Loss_Bridge.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_w_usbpr_bridge(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_w_USBPR_Bridge.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)

    def test_convert_river_culvert_inlet_outlet(self):
        dat_path = Path('./tests/fm_lib/data/River_Sections_Culvert_inlet_outlet.dat')
        setup = Setup(dat_path)
        pre_cooked_result = Result(setup.pre_conv_folder)
        run_conversion(setup)
        result = Result(setup.settings.output_dir)
        compare(result, pre_cooked_result)
