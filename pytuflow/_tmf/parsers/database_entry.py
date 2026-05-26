import re


class DatabaseEntry:

    def __init__(self, line, settings):
        self.line = line.strip('\n"\'')
        self.settings = settings
        self.header = False
        self.comment = False
        self.empty_line = False
        self.split_line = []
        self.file_ref = None
        self.new_file_ref = None
        self.new_line = None
        self.parse_line(self.line)

    def __repr__(self):
        return f'{self.line}'

    def parse_line(self, line):
        self.split_line = [x.strip() for x in re.split(r",(?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)", line)]
        for i, x in enumerate(self.split_line):
            if ',' not in x:
                # noinspection PyTypeChecker
                self.split_line[i] = x.strip('\'"')
        if len(self.split_line) < 2:
            return
        if not self.split_line[1]:
            return
        file = self.split_line[1].strip()
        try:
            float(file.strip('\'"').split(',')[0])
        except ValueError:
            file = self.settings.control_file.parent / file
            self.file_ref = file

    def replace_file_ref(self, file_ref):
        self.new_file_ref = file_ref
        if not self.new_file_ref:
            self.new_line = '{0}\n'.format(self.line)
        else:
            self.new_line = '{0},{1}'.format(self.split_line[0], self.new_file_ref)
            if len(self.split_line) > 2:
                self.new_line = '{0},{1}'.format(self.new_line, ','.join(self.split_line[2:]))
            self.new_line = '{0}\n'.format(self.new_line)
        return self.new_line
