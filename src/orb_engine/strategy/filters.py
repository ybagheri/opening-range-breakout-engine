"""Optional confirmation filters for breakouts.

Each filter has: a clear definition, configurable parameters, unit tests,
a documented rationale, and the ability to be fully disabled.

VolumeFilter (rationale: breakouts accompanied by above-average participation
are less likely to be weak/false moves; this mirrors the key empirical finding
of the reference research — relative volume on the breakout bar matters more
than price shape alone):
    RVOL = bar.volume / mean(volume of OR-formation bars)
    pass iff RVOL >= min_rvol. Disabled when min_rvol <= 0 or mean volume <= 0.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VolumeFilter:
    """Relative-volume confirmation. min_rvol <= 0 disables the filter."""

    min_rvol: float = 0.0

    @property
    def enabled(self) -> bool:
        return self.min_rvol > 0

    def rvol(self, bar_volume: float, or_mean_volume: float | None) -> float | None:
        if or_mean_volume is None or or_mean_volume <= 0:
            return None
        return bar_volume / or_mean_volume

    def passes(self, bar_volume: float, or_mean_volume: float | None) -> tuple[bool, str]:
        """Return (passes, reason). Disabled filter always passes."""
        if not self.enabled:
            return True, "volume filter disabled"
        rv = self.rvol(bar_volume, or_mean_volume)
        if rv is None:
            return False, "no baseline OR volume; refusing signal (conservative)"
        if rv >= self.min_rvol:
            return True, f"rvol={rv:.2f} >= {self.min_rvol}"
        return False, f"rvol={rv:.2f} < {self.min_rvol}"
