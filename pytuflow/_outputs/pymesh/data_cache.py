import typing


class Cache:

    def __init__(self):
        self._cache = {}

    def contains(self, type_: str, *key: typing.Any) -> bool:
        k = '::'.join([str(x) for x in key])
        return type_.lower() in self._cache and k.lower() in self._cache[type_]

    def get(self, type_: str, *key: typing.Any) -> typing.Any:
        k = '::'.join([str(x) for x in key])
        if not self.contains(type_, *key):
            raise KeyError(f'{type_}::{key} not found')
        return self._cache[type_.lower()][k.lower()]

    def set(self, value: typing.Any, type_: str, *key: typing.Any):
        k = '::'.join([str(x) for x in key])
        if type_.lower() not in self._cache:
            self._cache[type_.lower()] = {}
        self._cache[type_.lower()][k.lower()] = value
