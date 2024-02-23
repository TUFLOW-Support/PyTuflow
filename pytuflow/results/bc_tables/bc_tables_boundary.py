from .bc_tables_result_item import BCTablesResultItem


class Boundary(BCTablesResultItem):

    def __repr__(self) -> str:
        return f'<Boundary: {self.name}>'
