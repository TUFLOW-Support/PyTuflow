import typing
from pathlib import Path

import numpy as np
from .alembic import Alembic

if typing.TYPE_CHECKING:
    from ..import Mesh3DMixin
    from .. import FormatConvention
    from ... import PyMesh, Bbox2D, Transform2D


class AlembicMixin:

    def to_alembic(self: 'Mesh3DMixin | PyMesh',
                   output_path: Path | str,
                   mesh_geometry: str = '',
                   vertex_colour: list[str] = (),
                   uv_projection_extent: 'list[float] | tuple[float] | np.ndarray | Bbox2D' = (),
                   transform: 'Transform2D' = None,
                   time_sample_frequency: float = 1,
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
                mesh3d = self.mesh3d(
                    mesh_geometry,
                    time,
                    vertex_colour,
                    uv_projection_extent,
                    format_convention,
                    self.geom.winding_order == 'CW',
                    transform,
                )
                mesh.add_mesh_sample(mesh3d)
