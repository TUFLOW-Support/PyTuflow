from .bc_tables_result_item import BCTablesResultItem


class Boundary(BCTablesResultItem):
    """Boundary class for bc_tables."""

    def __repr__(self) -> str:
        return f'<Boundary: {self.name}>'
