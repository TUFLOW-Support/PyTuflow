# Flood Modeller to ESTRY

Library for converting a Flood Modeller river models to an ESTRY models.

Documentation: https://wiki.tuflow.com/Flood_Modeller_to_TUFLOW<br>
Repository: https://gitlab.com/tuflow-user-group/tuflow/model-conversions/fm-to-estry<br>
Compiled Executable: https://downloads.tuflow.com/Private_Download/fm_to_estry/fm_to_estry.0.16.zip

## Command Line Interface

REQUIRED INPUTS
  * `[/path/to/gxy]`
  * `[/path/to/dat]`

OPTIONAL
  * `-help` print tool documentation
  * `-crs [CRS]` specify the output CRS. Can be in the form of "Authority:Code" e.g. -crs "EPSG:27700" or can point to an existing GIS file e.g. -crs "/path/to/file.shp"
  * `-o [/path/to/output-dir]` specify the output directory. Default is the current working directory + DAT file name (also accepts "-out")
  * `-logfile [/optional/path/to/logfile.log]` outputs the log to a file (echo of console output to a log file)
  * `-shp` export the output to shapefiles
  * `-gpkg` export the output to a geopackage
  * `-mif` export the output to a mif file
  * `-tab` export the output to a tab file
  * `-check` output the dat/gxy data to GIS for checking prior to any conversion (also accepts "-raw").
  * `-loglimit [N]` sets the maximum number of warnings that will be logged to the console.
  * `-list-unconverted [/optional/path/to/unconverted.txt]` outputs a list of unconverted units to a text file. Default is the output folder.
  * `-co [OPTION=VALUE]` see conversion options below

CONVERSION OPTIONS
More advanced conversion options use the following form "-co OPTION=VALUE" where multiple "-co" can be specified. See examples further below.
  * `outname=[STR]` specify the output name for the ESTRY model (default is the name of the DAT file)
  * `output_dir=[STR]` specify the output directory for the ESTRY model (default is the current working directory + outname)
  * `gis_format=[STR]` specify the output format for the ESTRY model. Options are "shp", "gpkg", "mif", "tab" (default is GPKG)
  * `crs=[STR]` specify the output CRS for the ESTRY model (no default)
  * `group_db=[True/False]` GPKG output will be grouped in a single database or not (default is True)
  * `single_nwk=[True/False]` output the 1d_nwk features in a single layer or not (default is False)
  * `single_tab=[True/False]` output the 1d_tab (1d_xs, 1d_hw) features in a single layer or not (default is False)
  * `arch_bridge_approach=[BARCH/I-CULV]` output arch bridges as "BARCH" type or as irregular "I" type culverts (default is BARCH)
  * `arch_bridge_culv_approach=[SINGLE/MULTI]` when using "I-CULV" arch bridge approach, determines whether to output each arch as a single culvert or combine into a single HW table (default is MULTI)
  * `xs_gis_length=[float]` specify the length of 1d_xs and 1d_hw lines in the GIS output (default is 20)

EXAMPLES
  
1. Simple:<br>
`fm_to_estry.exe flood_model.dat flood_model.gxy -crs "EPSG:27700"`

