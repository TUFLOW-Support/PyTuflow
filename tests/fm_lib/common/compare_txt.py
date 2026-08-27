from pathlib import Path


def compare_txt(file1: Path, file2: Path):
    with file1.open() as f1:
        with file1.open() as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()
            assert len(lines1) == len(lines2), f'compare_txt(file1, file2): length of lines do not match:\nfile1: {len(lines1)}\nfile2: {len(lines2)}'
            for i, line1 in enumerate(f1):
                for line2 in f2:
                    assert line1 == line2, f'compare_txt(file1, file2): {file1} line {i} does not match {file2}:\nfile1: {line1}\nfile2: {line2}'
