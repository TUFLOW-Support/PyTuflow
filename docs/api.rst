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
   TSCF
   ADCF
   FVC
   FVWQ
   FVSed
   FVPTM
   BlockControl

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
   BlockControlInput
   BCBlockControlInput

.. rubric:: Run State Classes

.. autosummary::
   :toctree: ./api
   :template: custom-class-template.rst
   :nosignatures:

   TCFRunState
   FVCRunState
   TEFRunState
   ControlFileRunState
   DatabaseRunState
   BCDatabaseRunState
   MatDatabaseRunState
   SoilDatabaseRunState
   CrossSectionRunState
   InputRunState
   GisInputRunState
   BlockControlRunState
   BCBlockControlRunState

.. rubric:: Output Classes

.. autosummary::
   :toctree: ./api
   :nosignatures:
   :template: custom-class-template.rst

   XMDF
   TPC
   Grid
   GridMesh
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
   LP2D
   HydTablesCheck
   BCTablesCheck
   CrossSections
   DATCrossSections

.. rubric:: Project

.. autosummary::
   :toctree: ./api
   :nosignatures:
   :template: custom-class-template.rst

   HPCProject

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

   Scope
   TuflowBinaries
   results.ResultTypeError