2. Custom output directory<br>
`fm_to_estry.exe flood_model.dat flood_model.gxy -crs "EPSG:27700" -o .\custom_out_dir\`

3. Output to console to a log file<br>
`fm_to_estry.exe flood_model.dat flood_model.gxy -crs "EPSG:27700" -logfile`

4. Using Shapefile format<br>
`fm_to_estry.exe flood_model.dat flood_model.gxy -crs "EPSG:27700" -shp`

5. Output all 1d_nwk and 1d_tab to a single GIS layer<br>
`fm_to_estry.exe flood_model.dat flood_model.gxy -crs "EPSG:27700" -co single_nwk=True -co single_tab=True`

## Python Installation

Dependencies:

* Python 3.7+
* numpy
* pandas
* gdal

### Installation

1. Clone the repository<br>
`git clone https://gitlab.com/tuflow-user-group/tuflow/model-conversions/fm-to-estry.git`
2. Install dependencies<br>
`pip install numpy pandas`
3. Install gdal<br>
(on windows, get binares from https://github.com/cgohlke/geospatial-wheels/releases)<br>

The CLI can be run using `main.py`. Otherwise if using fm_to_estry as library to parse FM inputs, useful classes are `DAT` and `GXY` for reading input files

```python
from fm_to_estry.parsers.dat import DAT
from fm_to_estry.parsers.gxy import GXY

dat = DAT("path/to/dat")
gxy = GXY("path/to/gxy")
dat.add_gxy(gxy)  # adds spatial references to DAT units

unit = dat.unit('full_unit_id')  # e.g. dat.unit('RIVER_SECTION_FC01.35')
output = unit.convert()  # converts the unit to ESTRY - output is a list of Output objects that contain GIS/text data

```

#### Running Tests

There are 2 test suites:
* unit tests
* integration tests

To run the tests:

1. open terminal session
2. Navigate to the project folder (folder that contains `test` folder):<br>
`cd /path/to/fm_to_estry`
3. Add `fm_to_estry` to the PYTHONPATH:<br>
`set PYTHONPATH=%PYTHONPATH%;./fm_to_estry` (windows)<br>
`export PYTHONPATH=$PYTHONPATH:./fm_to_estry` (linux)
4. Run the `unit_tests`<br>
`python -m unittest discover -s tests/unit_tests`
5. Run the `integration_tests`<br>
`python -m unittest discover -s tests/integration_tests`


### Development

#### Unit Loading

All units are loaded via the classes in the `parsers.units` module. All unit types should be present but I have to admit that not all units have been fully tested. The unit loading has been based off the DAT reference in the Flood Modelling manual, however very occasionally there are discrepancies between the manual and what actually gets written (also more than very occasionally I make silly coding mistakes!). Any corrections to unit loading should be made to the appropriate file here following the many examples in this location.

#### Unit Conversion

The unit conversion is made by the classes present in the `converters` module. Any new units should be added to the location as a new Python file. The converter should inherit from the `Converter` class or any class that inherits from `Converter`. The library will automatically find and load any class that inherits from `Converter` located in this directory.

There are plenty of example conversions in this location, but the general form should follow the example below. The example assumes that there is some FM unit called `NEW_UNIT` which should obviously be changed to whatever the converted unit type is called (e.g. 'CircularConduit'). The code below is a guide, more complicate conversions may deviate from this example.

Note that this example assumes a conversion from some unit into a channel. Some units would be converted into boundaries (most likely point boundaries in ESTRY) and some unit types should not be directly converted into any ESTRY object e.g. LOSSES, which would be attached or added to other channels. In these cases, the example below is only a rough example or in the case of something like LOSSES isn't really applicable. In these cases, try and find a relevant example in the existing converters (e.g. how CULVERTs are handled).

```python
import typing
from collections import OrderedDict
import io
import os

from fm_to_estry.converters.converter import Converter  # converter base class
from fm_to_estry.output import Output, OutputCollection  # output classes
from fm_to_estry.helpers.tuflow_empty_files import tuflow_empty_field_map  # tuflow empty type attribute field mapping

if typing.TYPE_CHECKING:  # avoids any chance of circular references when using type hinting
    from fm_to_estry.parsers.units.handler import Handler


class NewUnit(Converter):
    
    def __init__(self, unit: 'Handler' = None) -> None:
        super().__init__(unit)
        # list expected outputs - not completely necessary, but it's nice to see what the unit is expected to output
        self.nwk = Output('GIS')  # 1d_nwk
        self.tab = Output('GIS')  # 1d_xs or 1d_hw (1d_tab) if applicable
        self.ecf = Output('CONTROL')  # control file data (use CONTROL for things like bc_dbase.csv as well)
        self.xs = Output('FILE')  # CSV file containing xs or hw data if applicable
        
    @staticmethod
    def complete_unit_type_name() -> str:
        # this is how the correct converter is found for a given unit type
        # this should return the form "TYPE_SUBTYPE" even if there isn't a subtype e.g. "RIVER_SECTION" or "ORIFICE_"
        return 'NEW_UNIT'
    
    def convert(self) -> OutputCollection:
        # this is the conversion routine - outputs an 'OutputCollection' which is basically just a list of 'Output' objects
        # note use 'OutputCollection' class though and not just a generic list type
        out_col = OutputCollection()
        
        # generate output classes and append to OutputCollection (order within the list is not important)
        nwk = self.get_nwk()
        out_col.append(nwk)
        
        xs = self.get_xs()  # xs csv can be useful to generate before 1d_xs since the filename may be needed for 1d_xs
        out_col.append(xs)
        
        tab = self.get_tab()  # 1d_xs
        out_col.append(tab)
        
        ecf = self.get_ecf()
        out_col.append(ecf)
        
        return out_col
    
    def get_nwk(self) -> Output:
        # generate 1d_nwk GIS/attribute data
        
        # convenience method to generate file name/layer name
        # considers things like GPKG grouping, 1d_nwk layer grouping etc.
        # first argument is the file name prefix, 
        # second is a unique identifier for the type (usually the unit type e.g. 'RIVER' / 'CONDUIT')
        self.nwk.fpath, self.nwk.lyrname = self.output_gis_file('1d_nwk', 'NEW_UNIT')
        
        # set generic data for the 1d_nwk output
        self.nwk.field_map = tuflow_empty_field_map('1d_nwk')
        self.nwk.geom_type = 2  # 1 = ogr.wkbPoint, 2 = ogr.wkbLineString, 3 = ogr.wkbPolygon
        
        # populate the actual content (geometry, attributes) of the 1d_nwk output
        # use convenience method in base class to set channel geometry. Generally this is all you need to for channel geometry.
        # for complicated cases you can override the base class 'get_ups_node' and 'get_dns_node' methods to override 
        # how the upstream and downstream line vertices are determined
        self.nwk.content.geom = self.channel_geom(self.unit)
        self.nwk.content.attributes = self.map_nwk_attributes(self.nwk_field_map, self.unit)
        
        return self.nwk
        
    def map_nwk_attributes(self, field_map: dict, unit: 'RiverHandler') -> OrderedDict:
        # return a dictionary of attributes and values for the nwk output
        d = OrderedDict()
        # initialise values with None
        for key, value in field_map.items():
            d[key] = None
        # populate required values
        # e.g.
        d['ID'] = unit.uid
        d['Type'] = 'S'
        return d
    
    def get_xs(self) -> Output:
        # returns the cross-section csv (or hw csv, or whatever it is)
        # the csv data is stored as a string inside the 'Output' object
        
        # set the file path for the xs csv
        self.xs.fpath = self.settings.output_dir / 'csv' / f'{self.unit.id}.csv'
        
        # most of the time a pandas dataframe will contain the data
        # so we will write dataframe data to a buffer and then return the buffer as a string
        buf = io.StringIO()
        buf.write(f'! Generated by fm_to_estry. Source: {self.dat.name}/{self.unit.uid}\n')
        
        df = self.unit.some_collected_data  # assume that the loaded unit has loaded cross-section into a dataframe already
        df.to_csv(buf, index=False, lineterminator='\n')
        self.xs.content = buf.getvalue()
        return self.xs
    
    def get_tab(self) -> Output:
        # similar to get_nwk but for 1d_xs or 1d_hw
        self.tab.fpath, self.tab.lyrname = self.output_gis_file('1d_xs', 'NEW_UNIT')
        
        self.tab.field_map = tuflow_empty_field_map('1d_tab')
        self.tab.geom_type = 2  # ogr.wkbLineString
        
        # use
        self.tab.content.geom = self.end_cross_section_geom(self.unit, avg_with_ups=True)
        # or
        self.tab.content.geom = self.mid_cross_section_geometry(self.unit)
        
        self.tab.content.attributes = self.map_tab_attributes(self.tab.field_map, self.unit)  # see map_nwk_attributes for how this would be implemented
        
        return self.tab
    
    def get_ecf(self) -> Output:
        # return the control file data
        
        # file path for the control file
        self.ecf.fpath = self.settings.output_dir / f'{self.settings.outname}.ecf'
        
        # use relative file path reference
        nwk_relpath = os.path.relpath(self.nwk.fpath, self.ecf.fpath.parent)
        # use convenience method to write filepath reference for control file
        # - this will consider GPKG grouped layers etc.
        fpath_ref = self.output_gis_ref(nwk_relpath, self.nwk.lyrname)
        nwk_cmd = f'Read GIS Network == {fpath_ref}\n'
        
        # similar stuff for 1d_xs/1d_hw
        tab_relpath = os.path.relpath(self.tab.fpath, self.ecf.fpath.parent)
        fpath_ref = self.output_gis_ref(tab_relpath, self.tab.lyrname)
        tab_cmd = f'Read GIS Table Links == {fpath_ref}\n'
        
        self.ecf.content = f'{nwk_cmd}{tab_cmd}'
        return self.ecf

```
