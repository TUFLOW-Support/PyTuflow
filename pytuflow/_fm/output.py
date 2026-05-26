import json
import typing
from collections import OrderedDict
from pathlib import Path

from .helpers.gis import FeatureMap


class OutputCollection(list):

    def __repr__(self) -> str:
        return '<OutputCollection>'
    def __str__(self) -> str:
        return self.to_json()

    def to_json(self) -> str:
        lst = [json.loads(x.to_json()) for x in self]
        return json.dumps(lst, indent=2, ensure_ascii=True)

    def find_output(self, search: str, type_: str = 'ALL', count: int = 1) -> typing.Union['Output', typing.List['Output']]:
        all = []
        for output in self.__iter__():
            if type_ == 'ALL' or output.TYPE == type_.upper():
                if output.match(search):
                    all.append(output)
                if len(all) == count:
                    if count == 1:
                        return all[0]
                    return all


class Output:

    def __new__(cls, type_: str, id_: str = None, *args, **kwargs) -> object:
        if type_.upper() == 'FILE':
            cls = FileOutput
        elif type_.upper() == 'GIS':
            cls = GISOutput
        elif type_.upper() == 'CONTROL':
            cls = ControlOutput
        return super().__new__(cls)

    def __init__(self, type_: str, id_: str = None, *args, **kwargs) -> None:
        super().__init__()
        self.TYPE = type_.upper()
        self.id = id_

    def __repr__(self) -> str:
        if hasattr(self, 'fpath') and self.fpath:
            return f'<{self.__class__.__name__} ({self.fpath.name})>'
        return f'<{self.__class__.__name__}>'

    def to_json(self) -> str:
        pass

    def match(self, search: str) -> bool:
        return search.upper() == self.TYPE


class FileOutput(Output):

    def __init__(self, type_: str, id_: str = None) -> None:
        super().__init__(type_, id_)
        self.fpath: Path = None
        self.content: typing.Any = None

    def to_json(self) -> str:
        d = OrderedDict()
        d['type'] = self.TYPE
        d['file_path'] = self.fpath.as_posix()
        d['content'] = self.content
        return json.dumps(d, indent=2, ensure_ascii=True)

    def match(self, search: str) -> bool:
        if super().match(search):
            return True
        return search.lower() in str(self.fpath).lower()


class ControlOutput(FileOutput):
    """Control File or Database."""
    pass


class GISOutput(FileOutput):

    def __init__(self, type_: str, id_: str = None) -> None:
        super().__init__(type_, id_)
        self.lyrname: str = None
        self.field_map: OrderedDict = OrderedDict()
        self.geom_type: int = None
        self.content = FeatureMap()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} ({self.lyrname})>'

    def to_json(self) -> str:
        d = OrderedDict()
        d['type'] = self.TYPE
        d['file_path'] = self.fpath.as_posix()
        d['layer_name'] = self.lyrname
        d['geometry'] = self.content.geom
        d['attributes'] = self.content.attributes
        return json.dumps(d, indent=2, ensure_ascii=True)

    def match(self, search: str) -> bool:
        if super().match(search):
            return True
        if search.lower() in self.lyrname.lower():
            return True
        if self.content.attributes:
            for value in self.content.attributes.values():
                if isinstance(value, str):
                    if search.lower() in value.lower():
                        return True
        return False
