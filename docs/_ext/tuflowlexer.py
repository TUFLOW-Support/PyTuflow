# _ext/tuflowlexer.py

from pygments.lexer import RegexLexer, include, words, bygroups
from pygments.token import Text, Comment, Operator, Keyword, Name, String, \
    Number, Punctuation, Generic, Other, Error, Whitespace


def setup(app):
    app.add_lexer('tuflow', TuflowLexer)


class TuflowLexer(RegexLexer):
    """Lexer for TUFLOW control files."""

    name = 'TUFLOW'
    url = 'https://www.tuflow.com'
    aliases = ['tuflow', 'tf']
    filenames = ['*.tcf', '*.tgc', '*.tbc', '*.tlf', '*.ecf', '*.tscf', '*.toc', '*.tsf', '*.tesf', '*.trfc']
    mimetypes = ['text/x-tuflow']

    tokens = {
        'root': [
            (r'\n', Whitespace),
            (r'^(\s*)([ A-Za-z0-9]+)((?:==)?)([ A-Za-z0-9_&>.\\/|]*)',
             bygroups(Whitespace, Keyword, Operator, Text)),
            (r'[#!].*$', Comment.Single)
        ],
    }
