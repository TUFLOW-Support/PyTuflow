import typing
from pathlib import Path

from . import GLTF

if typing.TYPE_CHECKING:
    from .. import Mesh3DMixin
    from ... import Bbox2D


class GLTFMixin:

    def to_gltf(self: 'Mesh3DMixin',
                output_path: Path | str,
                time: float = -1,
                time_index: int = -1,
                data_types: typing.Iterable[str] = ('Depth', 'Vector Velocity-x', 'Vector Velocity-y'),
                uv_projection_extent: 'typing.Iterable[float] | Bbox2D' = (),
                ):
        from .. import FormatConvention
        p = Path(output_path)
        if not p.parent.exists():
            p.mkdir(parents=True)
        mesh3d = self.mesh3d(
            time,
            time_index,
            data_types,
            uv_projection_extent,
            FormatConvention.OpenGL,
            reverse_winding_order=False
        )
        gltf = GLTF()
        gltf.add_mesh(mesh3d)
        gltf.write(str(output_path))
