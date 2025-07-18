# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import sys
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

if TYPE_CHECKING:
    from docutils.nodes import Node


sys.path.append((Path(__file__).resolve().parents[1]).as_posix())
sys.path.append((Path(__file__).resolve().parent / '_ext').as_posix())

project = 'pytuflow'
copyright = '2025, BMT'
author = 'Ellis Symons'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.napoleon',
    'tuflowlexer',
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
# html_static_path = ['_static']


class CustomPythonDomain(PythonDomain):
    """Override the Python domain to remove fragments from cross-page links when using :py:class:."""

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        result = super().resolve_xref(env, fromdocname, builder, typ, target, node, contnode)
        if result and "refuri" in result:
            refuri = result["refuri"]
            if "#" in refuri:
                ref_page, ref_anchor = refuri.split("#", 1)
                # Only modify links for :py:class: references
                if ref_page != fromdocname and typ == "class":
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
    app.connect("autodoc-skip-member", skip_member)
    app.add_domain(CustomPythonDomain, override=True)
