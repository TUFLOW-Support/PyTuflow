from ...pytuflow._tmf.tfstrings.patterns import identify_expanded_name, extract_names_from_pattern, replace_exact_names


def test_name_from_pattern_simple():
    template = '<<~s~>>_001.tcf'
    input_string = 'EG00_001.tcf'
    names = identify_expanded_name(template, input_string, '<<~s~>>')
    assert names == ['EG00']


def test_name_from_pattern_simple_2():
    template = '<<~s1~>>_<<~s2~>>_001.tcf'
    input_string = 'EG00_5m_001.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['EG00']
    names = identify_expanded_name(template, input_string, '<<~s2~>>')
    assert names == ['5m']


def test_name_from_filepath_simple():
    template = r'c:\tuflow\model\<<~s1~>>_<<~s1~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG00_EG00_001.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['EG00', 'EG00']


def test_name_from_filepath_simple_2():
    template = r'c:\tuflow\<<~s1~>>\<<~s1~>>_001.tcf'
    input_string = r'c:\tuflow\EG00\EG00_001.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['EG00', 'EG00']


def test_name_from_filepath_simple_3():
    template = r'c:\tuflow\model\EG00<<~s1~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG005m_001.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['5m']


def test_name_from_filepath_no_match():
    template = r'c:\tuflow\model\<<~s1~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG00_5m_002.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['']


def test_name_from_filepath_no_match_2():
    template = r'c:\tuflow\model\<<~s1~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG00_5m_002.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['']


def test_name_from_filepath_ambiguous():
    template = r'c:\tuflow\model\<<~s1~>><<~s2~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG005m_001.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['']
    names = identify_expanded_name(template, input_string, '<<~s2~>>')
    assert names == ['']


def test_name_from_filepath_ambiguous_2():
    template = r'c:\tuflow\model\<<~s1~>><<~s2~>>_<<~s1~>><<~s2~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG005m_EG005m_001.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['', '']
    names = identify_expanded_name(template, input_string, '<<~s2~>>')
    assert names == ['', '']


def test_name_from_filepath_less_ambiguous():
    template = r'c:\tuflow\model\<<~s1~>><<~s2~>>_<<~s1~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG005m_EG00_001.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['', 'EG00']
    names = identify_expanded_name(template, input_string, '<<~s2~>>')
    assert names == ['']


def test_name_from_filepath_less_ambiguous_2():
    template = r'c:\tuflow\model\<<~s1~>><<~s2~>>_<<~s2~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG005m_5m_001.tcf'
    names = identify_expanded_name(template, input_string, '<<~s1~>>')
    assert names == ['']
    names = identify_expanded_name(template, input_string, '<<~s2~>>')
    assert names == ['', '5m']


def test_extract_names():
    names = extract_names_from_pattern('2d_code_<<~s1~>>_001.shp', '2d_code_EG00_001.shp', r'<<~[sSeE]\d?~>>')
    assert names == {'<<~s1~>>': 'EG00'}


def test_extract_names_duplicates():
    names = extract_names_from_pattern('2d_code_<<~s1~>>_<<~s1~>>_001.shp', '2d_code_EG00_EG00_001.shp', r'<<~[sSeE]\d?~>>')
    assert names == {'<<~s1~>>': 'EG00'}


def test_extract_names_variables():
    names = extract_names_from_pattern('2d_code_<<CELL_SIZE>>_001.shp', '2d_code_5m_001.shp', r'<<CELL_SIZE>>')
    assert names == {'<<CELL_SIZE>>': '5m'}


def test_extract_names_ambiguous():
    template = r'c:\tuflow\model\<<~s1~>><<~s2~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG005m_001.tcf'
    names = extract_names_from_pattern(template, input_string, r'<<~[sSeE]\d?~>>')
    assert names == {'<<~s1~>>': '<<~s1~>>', '<<~s2~>>': '<<~s2~>>'}


def test_extract_names_ambiguous_2():
    template = r'c:\tuflow\model\<<~s1~>><<~s2~>>_<<~s1~>>_001.tcf'
    input_string = r'c:\tuflow\model\EG005m_EG00_001.tcf'
    names = extract_names_from_pattern(template, input_string, r'<<~[sSeE]\d?~>>')
    assert names == {'<<~s1~>>': 'EG00', '<<~s2~>>': '<<~s2~>>'}


def test_extract_names_ambiguous_edge_case_maybe():
    template = r'c:\tuflow\model\_ARI__DUR__<<~s1~>>_001.tcf'
    input_string = r'c:\tuflow\model\100yr2hr_EG00_001.tcf'
    names = extract_names_from_pattern(template, input_string, r'<<~[sSeE]\d?~>>')
    assert names == {'<<~s1~>>': '<<~s1~>>'}


