from hatchling.metadata.plugin.interface import MetadataHookInterface


def get_version():
    with open('./pytuflow/__init__.py', 'r') as f:
        return {x.split(' = ')[0].strip('\'" \n\t'): x.split(' = ')[1].strip('\'" \n\t') for x in f.read().split('\n') if len(x.split(' = ')) == 2}['__version__']


class CustomMetadataHook(MetadataHookInterface):

    def update(self, metadata):
        metadata['version'] = get_version()
