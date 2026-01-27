import typing
from pathlib import Path

import numpy as np

from . import GLTF

if typing.TYPE_CHECKING:
    from .. import Mesh3DMixin
    from ... import Bbox2D


class GLTFMixin:

    def to_gltf(self: 'Mesh3DMixin',
                output_path: Path | str,
                mesh_geometry: str = '',
                time: float = -1,
                vertex_colour: list[str] = (),
                uv_projection_extent: 'list[float] | tuple[float] | np.ndarray | Bbox2D' = (),
                ):
        from .. import FormatConvention
        p = Path(output_path)
        if not p.parent.exists():
            p.mkdir(parents=True)
        mesh3d = self.mesh3d(
            mesh_geometry,
            time,
            vertex_colour,
            uv_projection_extent,
            FormatConvention.OpenGL,
            reverse_winding_order=False
        )
        gltf = GLTF()
        gltf.add_mesh(mesh3d)
        gltf.write(str(output_path))
