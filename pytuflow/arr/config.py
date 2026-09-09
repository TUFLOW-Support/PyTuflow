"""JSON config file handling for :mod:`pytuflow.arr`.

See ``arr_config_schema.md`` in the repository root for the schema reference and the
rationale behind each section.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Optional, Union

from .exceptions import ArrConfigError

#: Burst initial loss lookup methods. ``"recommended"`` uses the Data Hub's newer burst
#: initial loss table (``BurstLossesNew``); ``"probability_neutral"`` uses the legacy
#: (NSW-only) probability-neutral burst initial loss table (``BurstIL``) - an error is
#: raised if that layer isn't available for the queried location.
LOSS_METHODS = ('recommended', 'probability_neutral')
#: Short-duration (below the Data Hub's shortest provided duration) loss extrapolation
#: methods, ported from the legacy script. ``"none"`` means do not extrapolate (an error
#: is raised if a requested duration is shorter than the Data Hub's minimum).
#: ``"interpolate"``/``"log_interpolate"`` extrapolate the burst initial loss directly
#: (linear, or log-linear on a ``log10(duration)`` axis); ``"interpolate_preburst"``/
#: ``"log_interpolate_preburst"`` instead extrapolate the implied preburst rainfall
#: depth (requires the storm initial loss). These are independent of (not mutually
#: exclusive with) ``losses.method`` above.
EXTRAPOLATION_METHODS = (
    'none', 'interpolate', 'log_interpolate', 'interpolate_preburst', 'log_interpolate_preburst',
    'rahman', 'hill', 'static',
)
IFD_SOURCES = ('bom',)  # future: 'limb', 'qra'
OUTPUT_FORMATS = ('csv', 'ts1')
OUTPUT_NOTATIONS = ('ari', 'aep')


def _from_dict(cls, data: Optional[dict]) -> Any:
    """Builds a dataclass instance ``cls`` from ``data``, ignoring unknown keys and
    falling back to the dataclass defaults for missing keys."""
    data = data or {}
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ArrConfigError(f"Unknown key(s) for '{cls.__name__}': {sorted(unknown)}")
    return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class SiteConfig:
    name: str = ''
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    catchment_area: Optional[float] = None

    def validate(self) -> list[str]:
        errors = []
        if not self.name:
            errors.append("site.name is required")
        if self.latitude is None:
            errors.append("site.latitude is required")
        if self.longitude is None:
            errors.append("site.longitude is required")
        return errors


@dataclass
class IFDConfig:
    source: str = 'bom'
    year: int = 1990

    def validate(self) -> list[str]:
        errors = []
        if self.source not in IFD_SOURCES:
            errors.append(f"ifd.source must be one of {IFD_SOURCES}, got '{self.source}'")
        if self.year not in (1990, 2030):
            errors.append(f"ifd.year must be one of (1990, 2030), got '{self.year}'")
        return errors


@dataclass
class EventsConfig:
    aep: Union[list, str] = field(default_factory=list)
    duration: Union[list, str] = field(default_factory=list)
    output_notation: str = 'ari'

    def validate(self) -> list[str]:
        errors = []
        if not self.aep:
            errors.append("events.aep is required (list of AEP/ARI/EY magnitudes, or 'all')")
        if not self.duration:
            errors.append("events.duration is required (list of durations in minutes, or 'all')")
        if self.output_notation not in OUTPUT_NOTATIONS:
            errors.append(f"events.output_notation must be one of {OUTPUT_NOTATIONS}, got '{self.output_notation}'")
        return errors


@dataclass
class TemporalPatternsConfig:
    point_tp_csv: Optional[str] = None
    areal_tp_csv: Optional[str] = None
    additional_tp: list = field(default_factory=list)
    all_point_tp: bool = False
    add_areal_tp: int = 0

    def validate(self) -> list[str]:
        errors = []
        if self.add_areal_tp < 0:
            errors.append("temporal_patterns.add_areal_tp must be >= 0")
        return errors


@dataclass
class ClimateChangeScenario:
    baseline_year: int = 2090
    ssp: str = 'SSP2'


@dataclass
class ClimateChangeConfig:
    enabled: bool = False
    scenarios: list = field(default_factory=list)

    def __post_init__(self):
        self.scenarios = [
            s if isinstance(s, ClimateChangeScenario) else ClimateChangeScenario(**s)
            for s in self.scenarios
        ]

    def validate(self) -> list[str]:
        errors = []
        if self.enabled and not self.scenarios:
            errors.append("climate_change.scenarios must not be empty when climate_change.enabled is true")
        for s in self.scenarios:
            if s.baseline_year not in (2030, 2050, 2090):
                errors.append(f"climate_change scenario baseline_year must be one of (2030, 2050, 2090), got '{s.baseline_year}'")
            if s.ssp not in ('SSP1', 'SSP2', 'SSP3', 'SSP5'):
                errors.append(f"climate_change scenario ssp must be one of (SSP1, SSP2, SSP3, SSP5), got '{s.ssp}'")
        return errors


@dataclass
class PreburstConfig:
    percentile: str = '50%'
    pattern_method: Optional[str] = None
    pattern_duration: Optional[float] = None
    pattern_tp: Optional[str] = None
    duration_proportional: bool = False

    def validate(self) -> list[str]:
        errors = []
        if self.percentile not in ('10%', '25%', '50%', '75%', '90%', 'recommended'):
            errors.append(
                f"preburst.percentile must be one of (10%, 25%, 50%, 75%, 90%, recommended), got '{self.percentile}'"
            )
        if self.pattern_method is not None and self.pattern_method.lower() not in ('recommended', 'constant', 'pattern'):
            errors.append(
                f"preburst.pattern_method must be one of (recommended, constant, pattern), got '{self.pattern_method}'"
            )
        return errors


@dataclass
class LossesConfig:
    method: str = 'recommended'
    extrapolation_method: str = 'none'
    mar: Optional[float] = None
    static_loss: Optional[float] = None
    tuflow_loss_method: str = 'infiltration'
    user_initial_loss: Optional[float] = None
    user_continuing_loss: Optional[float] = None
    urban_initial_loss: Optional[float] = None
    urban_continuing_loss: Optional[float] = None
    use_global_continuing_loss: bool = False

    def validate(self) -> list[str]:
        errors = []
        if self.method not in LOSS_METHODS:
            errors.append(f"losses.method must be one of {LOSS_METHODS}, got '{self.method}'")
        if self.extrapolation_method not in EXTRAPOLATION_METHODS:
            errors.append(
                f"losses.extrapolation_method must be one of {EXTRAPOLATION_METHODS}, got '{self.extrapolation_method}'"
            )
        if self.tuflow_loss_method not in ('infiltration', 'excess'):
            errors.append(f"losses.tuflow_loss_method must be one of (infiltration, excess), got '{self.tuflow_loss_method}'")
        if self.extrapolation_method == 'rahman' and self.mar is None:
            errors.append("losses.mar is required when losses.extrapolation_method == 'rahman'")
        if self.extrapolation_method == 'hill' and self.mar is None:
            errors.append("losses.mar is required when losses.extrapolation_method == 'hill'")
        if self.extrapolation_method == 'static' and self.static_loss is None:
            errors.append("losses.static_loss is required when losses.extrapolation_method == 'static'")
        return errors


@dataclass
class ArfConfig:
    ignore_limits_for_frequent: bool = False
    min_arf: float = 0.2

    def validate(self) -> list[str]:
        errors = []
        if not (0 <= self.min_arf <= 1):
            errors.append("arf.min_arf must be between 0 and 1")
        return errors


@dataclass
class OutputConfig:
    path: str = ''
    format: str = 'csv'
    verbose: bool = False

    def validate(self) -> list[str]:
        errors = []
        if not self.path:
            errors.append("output.path is required")
        if self.format not in OUTPUT_FORMATS:
            errors.append(f"output.format must be one of {OUTPUT_FORMATS}, got '{self.format}'")
        return errors


@dataclass
class ArrConfig:
    """Top-level, fully parsed and validated ARR config, built from a single JSON config file."""

    site: SiteConfig = field(default_factory=SiteConfig)
    ifd: IFDConfig = field(default_factory=IFDConfig)
    events: EventsConfig = field(default_factory=EventsConfig)
    temporal_patterns: TemporalPatternsConfig = field(default_factory=TemporalPatternsConfig)
    climate_change: ClimateChangeConfig = field(default_factory=ClimateChangeConfig)
    preburst: PreburstConfig = field(default_factory=PreburstConfig)
    losses: LossesConfig = field(default_factory=LossesConfig)
    arf: ArfConfig = field(default_factory=ArfConfig)
    complete_storm: bool = False
    output: OutputConfig = field(default_factory=OutputConfig)

    #: path this config was loaded from, if any (used for error messages / relative paths)
    source_path: Optional[Path] = None

    @classmethod
    def from_dict(cls, data: dict, source_path: Optional[Path] = None) -> 'ArrConfig':
        known = {f.name for f in fields(cls)} - {'source_path'}
        unknown = set(data) - known
        if unknown:
            raise ArrConfigError(f"Unknown top-level config key(s): {sorted(unknown)}")
        config = cls(
            site=_from_dict(SiteConfig, data.get('site')),
            ifd=_from_dict(IFDConfig, data.get('ifd')),
            events=_from_dict(EventsConfig, data.get('events')),
            temporal_patterns=_from_dict(TemporalPatternsConfig, data.get('temporal_patterns')),
            climate_change=_from_dict(ClimateChangeConfig, data.get('climate_change')),
            preburst=_from_dict(PreburstConfig, data.get('preburst')),
            losses=_from_dict(LossesConfig, data.get('losses')),
            arf=_from_dict(ArfConfig, data.get('arf')),
            complete_storm=data.get('complete_storm', False),
            output=_from_dict(OutputConfig, data.get('output')),
            source_path=source_path,
        )
        errors = config.validate()
        if errors:
            prefix = f"Invalid config '{source_path}':\n" if source_path else "Invalid config:\n"
            raise ArrConfigError(prefix + '\n'.join(f'  - {e}' for e in errors))
        return config

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> 'ArrConfig':
        path = Path(path)
        if not path.exists():
            raise ArrConfigError(f"Config file not found: {path}")
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ArrConfigError(f"Invalid JSON in config file '{path}': {e}") from e
        return cls.from_dict(data, source_path=path)

    def validate(self) -> list[str]:
        errors = []
        for section in (self.site, self.ifd, self.events, self.temporal_patterns,
                         self.climate_change, self.preburst, self.losses, self.arf, self.output):
            errors.extend(section.validate())
        return errors
