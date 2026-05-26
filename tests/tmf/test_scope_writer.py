import io

from ...pytuflow._tmf.scope_writer import ScopeWriter
from ...pytuflow._tmf.scope import Scope, ScopeList
from ...pytuflow._tmf.cf.tcf import TCF


def test_write_else_if():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC')]
    inp2.scope = [Scope('Scenario', 'CLA')]
    buf = io.StringIO()
    tcf.preview(buf)
    text = (
        'If Scenario == HPC\n'
        '    Solution Scheme == HPC\n'
        'End If\n'
        'If Scenario == CLA\n'
        '    Solution Scheme == Classic\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_no_scope():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'Solution Scheme == HPC\n'
        'Solution Scheme == Classic\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_1():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1 = tcf.find_input('solution scheme')[0]
    inp1.scope = [Scope('Scenario', 'HPC')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    Solution Scheme == HPC\n'
        'End If\n'
        'Solution Scheme == Classic\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_2():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1 = tcf.find_input('solution scheme')[0]
    inp1.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', 'GPU')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    If Scenario == GPU\n'
        '        Solution Scheme == HPC\n'
        '    End If\n'
        'End If\n'
        'Solution Scheme == Classic\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_3():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', 'GPU')]
    inp2.scope = [Scope('Scenario', 'HPC')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    If Scenario == GPU\n'
        '        Solution Scheme == HPC\n'
        '    End If\n'
        '    Solution Scheme == Classic\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_4():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', 'GPU')]
    inp2.scope = [Scope('Scenario', 'CLA')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    If Scenario == GPU\n'
        '        Solution Scheme == HPC\n'
        '    End If\n'
        'End If\n'
        'If Scenario == CLA\n'
        '    Solution Scheme == Classic\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_5():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC')]
    inp2.scope = [Scope('Scenario', '!HPC')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    Solution Scheme == HPC\n'
        'Else\n'
        '    Solution Scheme == Classic\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_6():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', 'GPU')]
    inp2.scope = [Scope('Scenario', '!HPC')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    If Scenario == GPU\n'
        '        Solution Scheme == HPC\n'
        '    End If\n'
        'Else\n'
        '    Solution Scheme == Classic\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_7():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC')]
    inp2.scope = [Scope('Scenario', '!HPC'), Scope('Scenario', 'CLA')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    Solution Scheme == HPC\n'
        'Else If Scenario == CLA\n'
        '    Solution Scheme == Classic\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_9():
    p = './tests/tmf/test_datasets/test_scope_write_2.tcf'
    tcf = TCF(p)
    inp1, inp2, inp3 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC')]
    inp2.scope = [Scope('Scenario', '!HPC'), Scope('Scenario', 'CLA')]
    inp3.scope = [Scope('Scenario', '!HPC'), Scope('Scenario', '!CLA')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    Solution Scheme == HPC\n'
        'Else If Scenario == CLA\n'
        '    Solution Scheme == Classic\n'
        'Else\n'
        '    Solution Scheme == Default\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_10():
    p = './tests/tmf/test_datasets/test_scope_write_2.tcf'
    tcf = TCF(p)
    inp1, inp2, inp3 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC')]
    inp2.scope = [Scope('Scenario', '!HPC'), Scope('Scenario', 'CLA')]
    inp3.scope = [Scope('Scenario', '!HPC'), Scope('Scenario', '!CLA'), Scope('Scenario', 'Default')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    Solution Scheme == HPC\n'
        'Else If Scenario == CLA\n'
        '    Solution Scheme == Classic\n'
        'Else If Scenario == Default\n'
        '    Solution Scheme == Default\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_11():
    p = './tests/tmf/test_datasets/test_scope_write_2.tcf'
    tcf = TCF(p)
    inp1, inp2, inp3 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', 'GPU')]
    inp2.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', '!GPU')]
    inp3.scope = [Scope('Scenario', '!HPC'), Scope('Scenario', 'Default')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    If Scenario == GPU\n'
        '        Solution Scheme == HPC\n'
        '    Else\n'
        '        Solution Scheme == Classic\n'
        '    End If\n'
        'Else If Scenario == Default\n'
        '    Solution Scheme == Default\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_12():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC')]
    inp2.scope = [Scope('Scenario', '!GPU')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    Solution Scheme == HPC\n'
        'End If\n'
        'If Scenario == GPU\n'
        'Else\n'
        '    Solution Scheme == Classic\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_13():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', 'GPU')]
    inp2.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', '!Classic'), Scope('Scenario', 'Default')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    If Scenario == GPU\n'
        '        Solution Scheme == HPC\n'
        '    End If\n'
        '    If Scenario == Classic\n'
        '    Else If Scenario == Default\n'
        '        Solution Scheme == Classic\n'
        '    End If\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_14():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', 'GPU')]
    inp2.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', '!Classic'), Scope('Scenario', '!Default')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    If Scenario == GPU\n'
        '        Solution Scheme == HPC\n'
        '    End If\n'
        '    If Scenario == Classic\n'
        '    Else If Scenario == Default\n'
        '    Else\n'
        '        Solution Scheme == Classic\n'
        '    End If\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_write_scope_input_iterator_15():
    p = './tests/tmf/test_datasets/test_scope_write.tcf'
    tcf = TCF(p)
    inp1, inp2 = tcf.find_input('solution scheme')
    inp1.scope = [Scope('Scenario', 'HPC'), Scope('Scenario', '!GPU')]
    inp2.scope = [Scope('Scenario', '!HPC')]
    buf = io.StringIO()
    scope_writer = ScopeWriter()
    for inp, scope_writer_ in scope_writer.inputs(buf, tcf.inputs):
        inp.write(buf, scope_writer_)
    text = (
        'If Scenario == HPC\n'
        '    If Scenario == GPU\n'
        '    Else\n'
        '        Solution Scheme == HPC\n'
        '    End If\n'
        'Else\n'
        '    Solution Scheme == Classic\n'
        'End If\n'
    )
    assert buf.getvalue() == text


def test_no_infinite_loop():
    p = './tests/tmf/test_datasets/M01_2_5m_~s1~.tcf'
    tcf = TCF(p)
    roughness = tcf.find_input('Read Materials File')[0]
    plus = f'Read Materials File == Dummy_File | 1.2'
    minus = f'Read Materials File == Dummy_File | 0.8'
    minus_inp = tcf.insert_input(roughness, minus)
    plus_inp = tcf.insert_input(roughness, plus)
    plus_inp.scope = [Scope('Scenario', f'!-20pct'), Scope('Scenario', f'+20pct')]
    buf = io.StringIO()
    tcf.preview(buf=buf)