def test_extract_names_ambiguous_edge_case_maybe_2():
    template = r'c:\tuflow\model\_ARI__DUR__<<~s1~>><<~s2~>>_001.tcf'
    input_string = r'c:\tuflow\model\100yr2hr_EG005m_001.tcf'
    names = extract_names_from_pattern(template, input_string, r'<<~[sSeE]\d?~>>')
    assert names == {'<<~s1~>>': '<<~s1~>>', '<<~s2~>>': '<<~s2~>>'}


def test_extract_names_ambiguous_edge_case_maybe_3():
    template = r'c:\tuflow\model\_ARI__DUR__<<~s1~>><<~s2~>>_<<~s1~>>_001.tcf'
    input_string = r'c:\tuflow\model\100yr2hr_EG005m_EG00_001.tcf'
    names = extract_names_from_pattern(template, input_string, r'<<~[sSeE]\d?~>>')
    assert names == {'<<~s1~>>': '<<~s1~>>', '<<~s2~>>': '<<~s2~>>'}


def test_extract_names_ambiguous_edge_case_maybe_4():
    template = r'c:\tuflow\model\_ARI__DUR__<<~s1~>><<~s2~>>_<<~s2~>>_001.tcf'
    input_string = r'c:\tuflow\model\100yr2hr_EG005m_5m_001.tcf'
    names = extract_names_from_pattern(template, input_string, r'<<~[sSeE]\d?~>>')
    assert names == {'<<~s1~>>': '<<~s1~>>', '<<~s2~>>': '<<~s2~>>'}


def test_replace_exact_names():
    pattern = r'<<~[Ss]\d?~>>'
    map = {'S1': 'EG00'}
    input_string = r'c:\tuflow\model\2d_code_<<~s1~>>_001.tcf'
    output_string = replace_exact_names(pattern, map, input_string)
    assert output_string == r'c:\tuflow\model\2d_code_EG00_001.tcf'


def test_replace_exact_names_no_sub():
    pattern = r'<<~[Ss]~>>'
    map = {'S1': 'EG00'}
    input_string = r'c:\tuflow\model\2d_code_EG00_001.tcf'
    output_string = replace_exact_names(pattern, map, input_string)
    assert output_string == r'c:\tuflow\model\2d_code_EG00_001.tcf'


def test_replace_exact_names_no_sub_2():
    pattern = r'<<~[Ss]\d?~>>'
    map = {'S1': 'EG00'}
    input_string = r'c:\tuflow\model\2d_code_<<~e1~>>_001.tcf'
    output_string = replace_exact_names(pattern, map, input_string)
    assert output_string == r'c:\tuflow\model\2d_code_<<~e1~>>_001.tcf'


def test_replace_exact_names_no_sub_3():
    pattern = r'<<~[Ss]\d?~>>'
    map = {'S1': 'EG00'}
    input_string = 5
    output_string = replace_exact_names(pattern, map, input_string)
    assert output_string == 5


def test_replace_exact_names_no_sub_4():
    pattern = r'<<~s2~>>'
    map = {'S1': 'EG00'}
    input_string = r'c:\tuflow\model\2d_code_<<~s2~>>_001.tcf'
    output_string = replace_exact_names(pattern, map, input_string)
    assert output_string == r'c:\tuflow\model\2d_code_<<~s2~>>_001.tcf'


def test_replace_exact_names_var_name():
    pattern = r'variable pattern'
    map = {'CELL_SIZE': '5m'}
    input_string = r'c:\tuflow\model\2d_code_<<CELL_SIZE>>_001.tcf'
    output_string = replace_exact_names(pattern, map, input_string)
    assert output_string == r'c:\tuflow\model\2d_code_5m_001.tcf'


def test_replace_exact_names_var_name_int():
    pattern = r'variable pattern'
    map = {'CELL_SIZE': 5}
    input_string = '<<CELL_SIZE>>'
    output_string = replace_exact_names(pattern, map, input_string)
    assert output_string == 5


def test_replace_exact_names_var_name_float():
    pattern = r'variable pattern'
    map = {'CELL_SIZE': 5.5}
    input_string = '<<CELL_SIZE>>'
    output_string = replace_exact_names(pattern, map, input_string)
    assert output_string == 5.5


def test_replace_exact_names_2():
    pattern = r'<<~s~>>'
    map = {'S1': 'EG00'}
    input_string = r'c:\tuflow\model\2d_code_<<~s~>>_001.tcf'
    output_string = replace_exact_names(pattern, map, input_string)
    assert output_string == r'c:\tuflow\model\2d_code_EG00_001.tcf'
