"""Life-to-plan: extraction, optimization, and narration."""

from .errors import LifeplanError
from .extract import Analysis, analyze
from .loaders import LoadedPrices, PriceLoader, load_price_bars
from .narrate import build_citations, check_faithfulness, narrate
from .optimize import OptimizedPlan, optimize
from .schemas import (
    Citation,
    DeviceConstraint,
    HouseholdConstraints,
    Narration,
    PriceBar,
    ScheduledSlot,
)

__all__ = [
    "Analysis",
    "Citation",
    "DeviceConstraint",
    "HouseholdConstraints",
    "LifeplanError",
    "LoadedPrices",
    "Narration",
    "OptimizedPlan",
    "PriceBar",
    "PriceLoader",
    "ScheduledSlot",
    "analyze",
    "build_citations",
    "check_faithfulness",
    "load_price_bars",
    "narrate",
    "optimize",
]
