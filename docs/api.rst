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
   AttrInput
   FileInput
   GisInput
   GridInput
   TinInput
   ControlFileInput
   DatabaseInput
   CommentInput

.. rubric:: Output Classes

.. autosummary::
   :toctree: ./api
   :nosignatures:
   :template: custom-class-template.rst

   TPC
   INFO
   GPKG1D
   GPKG2D
   GPKGRL
   FMTS
   FVBCTide
   HydTablesCheck
   BCTablesCheck
   CrossSections
