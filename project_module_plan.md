# Plan: `pytuflow.project` Module

## Overview

A new `pytuflow/project/` subpackage that enables users to **create new TUFLOW HPC projects from scratch** and **insert optional modules into existing projects**. Operates via Python API and CLI (`python -m pytuflow.project`). Designed to be extensible for TUFLOW FV later.

---

## Package Structure

```
pytuflow/
  project/
    __init__.py             # Public API exports
    __main__.py             # CLI entry point
    abc/
      project.py            # BaseProject ABC (shared by HPC + future FV)
      module.py             # BaseModule ABC
    hpc/
      __init__.py
      project.py            # HPCProject class
      modules/
        __init__.py
        estry.py
        quadtree.py
        soils.py
        ad.py
        toc.py
        rf.py
        events.py
    template/
      __init__.py
      manager.py            # TemplateManager — cache init & resolution
      engine.py             # Template rendering (variable substitution + directives)
    config/
      __init__.py
      defaults.py           # Default values + placeholder strings
      settings.py           # User settings (loads from cache defaults JSON files)
```

---

## Templates

### Source Templates

The existing `example_control_file_templates/hpc/` directory becomes the **bundled** (read-only) template source, shipped with the package. Missing templates for optional modules (QCF, ADCF, TOC, RF, TEF) will be added here as blank files for the user to populate.

### Cache Directory

On first use, bundled templates are copied to a user-writable cache inside the existing `~/.tuflow_model_files/` directory:

```
~/.tuflow_model_files/
  project_templates/
    defaults.json          # shared defaults (model_name, gis_format, etc.)
    hpc/
      hpc_defaults.json    # HPC-specific defaults/overrides (cell_size, etc.)
      runs/
        ${model_name}_${iter}.tcf
      model/
        ${model_name}_${iter}.tgc
        ${model_name}_${iter}.tbc
        ${model_name}_mat.csv
        ${model_name}_soils.tsoilf
        ${model_name}_${iter}.ecf
        ${model_name}_${iter}.qcf
        ${model_name}_${iter}.adcf
        ${model_name}_events.tef
        ${model_name}.toc
        ${model_name}_${iter}.rf
      bc_dbase/
        bc_dbase.csv
```

The user can freely edit cached templates and the defaults files. The tool always reads from the cache; if the cache doesn't exist it initialises it first.

### Template Engine

Templates use two levels of processing:

1. **Variable substitution** — `${variable_name}` replaced with values from the project config/defaults. E.g. `${model_name}`, `${iter}`, `${gis_format}`, `${cell_size}`.

2. **Directives** — special comments processed before variable substitution:

   | Directive | Purpose |
   |-----------|---------|
   | `##IF module:estry##` … `##ENDIF##` | Include block only if module is active |
   | `##LOOP map_output_formats##` … `##ENDLOOP##` | Expand per-format (e.g. `${format}`) |
   | `##INSERT_POINT control_files##` | Fallback marker — where to insert commands if a specific directive isn't found; pytuflow TCF/TGC classes are used as a secondary fallback |

   If no directive or insertion point is found, the tool uses the existing pytuflow `TCF`/`TGC` build-state classes to locate a sensible insertion position.

### Template Variables and Defaults

Two-level defaults system (HPC values override shared values where they overlap):

**`defaults.json`** (shared across HPC + future FV):

| Variable | Default |
|----------|---------|
| `model_name` | required (no default) |
| `iter` | `001` |
| `gis_format` | `SHP` |
| `gis_projection_command` | `! Projection == <path/to/projection>  ! TODO` |
| `model_domain_origin` | `0, 0` |
| `model_domain_angle` | `0` |
| `model_domain_size` | `<X, Y>  ! TODO` |

**`hpc/hpc_defaults.json`** (HPC-specific overrides + additions):

| Variable | Default |
|----------|---------|
| `cell_size` | `<cell size>  ! TODO populate with appropriate value` |
| `map_output_formats` | `["XMDF"]` |

Both files live in the cache directory and are fully user-editable.

---

## Modules

### Bare-Bones HPC Project (always created)

| File | Description |
|------|-------------|
| `runs/${model_name}_${iter}.tcf` | Main control file |
| `model/${model_name}_${iter}.tgc` | Geometry control file |
| `model/${model_name}_${iter}.tbc` | Boundary condition control file |
| `bc_dbase/bc_dbase.csv` | BC database |
| `model/${model_name}_mat.csv` | Materials database |

