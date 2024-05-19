# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import sys
from pathlib import Path
from sphinx.application import Sphinx


sys.path.append((Path(__file__).resolve().parents[1]).as_posix())

project = 'pytuflow'
copyright = '2024, Ellis Symons'
author = 'Ellis Symons'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.napoleon'
]
autosummary_generate = True
autodoc_typehints = 'description'

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_book_theme'
html_static_path = ['_static']

def skip_member(app: Sphinx, what: str, name: str, obj, skip, options):
    if name.startswith('_'):
        return True
    skip_methods = [
        'init_iterator',
        'load',
        'looks_empty',
        'looks_like_self',
    ]
    return name in skip_methods

def setup(app: Sphinx):
    app.connect(event='autodoc-skip-member', callback=skip_member)

