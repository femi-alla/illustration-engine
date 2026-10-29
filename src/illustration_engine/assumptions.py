"""Generic, synthetic product assumptions.

These numbers are invented for teaching purposes so that the mechanics of a
flexible-premium policy can be shown end to end. They are not drawn from any
carrier's rate book or any published mortality table.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MAX_ATTAINED_AGE = 121


def annual_mortality_rate(attained_age: int) -> float:
    """Synthetic annual probability of death, q(x), from a Gompertz-Makeham curve.

    q(x) = A + B * exp(c * x), capped at 1.0. The constants give a smooth curve
    that rises from roughly 1 per 1,000 in the 30s to several hundred per 1,000
    near the maximum age. This is a textbook shape, not a real table.
    """
    a, b, c = 0.0005, 0.00003, 0.095
    return min(1.0, a + b * math.exp(c * attained_age))


def corridor_factor(attained_age: int) -> float:
    """Generic death-benefit corridor factor by attained age.

    The corridor keeps the death benefit at least a multiple of the account value
    so that a policy keeps the character of life insurance rather than a pure
    savings vehicle. The factor steps down with age and reaches 1.0 at 95+.
    """
    if attained_age <= 40:
        return 2.50
    if attained_age >= 95:
        return 1.00
    if attained_age <= 90:
        # Linear glide from 2.50 at 40 to 1.05 at 90.
        return round(2.50 - (attained_age - 40) * (1.45 / 50), 4)
    # Then 1.05 at 90 down to 1.00 at 95.
    return round(1.05 - (attained_age - 90) * (0.05 / 5), 4)


RISK_CLASS_MULTIPLIER: dict[str, float] = {
    "preferred": 0.85,
    "standard": 1.00,
    "substandard": 1.50,
}


@dataclass(frozen=True)
class ProductSpec:
    """Charge structure for the generic product.

    Attributes:
        premium_load: Fraction of each premium deducted before it reaches the
            account value (covers premium tax and acquisition expense).
        monthly_policy_fee: Flat per-policy administrative fee deducted monthly.
        per_thousand_monthly_charge: Monthly expense charge per $1,000 of face
            amount, deducted for the first ``per_thousand_years`` policy years.
        per_thousand_years: Number of years the per-thousand charge applies.
        surrender_charge_per_thousand: Surrender charge per $1,000 of face amount
            by policy year, declining to zero after the schedule ends.
        current_coi_factor: Fraction of the guaranteed maximum cost-of-insurance
            rate actually charged under current assumptions.
    """

    premium_load: float = 0.06
    monthly_policy_fee: float = 8.00
    per_thousand_monthly_charge: float = 0.05
    per_thousand_years: int = 10
    surrender_charge_per_thousand: tuple[float, ...] = field(
        default_factory=lambda: (30.0, 27.0, 24.0, 21.0, 18.0, 15.0, 12.0, 9.0, 6.0, 3.0)
    )
    current_coi_factor: float = 0.60

    def surrender_charge(self, face_amount: float, policy_year: int) -> float:
        """Surrender charge in dollars for a given policy year."""
        schedule = self.surrender_charge_per_thousand
        if policy_year < 1 or policy_year > len(schedule):
            return 0.0
        return face_amount / 1000.0 * schedule[policy_year - 1]


DEFAULT_PRODUCT = ProductSpec()
