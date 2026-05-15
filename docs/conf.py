# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import re
# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys
import locale
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sphinx.application import Sphinx
from sphinx.domains.python import PythonDomain
from sphinx.ext.autosummary import Autosummary, autosummary_table
from docutils import nodes
from docutils.statemachine import StringList
from sphinx.util import rst
from sphinx.util.docutils import switch_source_input
from sphinx import addnodes
from pyvista.ext.viewer_directive import OfflineViewerDirective

if TYPE_CHECKING:
    from docutils.nodes import Node


# locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')


sys.path.append((Path(__file__).resolve().parents[1]).as_posix())
sys.path.append((Path(__file__).resolve().parent / '_ext').as_posix())

# -- pyvista configuration ---------------------------------------------------
import pyvista as pv
from pyvista.core.errors import PyVistaDeprecationWarning
from pyvista.core.utilities.docs import linkcode_resolve  # noqa: F401
from pyvista.core.utilities.docs import pv_html_page_context
from pyvista.plotting.utilities.sphinx_gallery import DynamicScraper

# Manage errors
pv.set_error_output_file('errors.txt')
# Ensure that offscreen rendering is used for docs generation
pv.OFF_SCREEN = True  # Not necessary - simply an insurance policy
# Preferred plotting style for documentation
pv.set_plot_theme('document_build')
pv.set_jupyter_backend(None)
# Save figures in specified directory
pv.FIGURE_PATH = str(Path('./assets/images/').resolve() / 'auto-generated/')
if not Path(pv.FIGURE_PATH).exists():
    Path(pv.FIGURE_PATH).mkdir()

# necessary when building the sphinx gallery
pv.BUILDING_GALLERY = True
os.environ['PYVISTA_BUILDING_GALLERY'] = 'true'

project = 'PyTUFLOW'
copyright = f'{datetime.now().year}, BMT'
author = 'TUFLOW'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.napoleon',
    'sphinxcontrib.video',
    'tuflowlexer',
    'jupyter_sphinx',
    "pyvista.ext.plot_directive",
    "pyvista.ext.viewer_directive",
    "sphinx_design",
]
autosummary_generate = True
autodoc_typehints = 'description'
add_module_names = False

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_book_theme'
html_favicon = 'assets/favicon/TUFLOW.ico'
html_static_path = ['_static']
html_css_files = ['custom.css']
# html_js_files = ['custom.js']
html_baseurl = 'https://docs.tuflow.com/pytuflow/'

pygments_style = "friendly"


def strip_redundant_fragments(app: Sphinx, doctree, docname):
    for node in doctree.traverse(nodes.reference):
        if 'refuri' in node:
            refuri = node['refuri']
            if '#' in refuri:
                base, frag = refuri.split('#', 1)
                parts = base.split('/')
                if len(parts) < 2:
                    continue
                base_ = ''.join(re.split(r'\s|_|-', parts[-2]))
                frag_ = ''.join(re.split(r'\s|_|-', frag))
                if base_ == frag_:
                    node['refuri'] = base


class CustomPythonDomain(PythonDomain):
    """Override the Python domain to remove fragments from cross-page links when using :py:class:."""

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        result = super().resolve_xref(env, fromdocname, builder, typ, target, node, contnode)
        if result and "refuri" in result:
            refuri = result["refuri"]
            if "#" in refuri:
                ref_page, ref_anchor = refuri.split("#", 1)
                # Only modify links for :py:class: references
                if ref_page != fromdocname and typ in ["class", "meth", "attr", "func", "exc"]:
                    result["refuri"] = ref_page
        return result


class CustomAutosummary(Autosummary):

    def get_table(self, items: list[tuple[str, str, str, str]]) -> list[Node]:
        """Generate a proper list of table nodes for autosummary:: directive.

        *items* is a list produced by :meth:`get_items`.
        """
        table_spec = addnodes.tabular_col_spec()
        table_spec['spec'] = r'\X{1}{2}\X{1}{2}'

        table = autosummary_table('')
        real_table = nodes.table('', classes=['autosummary longtable'])
        table.append(real_table)
        group = nodes.tgroup('', cols=2)
        real_table.append(group)
        group.append(nodes.colspec('', colwidth=10))
        group.append(nodes.colspec('', colwidth=90))
        body = nodes.tbody('')
        group.append(body)

        def append_row(*column_texts: str) -> None:
            row = nodes.row('')
            source, line = self.state_machine.get_source_and_line()
            for text in column_texts:
                node = nodes.paragraph('')
                vl = StringList()
                vl.append(text, '%s:%d:<autosummary>' % (source, line))
                with switch_source_input(self.state, vl):
                    self.state.nested_parse(vl, 0, node)
                    try:
                        if isinstance(node[0], nodes.paragraph):
                            node = node[0]
                    except IndexError:
                        pass
                    row.append(nodes.entry('', node))
            body.append(row)

        for name, sig, summary, real_name in items:
            qualifier = 'class'
            if 'nosignatures' not in self.options:
                col1 = f':py:{qualifier}:`{name} <{real_name}>`\\ {rst.escape(sig)}'
            else:
                col1 = f':py:{qualifier}:`{name} <{real_name}>`'
            col2 = summary
            append_row(col1, col2)

        return [table_spec, table]
    
class DirHTMLOfflineViewerDirective(OfflineViewerDirective):
    """Fixes static_viewer.html path for dirhtml builder.

    pyvista computes the path to _static relative to the RST source depth, which
    is correct for the regular html builder. The dirhtml builder wraps each page
    in a sub-directory (api/foo/index.html instead of api/foo.html), adding one
    extra level, so the path needs an additional ../ prefix.
    """

    def run(self):
        result = super().run()
        if self.state.document.settings.env.app.builder.name == 'dirhtml':
            fixed = []
            for node in result:
                if isinstance(node, nodes.raw) and '_static/static_viewer.html' in node.astext():
                    fixed_html = node.astext().replace("'../_static/", "'../../_static/")
                    fixed.append(nodes.raw('', fixed_html, format='html'))
                else:
                    fixed.append(node)
            return fixed
        return result


class ResetPyVista:
    """Reset pyvista module to default settings."""

    def __call__(self, gallery_conf, fname):  # noqa: ARG002
        """Reset pyvista module to default settings.

        If default documentation settings are modified in any example, reset here.
        """
        _filter_sphinx_gallery_warnings()
        import matplotlib as mpl  # must import before pyvista

        # clear all mpl figures, force non-interactive backend, and reset defaults
        mpl.use('Agg', force=True)
        mpl.pyplot.close('all')
        mpl.rcdefaults()
        mpl.pyplot.figure().clear()
        mpl.pyplot.close()

        import pyvista as pv

        pv._wrappers['vtkPolyData'] = pv.PolyData
        pv.set_plot_theme('document_build')

    def __repr__(self):
        return 'ResetPyVista'


def skip_member(app, what, name, obj, skip, options):
    # Optionally skip all private methods:
    if name.startswith("_"):
        return True

    # Or skip based on docstring tag
    doc = getattr(obj, '__doc__', '') or ''
    if doc.startswith('no-doc'):
        return True

    return skip  # fallback to default behavior


def setup(app: Sphinx):
    app.add_directive("autosummary", CustomAutosummary, override=True)
    app.add_directive("offlineviewer", DirHTMLOfflineViewerDirective, override=True)
    app.connect("autodoc-skip-member", skip_member)
    app.connect('doctree-resolved', strip_redundant_fragments)
    app.add_domain(CustomPythonDomain, override=True)
