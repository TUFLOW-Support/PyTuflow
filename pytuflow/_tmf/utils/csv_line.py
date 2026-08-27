import re

REGEX = re.compile(r',(?=(?:[^"]*"[^"]*")*[^"]*$)')


def csv_line_split(line: str) -> list[str]:
    """
    Split a CSV line into parts, handling quoted strings correctly.

    Args:
        line (str): The CSV line to split.

    Returns:
        list[str]: A list of parts from the CSV line.
    """
    if not line:
        return []
    return [part.strip('"') for part in REGEX.split(line.strip())]
