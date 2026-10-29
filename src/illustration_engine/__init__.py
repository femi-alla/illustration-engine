"""Educational life insurance illustration engine.

Projects a generic flexible-premium (universal-life style) policy year by year
under guaranteed, midpoint and current assumptions. Every table in this package
is synthetic and illustrative; nothing here describes a real product.
"""

from illustration_engine.engine import illustrate, project_scenario
from illustration_engine.models import (
    CreditingAssumption,
    IllustrationRequest,
    IllustrationResponse,
    LedgerRow,
    ScenarioLedger,
)

__all__ = [
    "CreditingAssumption",
    "IllustrationRequest",
    "IllustrationResponse",
    "LedgerRow",
    "ScenarioLedger",
    "illustrate",
    "project_scenario",
]

__version__ = "0.1.0"
