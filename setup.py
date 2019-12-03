import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pytuflow",
    version="0.0.6",
    author="tuflowsupport",
    author_email="support@tuflow.com",
    description="Package for scripting TUFLOW time series results.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/TUFLOW-Support/PyTuflow",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
)