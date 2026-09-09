# pytuflow.arr

Converts [Australian Rainfall and Runoff (ARR)](http://arr.ga.gov.au/home) rainfall
and loss data from the [ARR Data Hub](https://data.arr-software.org/about) into
TUFLOW model input files (`Event_File.tef`, `bc_dbase.csv`, `rf_inflow/*.csv`,
`soils.tsoilf` / `*.trd`).

This is a clean rewrite of the legacy `ARR_to_TUFLOW` QGIS plugin script, built against
the upgraded ARR Data Hub API (which now serves IFD depths, climate-change-adjusted
depths, and probability-neutral losses directly, removing the need to scrape BOM's
website or calculate climate-change adjustments locally). It works both as a standalone
command line tool and inside QGIS (see [QGIS usage](#qgis-usage) below).

## Usage

```bash
pytuflow-arr config1.json [config2.json ...]
```

Each JSON config file describes a single site/catchment. When multiple config files are
given, they are processed in order and their TUFLOW outputs are **appended** into a
single set of output files (one `Event_File.tef`, `bc_dbase.csv`, etc, covering all
sites) rather than overwritten by each subsequent config - equivalent to the legacy
script's multi-catchment (`catch_no`) batching, but driven by multiple config files
instead of a single config with batch arguments.

Add `-v`/`--verbose` for debug-level logging.

## QGIS usage

The module can also be imported and driven directly from Python inside QGIS (e.g. from
the Python console, or a custom plugin action):

```python
from tuflow.pt.pytuflow.arr.api_client import ArrApiClient
from tuflow.pt.pytuflow.arr.config import ArrConfig
from tuflow.pt.pytuflow.arr.engine import ArrEngine
from tuflow.pt.pytuflow.arr.writers import write_outputs

config = ArrConfig.from_file('config1.json')
client = ArrApiClient()
response = client.fetch(config)
results = ArrEngine(config, response).run()
write_outputs(config, results)
```

Inside QGIS, network requests automatically use `QgsNetworkAccessManager` instead of the
`requests` library, so proxy settings configured in QGIS (Settings > Options > Network)
are inherited automatically - **no manual proxy configuration is needed or supported**.
This is handled transparently by [`downloader.py`](downloader.py), which detects whether
the `qgis` package is importable and picks the appropriate downloader implementation; no
config option controls this.

## JSON config file

Every section below is optional unless stated otherwise - omitted sections use the
documented defaults. Unknown keys (at any level) raise a validation error rather than
being silently ignored, to catch typos early.

```json
{
  "site": {
    "name": "Site1",
    "latitude": -33.9347,
    "longitude": 150.8372,
    "catchment_area": 11.4
  },
  "ifd": {
    "source": "bom",
    "year": 1990
  },
  "events": {
    "aep": ["50%", "20%", "10%", "5%", "2%", "1%"],
    "duration": [60, 120, 180, 360, 720, 1440],
    "output_notation": "ari"
  },
  "temporal_patterns": {
    "point_tp_csv": null,
    "areal_tp_csv": null,
    "additional_tp": [],
    "all_point_tp": false,
    "add_areal_tp": 0
  },
  "climate_change": {
    "enabled": false,
    "scenarios": [
      {"baseline_year": 2090, "ssp": "SSP3"}
    ]
  },
  "preburst": {
    "percentile": "50%",
    "pattern_method": "recommended",
    "pattern_duration": null,
    "pattern_tp": null,
    "duration_proportional": false
  },
  "losses": {
    "method": "datahub",
    "mar": null,
    "static_loss": null,
    "tuflow_loss_method": "infiltration",
    "user_initial_loss": null,
    "user_continuing_loss": null,
    "urban_initial_loss": null,
    "urban_continuing_loss": null,
    "use_global_continuing_loss": false,
    "probability_neutral": true
  },
  "arf": {
    "ignore_limits_for_frequent": false,
    "min_arf": 0.2
  },
  "complete_storm": false,
  "output": {
    "path": "C:\\path\\to\\output",
    "format": "csv"
  }
}
```

### `site` (required)

| Key | Type | Description |
| --- | --- | --- |
| `name` | string | Site/catchment identifier - used as a prefix for output file names (e.g. `<name>_RF_...`) and as the TUFLOW `IL_<name>`/`CL_<name>` loss variable suffix. **Required.** |
| `latitude` / `longitude` | number | Site (catchment centroid) coordinates, decimal degrees. **Required.** |
| `catchment_area` | number | Catchment area in km². Used for ARF calculation and to select the areal temporal pattern area bucket. |

### `ifd`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `source` | string | `"bom"` | IFD data source. Only `"bom"` is currently supported (future: `"limb"`, `"qra"`). |
| `year` | int | `1990` | IFD baseline year: `1990` (historical) or `2030` (current baseline). Climate-change-adjusted depths for other baseline years/SSPs are configured separately, under `climate_change`. |

### `events` (required)

| Key | Type | Description |
| --- | --- | --- |
| `aep` | list[string] | AEP/ARI/EY magnitude labels to assemble events for, e.g. `"1%"`, `"1 in 200"`, `"0.5EY"`. **Required.** (`"all"` is accepted by the schema but not yet implemented.) |
| `duration` | list[number] | Storm durations in minutes, e.g. `60`, `1440`. **Required.** (`"all"` is accepted by the schema but not yet implemented.) |
| `output_notation` | string | `"ari"` (default) or `"aep"` - controls the `~ARI~`/`~AEP~` TUFLOW event variable used in `Event_File.tef` and `bc_dbase.csv`; does not change which events are calculated. |

### `temporal_patterns`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `point_tp_csv` | string \| null | `null` | Reserved for supplying a local point temporal pattern increments CSV instead of downloading from the Data Hub. Not yet used by the engine (always downloads from the Data Hub's supplied URL). |
| `areal_tp_csv` | string \| null | `null` | As above, for areal temporal patterns. Not yet used. |
| `additional_tp` | list | `[]` | Reserved for supplying additional/custom temporal patterns. Not yet used. |
| `all_point_tp` | bool | `false` | Reserved: matches legacy's "all point TP" option (include frequent/intermediate/rare point patterns for every duration, not just the duration's own AEP band). Not yet implemented in the engine. |
| `add_areal_tp` | int | `0` | Reserved: number of additional areal temporal pattern realisations to include beyond the default set. Not yet implemented in the engine. |

The temporal pattern actually used for each AEP/duration is selected automatically:
areal patterns are preferred over point patterns wherever the Data Hub provides an
areal pattern for the catchment's area bucket and the duration is long enough; see
[`temporal_patterns.py`](temporal_patterns.py) for full selection rules.

### `climate_change`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | bool | `false` | If `true`, an additional event is assembled for each scenario in `scenarios`, alongside the base (no climate-change) event. |
| `scenarios` | list[object] | `[]` | List of `{"baseline_year": ..., "ssp": ...}` objects. Required (non-empty) if `enabled` is `true`. |

Each scenario object:

| Key | Type | Allowed values |
| --- | --- | --- |
| `baseline_year` | int | `2030`, `2050`, `2090` |
| `ssp` | string | `"SSP1"`, `"SSP2"`, `"SSP3"`, `"SSP5"` |

Climate-change-adjusted IFD depths are requested directly from the Data Hub's
`CCAdjIFDDatasets` layer for the given baseline year/SSP. Climate-change loss
adjustment factors (initial and continuing loss) are requested from the Data Hub's
`ClimateChange` layer and applied by multiplying the base (no climate-change) storm
initial/continuing loss values - no manual climate-change factor calculation is
performed locally (unlike the legacy script's rate-of-change table lookups).

Each climate change scenario's rainfall is written into the **same** `rf_inflow`
CSV/ts1 file as the base (no climate-change) event for that AEP/duration, rather than a
separate file. The base event's temporal pattern columns are named `TP01`, `TP02`, etc;
each climate change scenario's columns are suffixed with `_<baseline_year>_<ssp>`, e.g.
`TP01_2090_SSP2`, `TP02_2090_SSP2`. `bc_dbase.csv` still references the plain `~TP~`
column (used to run the standard, non-climate-change events); a companion
`bc_dbase_CC.csv` is additionally written (only when climate change is enabled),
referencing `~TP~_~CC~` so TUFLOW's `~CC~` event variable (defined in
`Event_File.tef`) selects the matching suffixed column for each scenario - both files
point at the same merged `rf_inflow` file, only the column reference differs.

### `preburst`

Only used for **complete storm** events - see [Complete storm assembly](#complete-storm-assembly) below.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `percentile` | string | `"50%"` | Preburst depth/ratio percentile to use for the `"constant"`/`"pattern"` methods: one of `"10%"`, `"25%"`, `"50%"`, `"75%"`, `"90%"`. Not used by the `"recommended"` method (which supplies its own preburst depth). |
| `pattern_method` | string \| null | `"recommended"` | Preburst pattern method: `"recommended"`, `"constant"`, or `"pattern"` (see below). |
| `pattern_duration` | number \| null | `null` | Required for `"constant"`/`"pattern"` methods. Preburst duration in hours (or a proportion of the storm duration, if `duration_proportional` is `true`). |
| `pattern_tp` | string \| null | `null` | Required for the `"pattern"` method: which existing point temporal pattern to shape the preburst rainfall with, e.g. `"TP03"`. |
| `duration_proportional` | bool | `false` | If `true`, `pattern_duration` is treated as a proportion of the storm duration rather than an absolute number of hours. |

### `losses`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `method` | string | `"datahub"` | How to obtain the burst initial loss: `"datahub"` (use the Data Hub's probability-neutral burst loss table directly, no extrapolation - the default), `"interpolate"` (extrapolate short durations below the Data Hub's minimum via linear interpolation from an assumed 0 mm at 0 min), `"rahman"` (Rahman et al. short-duration loss formula; requires `mar`), `"hill"` (Hill et al. formula), or `"static"` (a fixed loss value; requires `static_loss`). |
| `mar` | number \| null | `null` | Mean Annual Rainfall (mm), required when `method == "rahman"`. |
| `static_loss` | number \| null | `null` | Fixed initial loss value (mm), required when `method == "static"`. |
| `tuflow_loss_method` | string | `"infiltration"` | `"infiltration"` writes a `soils.tsoilf` `ILCL` entry plus a companion `.trd` read file; `"excess"` writes only the `.trd` read file (rainfall excess method, no soils file). |
| `user_initial_loss` | number \| null | `null` | Overrides the storm initial loss with a fixed user-supplied value (scales/replaces the Data Hub value depending on context). |
| `user_continuing_loss` | number \| null | `null` | Reserved: overrides the storm continuing loss. Not yet implemented in the engine. |
| `urban_initial_loss` / `urban_continuing_loss` | number \| null | `null` | Reserved for urban catchment loss overrides. Not yet implemented in the engine. |
| `use_global_continuing_loss` | bool | `false` | If `true`, the continuing loss `Set Variable` line is omitted from the per-event `.trd` block (assumes a single global continuing loss value is set elsewhere in the TUFLOW model). |
| `probability_neutral` | bool | `true` | Reserved: matches legacy's probability-neutral-losses toggle. Not yet implemented as a separate code path (the Data Hub's burst loss tables are probability-neutral by construction). |

### `arf`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `ignore_limits_for_frequent` | bool | `false` | If `true`, applies the Areal Reduction Factor equations even to frequent events outside ARR's recommended range, rather than capping/warning. |
| `min_arf` | number | `0.2` | Minimum allowed ARF value (0-1); calculated ARF values are clamped to this floor. |

### `complete_storm`

| Type | Default | Description |
| --- | --- | --- |
| bool | `false` | If `true`, **every** requested event is assembled as a complete storm (preburst period prepended ahead of the design burst), using the `preburst` section's settings. |

Regardless of this setting, complete storm assembly is also triggered **automatically,
per AEP/duration cell**, whenever the Data Hub's burst initial loss table (`BurstLossesNew`/`BurstIL`)
returns its `"Use PB TP"` placeholder for that cell - see [Complete storm assembly](#complete-storm-assembly).

### `output` (required)

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `path` | string | - | Output folder for all TUFLOW files. **Required.** Created if it doesn't exist. |
| `format` | string | `"csv"` | Rainfall hyetograph file format: `"csv"` (time in hours, with an `Event ID` header row) or `"ts1"` (TUFLOW's native ts1 format, time in minutes). |
| `verbose` | bool | `false` | If `true`, also writes intermediate "working data" files (areal design IFD table, ARF table, burst initial loss table, and raw point/areal temporal pattern increment CSVs) to a `working_data` subfolder - see [Working data](#working-data) below. |

## Working data

Alongside the standard TUFLOW output files, a `working_data` subfolder of `output.path`
is used to save data useful for reviewing/QA'ing what the tool requested and calculated:

* `<site>_ARR_response.json` - the raw JSON response from the ARR Data Hub, exactly as
  received. **Always saved**, regardless of `output.verbose`, so a run can always be
  fully reproduced/inspected later without needing to re-query the Data Hub.

The following are only saved when `output.verbose` is `true`, since they are purely for
debugging/QA and are otherwise redundant with the always-written `rf_inflow`/loss
control files:

* `<site>_IFD_after_ARF[_<cc_scenario>].csv` - the areal (post-ARF) design rainfall
  depth (mm) for every requested duration x AEP, one file per climate change scenario
  (if enabled).
* `<site>_ARF[_<cc_scenario>].csv` - the Areal Reduction Factor applied for every
  requested duration x AEP.
* `<site>_burst_initial_loss[_<cc_scenario>].csv` - the probability-neutral burst
  initial loss (mm) table used (or extrapolated, if `losses.method` is not
  `"datahub"`), for every duration x AEP, one file per climate change scenario (if
  enabled) - climate change scenario files have the Data Hub's climate-change initial
  loss adjustment factor applied.
* `<site>_PointTP_Increments.csv` / `<site>_ArealTP_Increments.csv` - the raw temporal
  pattern increment CSVs downloaded from the Data Hub (before selection/filtering to the
  specific patterns used for each event).

## Complete storm assembly

A "complete storm" prepends a preburst rainfall period ahead of the ARR design
burst, so the full **storm** initial loss can be used (rather than a reduced **burst**
initial loss that already accounts for the preburst rainfall having "used up" some of
the loss). See [`complete_storm.py`](complete_storm.py) for the full implementation.

Three preburst pattern methods are available (`preburst.pattern_method`):

- **`"recommended"`** (default) - uses the Data Hub's `RecPreburstTP` layer, which
  supplies a specific historical event's preburst duration/depth/increments directly for
  the requested AEP/duration. This is the only method available for AEP/duration cells
  where the burst initial loss table returns the `"Use PB TP"` placeholder, since those
  cells have no fixed burst initial loss value to derive a preburst depth from another
  way. Only available in NSW (where the Data Hub provides this layer).
- **`"constant"`** - a single preburst block of a fixed duration (`preburst.pattern_duration`)
  at a constant rate, matching the legacy "Constant Rate" method. The preburst depth is
  derived from the `Preburst<percentile>` ratio table multiplied by the point design
  burst depth.
- **`"pattern"`** - shapes the preburst rainfall using a specific existing point temporal
  pattern (`preburst.pattern_tp`, e.g. `"TP03"`) at the closest available duration to the
  computed preburst duration. As with `"constant"`, the preburst depth comes from the
  `Preburst<percentile>` ratio table.

**Automatic per-cell triggering:** independently of `complete_storm`, whenever the
requested AEP/duration's burst initial loss is the Data Hub's `"Use PB TP"` placeholder
(meaning no fixed burst initial loss value exists for that cell), `pytuflow.arr`
automatically assembles that specific event as a complete storm using the `"recommended"`
preburst method, regardless of `preburst.pattern_method`. A log message records when
this happens. This means most configs never need to set `complete_storm` explicitly -
it is primarily useful for forcing complete storm assembly (with a specific
`pattern_method`) across every event for consistency.

### How to configure it

`complete_storm` and `preburst` are two separate top-level sections that work together:

- `complete_storm` (a plain `true`/`false`) decides **which events** are assembled as
  complete storms: `true` = every requested event; `false` (default) = only those
  specific AEP/duration cells that are forced to (the `"Use PB TP"` placeholder cells).
- `preburst` decides **how** the preburst period is built for those events (which
  method, and that method's parameters). It has no effect on its own - it is only
  consulted once an event is being assembled as a complete storm.

To turn on complete storm assembly for **every** event, using the recommended Data Hub
preburst pattern (the simplest option, NSW only):

```json
{
  "complete_storm": true,
  "preburst": {
    "pattern_method": "recommended"
  }
}
```

Since `"recommended"` is already the default `pattern_method`, this is equivalent to
just setting `"complete_storm": true` with no `preburst` section at all.

To force complete storm assembly for every event using a **constant-rate** preburst
block (e.g. a 2-hour constant preburst ahead of the design burst, using the median (50%)
preburst depth):

```json
{
  "complete_storm": true,
  "preburst": {
    "percentile": "50%",
    "pattern_method": "constant",
    "pattern_duration": 2.0,
    "duration_proportional": false
  }
}
```

To instead make the preburst duration proportional to the storm duration (e.g. 25% of
the storm duration) rather than a fixed number of hours:

```json
{
  "complete_storm": true,
  "preburst": {
    "percentile": "50%",
    "pattern_method": "constant",
    "pattern_duration": 0.25,
    "duration_proportional": true
  }
}
```

To shape the preburst rainfall using a specific existing point temporal pattern (e.g.
`TP03`) rather than a constant rate:

```json
{
  "complete_storm": true,
  "preburst": {
    "percentile": "50%",
    "pattern_method": "pattern",
    "pattern_duration": 1.0,
    "pattern_tp": "TP03",
    "duration_proportional": false
  }
}
```

If you leave `"complete_storm": false` (or omit it entirely - it defaults to `false`),
you **do not** need a `preburst` section at all for typical use: any AEP/duration cell
that requires complete storm assembly (the `"Use PB TP"` placeholder cells) will be
handled automatically using the `"recommended"` method. Only add a `preburst` section
in this case if you specifically want those auto-triggered cells to use the
`"constant"`/`"pattern"` method instead of `"recommended"`.

## Not yet implemented

The following config options are accepted (validated, parsed) but not yet acted on by
the engine - they are reserved for future work and are documented above per-key:

- `events.aep` / `events.duration` == `"all"`
- `temporal_patterns.point_tp_csv` / `areal_tp_csv` / `additional_tp` / `all_point_tp` / `add_areal_tp`
- `losses.user_continuing_loss`, `losses.urban_initial_loss` / `urban_continuing_loss`, `losses.probability_neutral`
- The `"pattern"` preburst method's legacy `design_burst` option (per-design-TP preburst shaping)

## See also

- `arr_config_schema.md` in the repository root - the original schema design document,
  including rationale for changes vs the legacy script's CLI arguments.
- `ARR_legacy/` - the original `ARR_to_TUFLOW` QGIS plugin script this module replaces
  (kept, untouched, for reference).
- `tests/arr/` - the automated test suite (uses cached real Data Hub API responses by
  default; a live smoke test can be run with `ARR_LIVE_TESTS=1`).
