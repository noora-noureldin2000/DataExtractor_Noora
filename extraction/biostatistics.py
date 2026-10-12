import math
from dataclasses import dataclass, field
from typing import Optional

from config import settings
from utils.helpers import logger


@dataclass
class DichotomousData:
    group_label: str
    events: int
    total: int
    variable: Optional[str] = None
    source_page: Optional[int] = None

    @property
    def risk(self) -> float:
        return self.events / self.total if self.total > 0 else 0.0


@dataclass
class ContinuousData:
    group_label: str
    n: int
    variable: Optional[str] = None
    mean: Optional[float] = None
    sd: Optional[float] = None
    median: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    baseline_mean: Optional[float] = None
    baseline_sd: Optional[float] = None
    post_mean: Optional[float] = None
    post_sd: Optional[float] = None
    mean_change: Optional[float] = None
    sd_change: Optional[float] = None
    data_type: str = "post"
    source_page: Optional[int] = None
    warnings: list[str] = field(default_factory=list)

    def compute_mean_change(self) -> Optional[float]:
        if self.mean_change is not None:
            return self.mean_change
        if self.post_mean is not None and self.baseline_mean is not None:
            change = self.post_mean - self.baseline_mean
            self.warnings.append(
                f"Mean change calculated as Post ({self.post_mean}) - Baseline ({self.baseline_mean}) = {change:.2f}"
            )
            return change
        return None

    def compute_sd_change(self, corr: Optional[float] = None) -> Optional[float]:
        if self.sd_change is not None:
            return self.sd_change
        if self.baseline_sd is not None and self.post_sd is not None:
            r = corr if corr is not None else settings.DEFAULT_CORR
            sd_ch = math.sqrt(
                self.baseline_sd**2 + self.post_sd**2
                - 2 * r * self.baseline_sd * self.post_sd
            )
            self.warnings.append(
                f"SD change imputed using Corr={r}: "
                f"sqrt({self.baseline_sd}^2 + {self.post_sd}^2 - 2*{r}*{self.baseline_sd}*{self.post_sd}) = {sd_ch:.2f}"
            )
            return sd_ch
        return None

    def convert_median_iqr(self) -> None:
        if self.median is None or self.q1 is None or self.q3 is None or self.n is None:
            return
        if self.n > 25:
            self.mean = self.median
            self.sd = (self.q3 - self.q1) / 1.35
            self.warnings.append(
                f"n={self.n} > 25: Mean ≈ Median ({self.median}), SD ≈ IQR/1.35 ({self.sd:.2f})"
            )
        else:
            self.mean = (self.q1 + self.median + self.q3) / 3.0
            self.sd = (self.q3 - self.q1) / 1.35
            self.warnings.append(
                f"n={self.n} ≤ 25: Mean ≈ (Q1+Med+Q3)/3 = {self.mean:.2f}, SD ≈ IQR/1.35 = {self.sd:.2f}"
            )

    def check_baseline_discrepancy(self) -> None:
        if self.baseline_mean is not None and self.post_mean is not None:
            if abs(self.baseline_mean) < 1e-9 and abs(self.post_mean) > 1e-9:
                self.warnings.append(
                    "Baseline is effectively zero; using Post-intervention mean."
                )
                self.mean = self.post_mean
                self.sd = self.post_sd
                self.data_type = "post"


@dataclass
class Arm:
    label: str
    population: Optional[str] = None
    continuous: list[ContinuousData] = field(default_factory=list)
    dichotomous: list[DichotomousData] = field(default_factory=list)


@dataclass
class ExtractionResult:
    study_id: str
    nct_number: Optional[str] = None
    arms: list[Arm] = field(default_factory=list)
    population_filter: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    sensitivity_analysis_needed: bool = False

    def check_mixed_data_types(self) -> None:
        data_types_used = set()
        for arm in self.arms:
            for cd in arm.continuous:
                data_types_used.add(cd.data_type)
        if "change" in data_types_used and "post" in data_types_used:
            self.sensitivity_analysis_needed = True
            self.warnings.append(
                "MIXED: Both 'Change' and 'Post-intervention' data detected. "
                "When standardizing via SMD, run a Sensitivity Analysis by "
                "removing Post-intervention studies to check stability."
            )

    def check_bias_unequal_baselines(self) -> None:
        if len(self.arms) < 2:
            return
        baselines = []
        for arm in self.arms:
            for cd in arm.continuous:
                if cd.baseline_mean is not None:
                    baselines.append((arm.label, cd.baseline_mean))
        if len(baselines) >= 2:
            vals = [b[1] for b in baselines]
            diff = abs(vals[0] - vals[1])
            if diff > 0.5 * (abs(vals[0]) + abs(vals[1])) / 2:
                self.warnings.append(
                    f"BIAS WARNING: Unequal baselines detected ({baselines[0][0]}: {vals[0]}, "
                    f"{baselines[1][0]}: {vals[1]}). Extracting Post-intervention data "
                    "may produce misleading results. Consider adjusting for baseline imbalance."
                )


def convert_median_iqr_to_mean_sd(
    median: float, q1: float, q3: float, n: int
) -> tuple[float, float]:
    if n > 25:
        mean = median
    else:
        mean = (q1 + median + q3) / 3.0
    sd = (q3 - q1) / 1.35
    return mean, sd
