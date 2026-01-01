import contextlib
import typing
from pathlib import Path

try:
    from alembic.AbcCoreAbstract import TimeSampling
    from alembic.Abc import OArchive
    from alembic.AbcGeom import (OPolyMesh, OPolyMeshSchemaSample, GeometryScope, OC3fGeomParamSample,
                                 OC3fGeomParam, OV2fGeomParamSample)
    from imath import V3f, V2f, V3fArray, V2fArray, IntArray, Color3f, C3fArray, UnsignedIntArray
except ImportError:
    from ...stubs.alembic.AbcCoreAbstract import TimeSampling
    from ...stubs.alembic.Abc import OArchive
    from ...stubs.alembic.AbcGeom import (OPolyMesh, OPolyMeshSchemaSample, GeometryScope, OC3fGeomParamSample,
                                          OC3fGeomParam, OV2fGeomParamSample)
    from ...stubs.imath import V3f, V2f, V3fArray, V2fArray, IntArray, Color3f, C3fArray, UnsignedIntArray

if typing.TYPE_CHECKING:
    from .. import SceneMesh


class AlembicMesh:

    def __init__(self, parent: OArchive, name: str, time_sampling: float):
        self.mesh_obj = OPolyMesh(parent.getTop(), name)
        self.mesh = self.mesh_obj.getSchema()
        ts = TimeSampling(time_sampling, 0)
        self.mesh.setTimeSampling(ts)
        self.cd = OC3fGeomParam(self.mesh.getArbGeomParams(), "Cd", False, GeometryScope.kVertexScope, 1)
        self.cd.setTimeSampling(ts)
        self._arrays_initialised = False
        self._inds = None
        self._inds_idx = None  # used to index uvs - uses different data type
        self._face_counts = None
        self._pos = None
        self._uv = None
        self._cd = None

    def __repr__(self) -> str:
        return f'<AlembicMesh: {self.mesh_obj.getName()}'

    def add_mesh_sample(self, mesh: 'SceneMesh'):
        if not self._arrays_initialised:
            self._init_arrays(mesh)

        for i in range(mesh.inds.count()):
            self._inds[i] = int(mesh.inds.data[i])
            self._inds_idx[i] = int(mesh.inds.data[i])
        for i in range(mesh.face_counts.count()):
            self._face_counts[i] = int(mesh.face_counts.data[i])
        for i in range(0, mesh.pos.size(), mesh.pos.n):
            j = i // mesh.pos.n
            self._pos[j] = V3f(*mesh.pos.data[i:i+mesh.pos.n].tolist())
        for i in range(0, mesh.uv.size(), mesh.uv.n):
            j = i // mesh.uv.n
            self._uv[j] = V2f(*mesh.uv.data[i:i+mesh.uv.n].tolist())
        for i in range(0, mesh.cd.size(), mesh.cd.n):
            j = i // mesh.cd.n
            self._cd[j] = Color3f(*mesh.cd.data[i:i+mesh.cd.n].tolist())

        # create uv sample
        uv_sample = OV2fGeomParamSample(self._uv, self._inds_idx, GeometryScope.kFacevaryingScope)

        # set mesh sample
        sample = OPolyMeshSchemaSample(self._pos, self._inds, self._face_counts, uv_sample)
        self.mesh.set(sample)

        # set colour param
        col_sample = OC3fGeomParamSample(self._cd, GeometryScope.kVertexScope)
        self.cd.set(col_sample)

    def _init_arrays(self, mesh: 'SceneMesh'):
        self._inds = IntArray(mesh.inds.count())
        self._inds_idx = UnsignedIntArray(mesh.inds.count())
        self._face_counts = IntArray(mesh.face_counts.count())
        self._pos = V3fArray(mesh.pos.count())
        self._uv = V2fArray(mesh.uv.count())
        self._cd = C3fArray(mesh.cd.count())
        self._arrays_initialised = True


class Alembic:

    def __init__(self):
        self.oarch = None
        self.fpath = None
        self.mesh_objs = {}

    def __repr__(self) -> str:
        if self.oarch is not None:
            return f'<Alembic: {self.fpath.stem}>'
        return '<Alembic: >'

    @contextlib.contextmanager
    def open(self, output_path: Path | str) -> typing.Generator['Alembic', None, None]:
        try:
            self.fpath = Path(output_path)
            self.oarch = OArchive(str(output_path))
            yield self
        finally:
            self.oarch = None

    def add_mesh(self, name: str, time_sampling: float) -> AlembicMesh:
        self.mesh_objs[name] = AlembicMesh(self.oarch, name, time_sampling)
        return self.mesh_objs[name]
