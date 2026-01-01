import typing
from pathlib import Path

from .alembic import Alembic

if typing.TYPE_CHECKING:
    from ..import Mesh3DMixin
    from .. import FormatConvention
    from ... import PyMesh


class AlembicMixin:

    def to_alembic(self: 'Mesh3DMixin | PyMesh',
                   output_path: Path | str,
                   time_sample_frequency: float = 1,
                   data_types: typing.Iterable[str] = ('Depth', 'Vector Velocity-x', 'Vector Velocity-y'),
                   uv_projection_extent: 'typing.Iterable[float] | Bbox2D' = (),
                   time_sampling: float = 1 / 24,
                   format_convention: 'FormatConvention' = 1  # FormatConvention.Blender
                   ):
        from .. import FormatConvention
        format_convention = FormatConvention(format_convention)
        p = Path(output_path)
        if not p.parent.exists():
            p.mkdir(parents=True)

        alembic = Alembic()
        with alembic.open(output_path):
            mesh = alembic.add_mesh(self.name, time_sampling)
            for i, time in enumerate(self.times('Water Level')):
                if i % time_sample_frequency:
                    continue
                mesh3d = self.mesh3d(-1, i, data_types, uv_projection_extent, format_convention, reverse_winding_order=True)
                mesh.add_mesh_sample(mesh3d)
