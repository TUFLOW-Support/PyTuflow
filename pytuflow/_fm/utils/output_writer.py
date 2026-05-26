import logging
import typing
from pathlib import Path

from ..helpers.settings import get_fm2estry_settings

if typing.TYPE_CHECKING:
    from ..output import Output, OutputCollection


logger = logging.getLogger('pytuflow')

# Maps OGR wkb geometry type integers to string names used by TuflowPath.open_gis().
_OGR_WKB_TO_GEOM_STR = {
    1: 'Point',
    2: 'LineString',
    3: 'Polygon',
    4: 'MultiPoint',
    5: 'MultiLineString',
    6: 'MultiPolygon',
}


class OutputWriter:

    def __init__(self) -> None:
        self.settings = get_fm2estry_settings()
        self.open_files = []
        self.open_outputs = []
        self._key2hnd = {}
        self._key2openfile = {}
        self._txt_cmds = {}

    def get_key(self, output: 'Output') -> str:
        key = str(output.fpath).lower().strip().replace('\\', '/')
        if hasattr(output, 'lyrname'):
            key = f'{key} >> {output.lyrname.lower()}'
        return key

    def finalize(self) -> None:
        for output in self.open_outputs.copy():
            self.close_output(output)

    def write(self, output_collection: 'OutputCollection') -> None:
        for output in output_collection:
            try:
                self.write_output(output)
            except Exception as e:
                logger.error(f'Error writing output type "{output.TYPE}" for "{output.id}": {e}')
                return

    def write_output(self, output: 'Output') -> bool:
        fo = self.open_output(output)
        if fo is None:
            return False
        if output.TYPE == 'FILE':
            return self.write_file_output(fo, output)
        elif output.TYPE == 'CONTROL':
            return self.write_control_output(fo, output)
        elif output.TYPE == 'GIS':
            return self.write_vector_output(fo, output)
        return False

    def write_file_output(self, fo: typing.TextIO, output: 'Output') -> bool:
        fo.write(output.content)
        return True

    def write_control_output(self, fo: typing.TextIO, output: 'Output') -> bool:
        first = False
        if fo not in self._txt_cmds:
            self._txt_cmds[fo] = []
            first = True
        content = []
        content_common = []
        for line in output.content.strip('\n').split('\n'):
            line_common = line.lower().replace('\\', '/')
            if line_common not in self._txt_cmds[fo]:
                content.append(line)
                content_common.append(line_common)
        self._txt_cmds[fo].extend(content_common)
        if content:
            if first:
                fo.write('{0}\n'.format('\n'.join(content)))
            else:
                fo.write('\n{0}\n'.format('\n'.join(content)))
        return True

    def write_vector_output(self, vlo, output: 'Output') -> bool:
        # Build a case-insensitive lookup from the registered field names so that
        # attribute keys that differ only in case are mapped to the canonical name.
        # This matches the original OGR behaviour where SetField() silently ignored
        # keys that did not match any defined field.
        field_name_map = {}
        for fname in output.field_map.keys():
            actual = fname[:10] if self.settings.gis_format == 'SHP' else fname
            field_name_map[actual.lower()] = actual

        attrs = {}
        for k, v in output.content.attributes.items():
            k_norm = k[:10] if self.settings.gis_format == 'SHP' else k
            canonical = field_name_map.get(k_norm.lower())
            if canonical is not None:
                attrs[canonical] = v

        vlo.add_feature(output.content.geom, attrs)
        return True

    def open_output(self, output: 'Output') -> typing.Union[typing.TextIO, object]:
        if not hasattr(output, 'fpath'):
            return  # if no file, can't open anything
        if not Path(output.fpath.parent).exists():
            Path(output.fpath.parent).mkdir(parents=True)
        key = self.get_key(output)
        hnd = self._key2hnd.get(key)
        if hnd:
            return hnd
        if output.TYPE in ['FILE', 'CONTROL']:
            hnd = self.open_text_file(key, output)
        elif output.TYPE == 'GIS':
            hnd = self.open_vector_file(key, output)
        if hnd:
            self.open_outputs.append(output)
        return hnd

    def close_output(self, output: 'Output') -> None:
        key = self.get_key(output)
        fo = self._key2hnd.get(key)
        if fo:
            if output.TYPE in ['FILE', 'CONTROL']:
                self.close_text_file(key, fo)
            elif output.TYPE == 'GIS':
                self.close_vector_file(key, fo)
        self.open_outputs.remove(output)

    def open_text_file(self, key: str, output: 'Output') -> typing.TextIO:
        if not output.fpath.parent.exists():
            output.fpath.parent.mkdir(parents=True)
        fo = output.fpath.open('w')
        self.open_files.append(output.fpath)
        self._key2openfile[key] = output.fpath
        self._key2hnd[key] = fo
        return fo

    def close_text_file(self, key: str, fo: typing.TextIO) -> None:
        fo.close()
        self._key2hnd.pop(key)
        if fo in self._txt_cmds:
            self._txt_cmds.pop(fo)
        open_file = self._key2openfile.pop(key)
        self.open_files.remove(open_file)

    def open_vector_file(self, key: str, output: 'Output'):
        from ..._tmf.tfpathlib import TuflowPath
        tfpath = TuflowPath(f'{output.fpath} >> {output.lyrname}')
        geom_str = _OGR_WKB_TO_GEOM_STR.get(output.geom_type)
        # Pass crs_ directly when it's a pyproj.CRS (open_gis accepts it natively);
        # fall back to the string representation otherwise.
        crs = self.settings.crs_ if self.settings.crs_ is not None else self.settings.crs
        vlo = tfpath.open_gis('w', geometry_type=geom_str, crs=crs)
        for field_name, field_info in output.field_map.items():
            name = field_name[:10] if self.settings.gis_format == 'SHP' else field_name
            vlo.create_field(
                name,
                field_info['type'],
                width=field_info.get('width'),
                prec=field_info.get('prec'),
            )
        open_file = f'{output.fpath} >> {output.lyrname}'
        self.open_files.append(open_file)
        self._key2openfile[key] = open_file
        self._key2hnd[key] = vlo
        return vlo

    def close_vector_file(self, key: str, vlo) -> None:
        self._key2hnd.pop(key)
        open_file = self._key2openfile.pop(key)
        self.open_files.remove(open_file)
        vlo.close()
