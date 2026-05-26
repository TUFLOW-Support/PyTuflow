import struct


# noinspection DuplicatedCode
def unpack_fixed_field(input_string, col_widths):
    """Unpacks input string based on fixed field lengths described in col_widths.
    The function will return a list of the split columns.

    The function will handle most situations where the input string length
    is shorter than the input fixed fields.

    Parameters
    ----------
    input_string : str
        The string to be split.
    col_widths : tuple[int] | list[int]
        list of column widths

    Returns
    -------
    list[str]
        The split columns.
    """

    sum_ = 0
    new_widths = []
    for len_ in col_widths:
        if len(input_string) <= sum_ + len_:
            if len(input_string) - sum_ < 1:
                break
            else:
                new_widths.append(len(input_string) - sum_)
                break
        else:
            new_widths.append(len_)
            sum_ += len_

    fmtstring = ' '.join('{0}{1}'.format(abs(len_), 'x' if len_ < 0 else 's') for len_ in new_widths)
    return [x.decode('utf-8') for x in struct.unpack_from(fmtstring, input_string.encode())]
