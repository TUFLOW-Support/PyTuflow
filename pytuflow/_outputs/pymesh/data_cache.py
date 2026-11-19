import typing


class Cache:
    # cache types that are valid to use while planning a progress-tracked extraction (i.e. do not hold extracted data)
    PLANNING_SAFE = {'translate_data_type', 'times', 'reference_time', 'is_vector', 'is_static', 'on_vertex', 'is_3d',
                     'mesh_line', 'loaded_in_memory'}

    def __init__(self):
        self._cache = {}
        self.planning = False

    def clear(self, *key: typing.Any):
        k = '::'.join([str(x) for x in key])
        if k:
            self._cache.pop(k, None)
        else:
            self._cache.clear()

    def contains(self, type_: str, *key: typing.Any) -> bool:
        if self.planning and type_.lower() not in self.PLANNING_SAFE:
            return False
        k = '::'.join([str(x) for x in key])
        return type_.lower() in self._cache and k.lower() in self._cache[type_]

    def get(self, type_: str, *key: typing.Any) -> typing.Any:
        k = '::'.join([str(x) for x in key])
        if not self.contains(type_, *key):
            raise KeyError(f'{type_}::{key} not found')
        return self._cache[type_.lower()][k.lower()]

    def set(self, value: typing.Any, type_: str, *key: typing.Any):
        if self.planning and type_.lower() not in self.PLANNING_SAFE:
            return
        k = '::'.join([str(x) for x in key])
        if type_.lower() not in self._cache:
            self._cache[type_.lower()] = {}
        self._cache[type_.lower()][k.lower()] = value
