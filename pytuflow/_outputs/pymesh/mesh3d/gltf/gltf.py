import typing

import numpy as np
try:
    import pygltflib
except ImportError:
    from ...stubs import pygltflib

if typing.TYPE_CHECKING:
    from .. import SceneMesh



class GLTF:

    def __init__(self):
        self.meshes: list['SceneMesh'] = []
        if '.stubs' in pygltflib.__name__:
            raise ImportError('pygltflib is required to use GLTF output. Please install it via "pip install pygltflib".')

    def add_mesh(self, mesh: 'SceneMesh'):
        pos = 0
        if self.meshes:
            prev = self.meshes[-1]
            pos = prev.start_pos + prev.blob_size()
        mesh.start_pos = pos
        mesh.inds.start_pos = pos
        mesh.pos.start_pos = mesh.inds.start_pos + mesh.inds.blob_size()
        mesh.cd.start_pos = mesh.pos.start_pos + mesh.pos.blob_size()
        mesh.uv.start_pos = mesh.cd.start_pos + mesh.cd.blob_size()

        self.meshes.append(mesh)

    def write(self, output_path: str):
        mesh_count = len(self.meshes)
        gltf = pygltflib.GLTF2(
            scene=0,
            scenes=[pygltflib.Scene(nodes=[i for i in range(mesh_count)])],
            nodes=[pygltflib.Node(mesh=i) for i in range(mesh_count)],
            meshes=[
                pygltflib.Mesh(
                    primitives=[
                        pygltflib.Primitive(
                            attributes=pygltflib.Attributes(POSITION=1, COLOR_0=2, TEXCOORD_0=3), indices=0
                        )
                    ]
                ) for _ in self.meshes
            ],
            accessors=np.array([
                [
                    pygltflib.Accessor(
                        bufferView=i * 4,
                        componentType=pygltflib.UNSIGNED_INT,
                        count=mesh.inds.count(),
                        type=pygltflib.SCALAR,
                        max=[int(mesh.inds.max())],
                        min=[int(mesh.inds.min())],
                    ),
                    pygltflib.Accessor(
                        bufferView=i * 4 + 1,
                        componentType=pygltflib.FLOAT,
                        count=mesh.pos.count(),
                        type=pygltflib.VEC3,
                        max=mesh.pos.max(),
                        min=mesh.pos.min(),
                    ),
                    pygltflib.Accessor(
                        bufferView=i * 4 + 2,
                        componentType=pygltflib.FLOAT,
                        count=mesh.cd.count(),
                        type=pygltflib.VEC3,
                        max=mesh.cd.max(),
                        min=mesh.cd.min(),
                    ),
                    pygltflib.Accessor(
                        bufferView=i * 4 + 3,
                        componentType=pygltflib.FLOAT,
                        count=mesh.uv.count(),
                        type=pygltflib.VEC2,
                        max=mesh.uv.max(),
                        min=mesh.uv.min(),
                    ),
                ] for i, mesh in enumerate(self.meshes)
            ]).flatten().tolist(),
            bufferViews=np.array([
                [
                    pygltflib.BufferView(
                        buffer=0,
                        byteOffset=mesh.inds.start_pos,
                        byteLength=mesh.inds.blob_size(),
                        target=pygltflib.ELEMENT_ARRAY_BUFFER,
                    ),
                    pygltflib.BufferView(
                        buffer=0,
                        byteOffset=mesh.pos.start_pos,
                        byteLength=mesh.pos.blob_size(),
                        target=pygltflib.ARRAY_BUFFER,
                    ),
                    pygltflib.BufferView(
                        buffer=0,
                        byteOffset=mesh.cd.start_pos,
                        byteLength=mesh.cd.blob_size(),
                        target=pygltflib.ARRAY_BUFFER,
                    ),
                    pygltflib.BufferView(
                        buffer=0,
                        byteOffset=mesh.uv.start_pos,
                        byteLength=mesh.uv.blob_size(),
                        target=pygltflib.ARRAY_BUFFER,
                    ),
                ] for mesh in self.meshes
            ]).flatten().tolist(),
            buffers=[
                pygltflib.Buffer(
                    byteLength=sum([mesh.blob_size() for mesh in self.meshes])
                )
            ],
        )
        gltf.set_binary_blob(b''.join([mesh.blob() for mesh in self.meshes]))
        gltf.save(output_path)
