import setuptools

def get_long_description():
    with open("README.md", "r") as fh:
        return fh.read()

def get_version():
    with open('./pytuflow/__init__.py', 'r') as f:
        return {x.split(' = ')[0].strip('\'" \n\t'): x.split(' = ')[1].strip('\'" \n\t') for x in f.read().split('\n') if len(x.split(' = ')) == 2}['__version__']

setuptools.setup(
    version=get_version(),
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    package_data={
        'pytuflow._tmf.tmf.data': ['*.json'],
        'pytuflow._tmf.tmf.convert_tuflow_model_gis_format.conv_tf_gis_format.data': ['*.json'],
        'pytuflow._fm_to_estry.data': ['*.json'],
        'pytuflow._outputs.data': ['*.json'],
    },
    include_package_data=True,
)
