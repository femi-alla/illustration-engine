"""Request and response models for the illustration engine."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from illustration_engine.assumptions import MAX_ATTAINED_AGE

ScenarioName = Literal["guaranteed", "midpoint", "current"]
DeathBenefitOption = Literal["level", "increasing"]
RiskClass = Literal["preferred", "standard", "substandard"]
CreditingKind = Literal["fixed", "indexed"]


class CreditingAssumption(BaseModel):
    """How interest is credited to the account value.

    ``fixed``: ``current_rate`` is the assumed declared rate and interest is
    credited monthly. ``indexed``: ``current_rate`` is the assumed annual index
    return, which is multiplied by ``participation`` and then clamped between
    ``floor`` and ``cap`` to give the credited rate; interest is credited once
    per policy year. In both cases the guaranteed scenario credits
    ``guaranteed_rate`` and the midpoint scenario credits the average of the
    guaranteed and current rates.
    """

    model_config = ConfigDict(extra="forbid")

    kind: CreditingKind = "fixed"
    current_rate: float = Field(
        0.05, ge=-0.5, le=0.5, description="Assumed declared rate (fixed) or index return (indexed)"
    )
    guaranteed_rate: float | None = Field(
        None,
        ge=0.0,
        le=0.1,
        description="Minimum rate; defaults to 2% for fixed, the floor for indexed",
    )
    cap: float | None = Field(None, ge=0.0, le=0.5, description="Indexed only: maximum credit")
    floor: float = Field(0.0, ge=0.0, le=0.1, description="Indexed only: minimum credit")
    participation: float = Field(1.0, ge=0.0, le=3.0, description="Indexed only: index share")

    @model_validator(mode="after")
    def _apply_defaults_and_check(self) -> CreditingAssumption:
        if self.kind == "indexed" and self.cap is not None and self.cap < self.floor:
            raise ValueError("cap must be greater than or equal to floor")
        if self.guaranteed_rate is None:
            self.guaranteed_rate = 0.02 if self.kind == "fixed" else self.floor
        if self.kind == "indexed" and self.guaranteed_rate > self.floor:
            raise ValueError("guaranteed_rate cannot exceed the floor for an indexed credit")
        return self

    @property
    def effective_guaranteed_rate(self) -> float:
        return self.guaranteed_rate if self.guaranteed_rate is not None else 0.0

    def current_credited_rate(self) -> float:
        """Annual rate credited under current assumptions before the guarantee is applied."""
        if self.kind == "fixed":
            return self.current_rate
        rate = max(self.participation * self.current_rate, self.floor)
        if self.cap is not None:
            rate = min(rate, self.cap)
        return rate

    def credited_rate(self, scenario: ScenarioName) -> float:
        """Annual rate credited under a scenario, never below the guarantee."""
        guaranteed = self.effective_guaranteed_rate
        current = max(self.current_credited_rate(), guaranteed)
        if scenario == "guaranteed":
            return guaranteed
        if scenario == "current":
            return current
        return (guaranteed + current) / 2.0


class ProductOverrides(BaseModel):
    """Optional overrides for the generic charge structure."""

    model_config = ConfigDict(extra="forbid")

    premium_load: float | None = Field(None, ge=0.0, le=0.3)
    monthly_policy_fee: float | None = Field(None, ge=0.0, le=100.0)
    per_thousand_monthly_charge: float | None = Field(None, ge=0.0, le=2.0)
    per_thousand_years: int | None = Field(None, ge=0, le=30)
    current_coi_factor: float | None = Field(None, ge=0.05, le=1.0)


class IllustrationRequest(BaseModel):
    """Inputs that describe the policy being illustrated."""

    model_config = ConfigDict(extra="forbid")

    issue_age: int = Field(..., ge=18, le=85)
    face_amount: float = Field(..., ge=25_000, le=50_000_000)
    annual_premium: float = Field(..., ge=0, le=10_000_000)
    premium_years: int | None = Field(
        None, ge=0, le=100, description="Years premiums are paid; omit to pay every year"
    )
    projection_years: int | None = Field(
        None, ge=1, le=100, description="Years to project; omit to run to attained age 100"
    )
    death_benefit_option: DeathBenefitOption = "level"
    risk_class: RiskClass = "standard"
    crediting: CreditingAssumption = Field(default_factory=CreditingAssumption)
    product: ProductOverrides | None = None

    @model_validator(mode="after")
    def _check_horizon(self) -> IllustrationRequest:
        max_years = MAX_ATTAINED_AGE - self.issue_age
        if self.projection_years is not None and self.projection_years > max_years:
            raise ValueError(f"projection_years cannot exceed {max_years} for this issue age")
        return self

    @property
    def horizon_years(self) -> int:
        """Number of policy years to project."""
        if self.projection_years is not None:
            return self.projection_years
        return max(1, 100 - self.issue_age)


class LedgerRow(BaseModel):
    """One policy year of the illustration. Money fields are end-of-year dollars."""

    policy_year: int
    attained_age: int
    premium_outlay: float
    cumulative_premium: float
    premium_load: float
    expense_charges: float
    coi_charges: float
    interest_credited: float
    account_value: float
    surrender_charge: float
    surrender_value: float
    death_benefit: float
    in_force: bool


class ScenarioLedger(BaseModel):
    """A full projection under one set of assumptions."""

    scenario: ScenarioName
    credited_rate: float
    coi_factor: float
    lapse_year: int | None = None
    rows: list[LedgerRow]


class AssumptionsSummary(BaseModel):
    """Echo of the charge structure used, so a reader can audit the ledger."""

    premium_load: float
    monthly_policy_fee: float
    per_thousand_monthly_charge: float
    per_thousand_years: int
    surrender_charge_years: int
    current_coi_factor: float
    risk_class_multiplier: float


class IllustrationResponse(BaseModel):
    """Three scenario ledgers plus the inputs and assumptions that produced them."""

    request: IllustrationRequest
    assumptions: AssumptionsSummary
    scenarios: dict[ScenarioName, ScenarioLedger]
    notice: str = (
        "Educational software demo. All rates, charges and mortality assumptions are "
        "synthetic. This output is not an offer, quote or illustration of any real product."
    )
