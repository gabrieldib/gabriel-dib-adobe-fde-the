from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter


@dataclass(slots=True)
class RunMetrics:
    total_products_processed: int = 0
    products_skipped: int = 0
    assets_reused: int = 0
    assets_generated: int = 0
    total_variants_produced: int = 0
    execution_time_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class Timer:
    def __init__(self) -> None:
        self._start = perf_counter()

    def elapsed(self) -> float:
        return perf_counter() - self._start
