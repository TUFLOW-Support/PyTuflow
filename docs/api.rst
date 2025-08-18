API
===

This page gives an overview of the public modules, classes, and functions within PyTUFLOW.


.. toctree::
   :maxdepth: 2
   :caption: API:

.. currentmodule:: pytuflow

.. rubric:: Control File Classes

.. autosummary::
   :toctree: ./api
   :template: custom-class-template.rst
   :nosignatures:

   TCF
   ECF
   TGC
   TBC
   TEF
   QCF
   TOC
   TRFC
   TSCF
   TESF

.. rubric:: Database Classes

.. autosummary::
   :toctree: ./api
   :template: custom-class-template.rst
   :nosignatures:

   BCDatabase
   MatDatabase
   PitInletDatabase
   RainfallDatabase
   SoilDatabase
   CrossSectionDatabase

.. rubric:: Input Classes

.. autosummary::
   :toctree: ./api
   :template: custom-class-template.rst
   :nosignatures:

   SettingInput
   FileInput
   FolderInput
   GisInput
   GridInput
   TinInput
   ControlFileInput
   DatabaseInput
   CommentInput

.. rubric:: Run State Classes

.. autosummary::
   :toctree: ./api
   :template: custom-class-template.rst
   :nosignatures:

   TCFRunState
   TEFRunState
   ControlFileRunState
   DatabaseRunState
   BCDatabaseRunState
   MatDatabaseRunState
   SoilDatabaseRunState
   CrossSectionRunState
   InputRunState
   GisInputRunState

.. rubric:: Output Classes

.. autosummary::
   :toctree: ./api
   :nosignatures:
   :template: custom-class-template.rst

   XMDF
   TPC
   NCGrid
   NCMesh
   CATCHJson
   INFO
   DAT
   GPKG1D
   GPKG2D
   GPKGRL
   FMTS
   FVBCTide
   HydTablesCheck
   BCTablesCheck
   CrossSections

.. rubric:: Utilities

.. autosummary::
   :toctree: ./api
   :nosignatures:

   register_tuflow_binary
   register_tuflow_binary_folder
   tuflow_binaries

.. rubric:: Everything Else

.. autosummary::
   :toctree: ./api
   :nosignatures:
   :template: custom-class-template.rst

   TuflowBinaries
   results.ResultTypeError


