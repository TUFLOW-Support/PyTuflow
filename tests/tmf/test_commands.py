from pytuflow._tmf.parsers.command import EventCommand, Command
from pytuflow._tmf.parsers.non_recursive_basic_parser import get_commands
from pytuflow._tmf.settings import TCFConfig


def test_import():
    pass


def test_re_add_comments():
    text = 'SHP Projection == <placeholder>                   ! comment'
    cmd = Command(text, TCFConfig())

    assert cmd.comment_index == 50

    new_text = cmd.re_add_comments('SHP Projection == ../model/gis/projection.prj')
    assert new_text.index('!') == 50
