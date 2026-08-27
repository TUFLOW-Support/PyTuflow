class DefineBlock:

    def __init__(self, type_, name_):
        self.type = type_
        self.name = name_
        self.first_if_written = True
        self.any_if_written = False

    def __eq__(self, other):
        if isinstance(other, DefineBlock):
            return self.type == other.type and self.name == other.name
        return False
