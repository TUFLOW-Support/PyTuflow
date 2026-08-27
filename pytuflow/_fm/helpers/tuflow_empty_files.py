from collections import OrderedDict


def tuflow_empty_field_map(empty_type: str) -> OrderedDict:
    """
    Return empty field type for the given empty type.

    :param empty_type: str
    :return: OrderedDict
    """

    if empty_type.lower() == '1d_nwk':
        return _1d_nwk_empty()
    elif empty_type.lower() == '1d_tab':
        return _1d_tab_empty()


def _1d_tab_empty() -> OrderedDict:
    """
    1d_tab empty type fields.

    :return: OrderedDict
    """

    fields = OrderedDict(
        {
            'Source': {'type': 'str', 'width': 50},
            'Type': {'type': 'str', 'width': 2},
            'Flags': {'type': 'str', 'width': 8},
            'Column_1': {'type': 'str', 'width': 20},
            'Column_2': {'type': 'str', 'width': 20},
            'Column_3': {'type': 'str', 'width': 20},
            'Column_4': {'type': 'str', 'width': 20},
            'Column_5': {'type': 'str', 'width': 20},
            'Column_6': {'type': 'str', 'width': 20},
            'Z_Increment': {'type': 'float', 'width': 15, 'prec': 5},
            'Z_Maximum': {'type': 'float', 'width': 15, 'prec': 5},
            'Skew': {'type': 'float', 'width': 15, 'prec': 5},
            'Comment_1': {'type': 'str', 'width': 100},
            'Comment_2': {'type': 'str', 'width': 100}
        }
    )

    return fields


def _1d_nwk_empty() -> OrderedDict:
    """
    1d_nwk empty type fields.

    :return: OrderedDict
    """

    fields = OrderedDict(
        {
            'ID': {'type': 'str', 'width': 36},
            'Type': {'type': 'str', 'width': 36},
            'Ignore': {'type': 'str', 'width': 1},
            'UCS': {'type': 'str', 'width': 1},
            'Len_or_ANA': {'type': 'float', 'width': 15, 'prec': 5},
            'n_nf_Cd': {'type': 'float', 'width': 15, 'prec': 5},
            'US_Invert': {'type': 'float', 'width': 15, 'prec': 5},
            'DS_Invert': {'type': 'float', 'width': 15, 'prec': 5},
            'Form_Loss': {'type': 'float', 'width': 15, 'prec': 5},
            'pBlockage': {'type': 'float', 'width': 15, 'prec': 5},
            'Inlet_Type': {'type': 'str', 'width': 256},
            'Conn_1D_2D': {'type': 'str', 'width': 4},
            'Conn_No': {'type': 'int', 'width': 8},
            'Width_or_Dia': {'type': 'float', 'width': 15, 'prec': 5},
            'Height_or_WF': {'type': 'float', 'width': 15, 'prec': 5},
            'Number_of': {'type': 'int', 'width': 8},
            'HConF_or_WC': {'type': 'float', 'width': 15, 'prec': 5},
            'WConF_or_WEx': {'type': 'float', 'width': 15, 'prec': 5},
            'EntryC_or_WSa': {'type': 'float', 'width': 15, 'prec': 5},
            'ExitC_or_WSb': {'type': 'float', 'width': 15, 'prec': 5},
        }
    )

    return fields