### Optional Modules (opt-in)

| Module name | Files added | TCF change |
|-------------|-------------|------------|
| `estry` | `model/${model_name}_${iter}.ecf` | Uncomments / adds `Estry Control File` command |
| `quadtree` | `model/${model_name}_${iter}.qcf` | Adds `Quadtree Control File` command |
| `soils` | `model/${model_name}_soils.tsoilf` | Uncomments / adds `Read Soils File` command; also adds soil commands to TGC |
| `ad` | `model/${model_name}_${iter}.adcf` | Adds `AD Control File` command |
| `toc` | `model/${model_name}.toc` | Adds `Read Operational Controls` command |
| `rf` | `model/${model_name}_${iter}.rf` | Adds `Read Rainfall File` command |
| `events` | `model/${model_name}_events.tef` | Uncomments event/scenario commands in TCF |

---

## Core Classes

### `HPCProject`

```python
project = HPCProject(
    name="mymodel",
    output_dir="/path/to/project",
    modules=["estry", "soils"],          # optional modules
    gis_format="GPKG",
    map_output_formats=["XMDF", "TIF"],  # used for loop expansion
    cell_size=5.0,
    # ... other overrides
)
project.create()   # write all files to disk
```

### `HPCProject.insert_module(module_name, tcf_path)`

Inserts an optional module into an **existing** project. Reads the existing TCF using `pytuflow.TCF`, finds the right insertion point, adds the control file reference and creates the new control file from template.

### `BaseProject` (ABC)

Defines the interface: `create()`, `insert_module()`, `validate()`. Both HPC and (future) FV projects extend this.

### `BaseModule` (ABC)

Each module class encapsulates:
- which template files it needs
- which variables it provides
- how to modify the parent TCF (command to add, where to add it)
- any secondary file modifications (e.g. soils module also modifies TGC)

---

## CLI Design

```
python -m pytuflow.project create \
    --name mymodel \
    --output-dir /path/to/project \
    --modules estry soils \
    --gis-format GPKG \
    --map-output-formats XMDF TIF \
    --cell-size 5.0

python -m pytuflow.project insert \
    --tcf /path/to/runs/mymodel_001.tcf \
    --module quadtree

python -m pytuflow.project init-templates   # copy bundled templates to ~/.tuflow_model_files/project_templates/ (reset)
python -m pytuflow.project list-modules     # list available modules
```

---

## File Layout on Disk

```
<output_dir>/
  runs/
    mymodel_001.tcf
  model/
    mymodel_001.tgc
    mymodel_001.tbc
    mymodel_mat.csv
    [mymodel_001.ecf]        # if estry
    [mymodel_soils.tsoilf]   # if soils
    [mymodel_001.qcf]        # if quadtree
    [mymodel_001.adcf]       # if ad
    [mymodel.toc]            # if toc
    [mymodel_001.rf]         # if rf
    [mymodel_events.tef]     # if events
  bc_dbase/
    bc_dbase.csv
  results/    (empty, created)
  check/      (empty, created)
  log/        (empty, created)
```

---

## Key Design Principles

- **Template-first**: the output is entirely driven by templates; code only substitutes variables and applies directives.
- **Graceful degradation**: if a directive is not found in a template, `pytuflow.TCF` / `.TGC` build-state classes are used to find a sensible insertion location.
- **User-modifiable defaults**: `~/.tuflow_model_files/project_templates/defaults.json` and `hpc_defaults.json` are the single place to change all defaults.
- **TODO placeholders**: when no default value is appropriate (e.g. cell size), the placeholder string is used verbatim so the user knows what to fill in before running.
- **Extensible**: `BaseProject` and `BaseModule` abstractions make it straightforward to add `FVProject` later.

---

## Phase Breakdown

| Phase | Work |
|-------|------|
| 1 | Package skeleton, ABC classes, TemplateManager (cache init), template engine (variable sub + directives) |
| 2 | Core bare-bones `HPCProject.create()` — TCF, TGC, TBC, bc_dbase, mat |
| 3 | Optional module classes (estry, quadtree, soils, ad, toc, rf, events) + new blank template files |
| 4 | `HPCProject.insert_module()` — modifying existing projects |
| 5 | CLI (`__main__.py`) |
| 6 | Tests + wiring into `pytuflow.__init__` |
