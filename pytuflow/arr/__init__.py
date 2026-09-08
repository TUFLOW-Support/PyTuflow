"""pytuflow.arr

Rewritten ARR-to-TUFLOW module. Fetches rainfall/loss data from the ARR Data Hub API
and converts it into TUFLOW-ready input files (event file, boundary database, rainfall
loss read files, etc).

This replaces the legacy ``ARR_legacy`` (formerly the ``ARR`` QGIS plugin module),
which relied on scraping BOM and ARR Data Hub HTML/text pages. The new module talks to
the upgraded ARR Data Hub JSON API directly and no longer needs to contact BOM at all.
"""

from .exceptions import ArrError, ArrApiError, ArrConfigError
