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
    "method": "recommended",
    "extrapolation_method": "none",
    "mar": null,
    "static_loss": null,
    "tuflow_loss_method": "infiltration",
    "user_initial_loss": null,
    "user_continuing_loss": null,
    "urban_initial_loss": null,
    "urban_continuing_loss": null
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
| `additional_tp` | list[string] | `[]` | Names of other ARR temporal pattern regions (see list below) to fetch and merge in alongside the catchment's own point temporal patterns, for every point-sourced duration/AEP. Each region's own `TP01`-`TP10` numbering is preserved; output columns are only suffixed with the region name when more than one region is present for that event (e.g. `TP01_WetTropics`). The catchment's own (native) region patterns are always output first, ahead of any additional regions. Ignored for areal-sourced durations. |
| `all_point_tp` | bool | `false` | When `true`, include all three AEP point-pattern bands (frequent/intermediate/rare) for every point-sourced duration, not just the duration's own band. Output columns are only suffixed with the band name (e.g. `TP01_frequent`) when more than one band is present. Ignored for areal-sourced durations. |
| `add_areal_tp` | int | `0` | Number of additional areal temporal pattern catchment-area buckets (beyond the catchment's own bucket) to include for every areal-sourced duration, e.g. `1` adds the next-larger area bucket's 10 patterns, `2` adds the next two, etc. Additional sets are tagged `_add1`, `_add2`, ... in output column labels. If fewer buckets remain than requested, a warning is logged and the available buckets are used. Ignored for point-sourced durations. |

The temporal pattern actually used for each AEP/duration is selected automatically:
areal patterns are preferred over point patterns wherever the Data Hub provides an
areal pattern for the catchment's area bucket and the duration is long enough; see
[`temporal_patterns.py`](temporal_patterns.py) for full selection rules.

Valid `additional_tp` region names (case-insensitive): `Rangelands West`, `Wet
Tropics`, `Rangelands`, `Central Slopes`, `Monsoonal North`, `Murray Basin`, `East
Coast North`, `East Coast South`, `Southern Slopes Mainland`, `Southern Slopes
Tasmania`, `East Flatlands`, `West Flatlands`. Each is fetched from the Data Hub
using a representative lat/lon coordinate for that region.

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
`ClimateChange` layer; continuing loss is always applied by multiplying the base (no
climate-change) storm continuing loss by the factor, while initial loss is applied
according to `losses.climate_change_method` (`"burst"`, the default, multiplies the
burst initial loss directly; `"storm"` re-derives it from the climate-change-scaled
storm initial loss minus a climate-change preburst depth - see the `losses` section
below) - no manual climate-change factor calculation is performed locally (unlike the
legacy script's rate-of-change table lookups).

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
| `percentile` | string | `"50%"` | Preburst depth/ratio percentile to use for the `"constant"`/`"temporal_pattern"` methods: one of `"10%"`, `"25%"`, `"50%"`, `"75%"`, `"90%"`, or `"recommended"` (the Data Hub's preferred/recommended preburst ratio, from the `RecPreburst` layer - not necessarily the same value as the exact `"50%"` percentile). Not used by the `pattern_method == "recommended"` method (which supplies its own preburst depth from `RecPreburstTP`). |
| `pattern_method` | string \| null | `"recommended"` | Preburst pattern method: `"recommended"`, `"constant"`, or `"temporal_pattern"` (see below). |
| `pattern_duration` | number \| null | `null` | Required for `"constant"`/`"temporal_pattern"` methods. Preburst duration in hours (or a proportion of the storm duration, if `duration_proportional` is `true`). |
| `pattern_tp` | string \| null | `null` | Required for the `"temporal_pattern"` method: which existing point temporal pattern to shape the preburst rainfall with, e.g. `"TP03"` - or `"design_burst"`, which matches each design burst temporal pattern to a preburst pattern of the same `tp_number` (e.g. the `"TP01"` design burst gets a `"TP01"` preburst), rather than a single fixed pattern for every column. |
| `duration_proportional` | bool | `false` | If `true`, `pattern_duration` is treated as a proportion of the storm duration rather than an absolute number of hours. |

### `losses`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `method` | string | `"recommended"` | Which Data Hub burst initial loss table to use: `"recommended"` (the newer `BurstLossesNew` table), or `"probability_neutral"` (the legacy NSW-only probability-neutral `BurstIL` table - raises an error if that layer isn't available for the queried location). |
| `extrapolation_method` | string | `"none"` | How to extrapolate the burst initial loss for requested durations shorter than the Data Hub's shortest provided duration (independent of, and can be combined with, `method` above): `"none"` (do not extrapolate - raises an error if a shorter duration is requested), `"interpolate"` (linear interpolation of the burst initial loss from an assumed 0 mm at 0 min), `"log_interpolate"` (as `"interpolate"`, but on a `log10(duration)` axis), `"interpolate_preburst"` (linear interpolation of the *implied preburst depth* - `storm initial loss - burst initial loss` - from an assumed 0 mm at 0 min, then converted back to a burst initial loss; matches the legacy "Constant Rate"-style preburst-depth extrapolation), `"log_interpolate_preburst"` (as `"interpolate_preburst"`, but on a `log10(duration)` axis), `"rahman"` (Rahman et al. short-duration loss formula; requires `mar`), `"hill"` (Hill et al. formula; requires `mar`), `"static"` (a fixed loss value; requires `static_loss`), or `"constant"` (holds the Data Hub's shortest known duration's loss value constant for all shorter durations - matches the legacy option to continue using the 60 min loss for smaller durations, adapted to the Data Hub's current shortest duration, typically 30 min). Note: any requested duration that instead falls *within* the Data Hub's provided duration range but isn't itself one of the table's rows (e.g. 270 min, between the table's 180 and 360 min rows) is always linearly gap-filled regardless of this setting, matching the legacy script's behaviour. |
| `mar` | number \| null | `null` | Mean Annual Rainfall (mm), required when `extrapolation_method` is `"hill"`. |
| `static_loss` | number \| null | `null` | Fixed initial loss value (mm), required when `extrapolation_method == "static"`. |
| `tuflow_loss_method` | string | `"infiltration"` | `"infiltration"` writes a `soils.tsoilf` `ILCL` entry plus a companion `.trd` read file; `"excess"` writes only the `.trd` read file (rainfall excess method, no soils file). |
| `user_initial_loss` | number \| null | `null` | Overrides the storm initial loss (used directly for complete storm events, and as the reference value climate-change `"storm"` scaling is anchored to) with a fixed user-supplied value. The burst initial loss table is proportionally scaled per-AEP so its (per-AEP) storm initial loss matches this value, preserving the Data Hub's relative duration/AEP reduction shape - matches the legacy script's `applyUserInitialLoss`. |
| `user_continuing_loss` | number \| null | `null` | Overrides the storm continuing loss with a fixed user-supplied value (used directly for every AEP, in place of the Data Hub's `NewStormLosses`/`StormLosses` value) - matches the legacy script's `applyUserContinuingLoss`. |
| `urban_initial_loss` / `urban_continuing_loss` | number \| null | `null` | Fixed impervious/urban area initial and continuing loss values (mm, mm/h). Must be set together (both or neither), and require `tuflow_loss_method == "infiltration"`. When set, an additional fixed-value `ILCL` entry (soil ID 1, labelled "Impervious/Urban Area Rainfall Losses") is written to `soils.tsoilf` ahead of the catchment's own design ARR losses entry - matches the legacy script's impervious-area loss row. Only written once per model (the first config in a multi-config/append run), matching the legacy script. |
| `climate_change_method` | string | `"burst"` | How the Data Hub's climate-change initial loss adjustment factor is applied to burst-loss (i.e. non complete-storm) events: `"burst"` (default, legacy-equivalent) scales the burst initial loss directly by the factor; `"storm"` instead scales the (baseline) full storm initial loss by the factor, then subtracts a climate-change preburst depth (the climate-change-adjusted point rainfall depth at that duration/AEP, multiplied by the `preburst.percentile` preburst ratio) to derive the climate-change burst initial loss - i.e. the preburst reduction reflects the climate-change rainfall rather than being carried over unchanged from the baseline event. Complete storm events are unaffected by this setting (they already scale the unreduced full storm initial loss directly, matching the `"storm"` approach).

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
| `verbose` | bool | `false` | If `true`, also writes intermediate "working data" files (areal design IFD table, ARF table, burst initial loss table, extrapolated short-duration losses CSV, and raw point/areal temporal pattern increment CSVs) to a `working_data` subfolder - see [Working data](#working-data) below. |

## Working data

Alongside the standard TUFLOW output files, a `working_data` subfolder of `output.path`
is used to save data useful for reviewing/QA'ing what the tool requested and calculated:

* `<site>_ARR_response.json` - the raw JSON response from the ARR Data Hub, exactly as
  received. **Always saved**, regardless of `output.verbose`, so a run can always be
  fully reproduced/inspected later without needing to re-query the Data Hub.
* `<site>_ARR_response_<region>.json` - one per `temporal_patterns.additional_tp`
  region configured (if any) - the raw JSON response from the separate ARR Data Hub
  request made for that region's representative coordinates. **Always saved**, same as
  the site's own response, for the same reason. `<region>` is the region name with
  spaces removed (e.g. `WetTropics`).

The following are only saved when `output.verbose` is `true`, since they are purely for
debugging/QA and are otherwise redundant with the always-written `rf_inflow`/loss
control files:

* `<site>_IFD_after_ARF[_<cc_scenario>].csv` - the areal (post-ARF) design rainfall
  depth (mm) for every requested duration x AEP, one file per climate change scenario
  (if enabled).
* `<site>_ARF[_<cc_scenario>].csv` - the Areal Reduction Factor applied for every
  requested duration x AEP.
* `<site>_burst_initial_loss[_<cc_scenario>].csv` - the burst initial loss (mm) table
  used (per `losses.method`; extrapolated for short durations if
  `losses.extrapolation_method` is not `"none"`), for every duration x AEP, one file per
  climate change scenario (if enabled) - climate change scenario files have the Data
  Hub's climate-change initial loss adjustment factor applied.
* `<site>_extrapolated_losses[_<cc_scenario>].csv` - the extrapolated burst initial
  loss (mm) values, in the same duration (index) x AEP% (columns) table format as
  `<site>_burst_initial_loss...csv`, but containing **only** the rows for durations that
  were actually extrapolated below the Data Hub's shortest provided duration (i.e.
  `losses.extrapolation_method != "none"` and a shorter duration was requested) - for
  easy visual comparison against the full burst initial loss table. One file per
  climate change scenario (if enabled); a scenario's file is omitted entirely if nothing
  was extrapolated for it.
* `<site>_PointTP_Increments.csv` / `<site>_ArealTP_Increments.csv` - the raw temporal
  pattern increment CSVs downloaded from the Data Hub (before selection/filtering to the
  specific patterns used for each event).
* `<site>_PointTP_Increments_<region>.csv` - one per `temporal_patterns.additional_tp`
  region configured (if any) - that region's own raw point temporal pattern increments
  CSV, downloaded from its own separate ARR Data Hub request. `<region>` is the region
  name with spaces removed (e.g. `WetTropics`), matching the `_<region>` suffix used in
  `rf_inflow` column labels (see `additional_tp` above).

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
  way. Only available in NSW (where the Data Hub provides this layer). If the Data Hub
  has no exact (Duration, AEP) match in this layer, the first available preburst
  pattern with the same duration and the same event rarity (AEP band -
  `"frequent"`/`"intermediate"`/`"rare"`) as the requested event is used instead as an
  assumed proxy (a warning is logged). If the Data Hub has no `RecPreburstTP` data at
  all for that duration (e.g. very short durations below its minimum of 30 min), the
  first available point/design temporal pattern (lowest `TP` number) with the same
  duration and event rarity is used as the preburst shape instead - scaled to the
  configured `percentile` ratio depth, same as the `"temporal_pattern"` method below (a
  warning is logged). An error is only raised if no point temporal pattern at all is
  available for that duration/event rarity combination either.
- **`"constant"`** - a single preburst block of a fixed duration (`preburst.pattern_duration`)
  at a constant rate, matching the legacy "Constant Rate" method. The preburst depth is
  derived from the `Preburst<percentile>` ratio table (or the `RecPreburst` layer, if
  `percentile == "recommended"`) multiplied by the point design burst depth.
- **`"temporal_pattern"`** - shapes the preburst rainfall using an existing point
  temporal pattern (`preburst.pattern_tp`) at the closest available duration to the
  computed preburst duration. As with `"constant"`, the preburst depth comes from the
  `Preburst<percentile>` ratio table (or `RecPreburst`). `pattern_tp` is either:
  - a specific pattern, e.g. `"TP03"` - used for every design burst temporal pattern
    column in the event (a single, shared preburst shape), or
  - `"design_burst"` - matches each design burst temporal pattern column to a preburst
    pattern of the *same* `tp_number` (e.g. the `"TP01"` design burst gets a `"TP01"`
    preburst, `"TP02"` gets `"TP02"`, etc), so each column in the `rf_inflow` output has
    its own distinct preburst shape rather than a single shape shared by every column -
    matching the legacy script's per-design-TP preburst option.

**Negligible preburst assumption:** if the resulting preburst depth turns out to be less
than 1% of the point design burst depth (implied preburst ratio < 0.01), the preburst
period is dropped entirely and the event falls back to a standard burst-only event
(using the ordinary burst initial loss, or - for `"Use PB TP"` placeholder cells with no
fixed burst initial loss available - the full storm initial loss as a proxy, since the
preburst contribution is negligible either way).

**Automatic per-cell triggering:** independently of `complete_storm`, whenever the
requested AEP/duration's burst initial loss is the Data Hub's `"Use PB TP"` placeholder
(meaning no fixed burst initial loss value exists for that cell), `pytuflow.arr`
automatically assembles that specific event as a complete storm using the `"recommended"`
preburst method, regardless of `preburst.pattern_method`. A log message records when
this happens. This means most configs never need to set `complete_storm` explicitly -
it is primarily useful for forcing complete storm assembly (with a specific
`pattern_method`) across every event for consistency.

**Requested durations between a `"Use PB TP"` cell and a fixed-value cell:** if a
requested duration falls between two rows of the burst initial loss table where one is
numeric and the other is the `"Use PB TP"` placeholder (for the same AEP), a straight
linear interpolation between them wouldn't make sense (a placeholder isn't a loss
value). Instead, `pytuflow.arr` derives an implied burst initial loss for that cell from
the (interpolated) preburst depth and the storm initial loss: `storm initial loss -
preburst depth`, where the preburst depth is `preburst.percentile` ratio × point design
burst depth at that duration. If the result is positive, it's used directly (no complete
storm needed); if it would be negative (the preburst rainfall alone exceeds the storm
initial loss), the cell is itself treated as `"Use PB TP"`, automatically triggering
complete storm assembly for that specific AEP/duration. A duration bracketed by two
`"Use PB TP"` cells is likewise treated as `"Use PB TP"` (no numeric neighbour exists to
derive anything from).

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
    "pattern_method": "temporal_pattern",
    "pattern_duration": 1.0,
    "pattern_tp": "TP03",
    "duration_proportional": false
  }
}
```

To instead match each design burst temporal pattern column to a preburst pattern of the
*same* `tp_number` (e.g. the `"TP01"` design burst column gets a `"TP01"` preburst, and
so on for every `TP` column), matching the legacy script's per-design-TP preburst
option:

```json
{
  "complete_storm": true,
  "preburst": {
    "percentile": "50%",
    "pattern_method": "temporal_pattern",
    "pattern_duration": 1.0,
    "pattern_tp": "design_burst",
    "duration_proportional": false
  }
}
```

If you leave `"complete_storm": false` (or omit it entirely - it defaults to `false`),
you **do not** need a `preburst` section at all for typical use: any AEP/duration cell
that requires complete storm assembly (the `"Use PB TP"` placeholder cells) will be
handled automatically using the `"recommended"` method. Only add a `preburst` section
in this case if you specifically want those auto-triggered cells to use the
`"constant"`/`"temporal_pattern"` method instead of `"recommended"`.

## Not yet implemented

The following config options are accepted (validated, parsed) but not yet acted on by
the engine - they are reserved for future work and are documented above per-key:

- `events.aep` / `events.duration` == `"all"`
- `temporal_patterns.point_tp_csv` / `areal_tp_csv`

## See also

- `arr_config_schema.md` in the repository root - the original schema design document,
  including rationale for changes vs the legacy script's CLI arguments.
- `ARR_legacy/` - the original `ARR_to_TUFLOW` QGIS plugin script this module replaces
  (kept, untouched, for reference).
- `tests/arr/` - the automated test suite (uses cached real Data Hub API responses by
  default; a live smoke test can be run with `ARR_LIVE_TESTS=1`).
