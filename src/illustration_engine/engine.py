"""Projection engine.

The policy is processed monthly, the way a flexible-premium policy's
administration system would do it, and reported yearly:

1. Premium (net of load) is added at the start of the policy year.
2. Each month: expense charges, then the cost of insurance (COI) on the net
   amount at risk, then interest (fixed crediting is monthly; indexed crediting
   is applied once at the end of the policy year).
3. If the account value is exhausted the policy lapses and the ledger stops.

Three scenarios are produced, following the usual structure of a regulated
illustration: ``guaranteed`` (maximum charges, minimum interest), ``current``
(the charges and interest assumed today) and ``midpoint`` (the average of the
two for both interest and charges).
"""

from __future__ import annotations

from dataclasses import replace

from illustration_engine.assumptions import (
    DEFAULT_PRODUCT,
    RISK_CLASS_MULTIPLIER,
    ProductSpec,
    annual_mortality_rate,
    corridor_factor,
)
from illustration_engine.models import (
    AssumptionsSummary,
    DeathBenefitOption,
    IllustrationRequest,
    IllustrationResponse,
    LedgerRow,
    ScenarioLedger,
    ScenarioName,
)

SCENARIOS: tuple[ScenarioName, ...] = ("guaranteed", "midpoint", "current")
MONTHS = 12


def build_product(request: IllustrationRequest) -> ProductSpec:
    """Apply any request-level overrides to the default charge structure."""
    if request.product is None:
        return DEFAULT_PRODUCT
    overrides = {k: v for k, v in request.product.model_dump().items() if v is not None}
    return replace(DEFAULT_PRODUCT, **overrides)


def coi_factor_for(scenario: ScenarioName, product: ProductSpec) -> float:
    """Fraction of the guaranteed maximum COI rate charged under a scenario."""
    if scenario == "guaranteed":
        return 1.0
    if scenario == "current":
        return product.current_coi_factor
    return (1.0 + product.current_coi_factor) / 2.0


def death_benefit(
    face_amount: float, account_value: float, attained_age: int, option: DeathBenefitOption
) -> float:
    """Death benefit after the corridor test.

    Option ``level`` pays the face amount; option ``increasing`` pays face plus
    account value. Either way the benefit is at least the account value times
    the corridor factor for the insured's age.
    """
    av = max(account_value, 0.0)
    base = face_amount if option == "level" else face_amount + av
    return max(base, av * corridor_factor(attained_age))


def monthly_rate(annual_rate: float) -> float:
    """Monthly equivalent of an annual effective rate."""
    return float((1.0 + annual_rate) ** (1.0 / MONTHS) - 1.0)


def _money(value: float) -> float:
    return round(value + 0.0, 2)


def project_scenario(
    request: IllustrationRequest, scenario: ScenarioName, product: ProductSpec | None = None
) -> ScenarioLedger:
    """Run one scenario and return its year-by-year ledger."""
    product = product or build_product(request)
    credited_rate = request.crediting.credited_rate(scenario)
    coi_factor = coi_factor_for(scenario, product)
    risk_multiplier = RISK_CLASS_MULTIPLIER[request.risk_class]
    fixed_monthly = monthly_rate(credited_rate) if request.crediting.kind == "fixed" else 0.0

    face = request.face_amount
    option = request.death_benefit_option
    account_value = 0.0
    cumulative_premium = 0.0
    rows: list[LedgerRow] = []
    lapse_year: int | None = None

    for year in range(1, request.horizon_years + 1):
        age_during_year = request.issue_age + year - 1
        pays_premium = request.premium_years is None or year <= request.premium_years
        premium = request.annual_premium if pays_premium else 0.0
        load = premium * product.premium_load
        account_value += premium - load
        cumulative_premium += premium

        year_expense = 0.0
        year_coi = 0.0
        year_interest = 0.0
        lapsed = False

        annual_q = min(1.0, annual_mortality_rate(age_during_year) * risk_multiplier * coi_factor)
        monthly_q = 1.0 - (1.0 - annual_q) ** (1.0 / MONTHS)
        per_thousand = (
            face / 1000.0 * product.per_thousand_monthly_charge
            if year <= product.per_thousand_years
            else 0.0
        )

        for _month in range(MONTHS):
            expense = product.monthly_policy_fee + per_thousand
            account_value -= expense
            year_expense += expense

            benefit = death_benefit(face, account_value, age_during_year, option)
            net_amount_at_risk = max(benefit - max(account_value, 0.0), 0.0)
            coi = net_amount_at_risk * monthly_q
            account_value -= coi
            year_coi += coi

            if account_value < 0.0:
                lapsed = True
                break

            if fixed_monthly:
                interest = account_value * fixed_monthly
                account_value += interest
                year_interest += interest

        if not lapsed and request.crediting.kind == "indexed":
            interest = account_value * credited_rate
            account_value += interest
            year_interest += interest

        if lapsed:
            lapse_year = year
            rows.append(
                LedgerRow(
                    policy_year=year,
                    attained_age=age_during_year + 1,
                    premium_outlay=_money(premium),
                    cumulative_premium=_money(cumulative_premium),
                    premium_load=_money(load),
                    expense_charges=_money(year_expense),
                    coi_charges=_money(year_coi),
                    interest_credited=_money(year_interest),
                    account_value=0.0,
                    surrender_charge=0.0,
                    surrender_value=0.0,
                    death_benefit=0.0,
                    in_force=False,
                )
            )
            break

        surrender_charge = min(product.surrender_charge(face, year), account_value)
        rows.append(
            LedgerRow(
                policy_year=year,
                attained_age=age_during_year + 1,
                premium_outlay=_money(premium),
                cumulative_premium=_money(cumulative_premium),
                premium_load=_money(load),
                expense_charges=_money(year_expense),
                coi_charges=_money(year_coi),
                interest_credited=_money(year_interest),
                account_value=_money(account_value),
                surrender_charge=_money(surrender_charge),
                surrender_value=_money(account_value - surrender_charge),
                death_benefit=_money(death_benefit(face, account_value, age_during_year, option)),
                in_force=True,
            )
        )

    return ScenarioLedger(
        scenario=scenario,
        credited_rate=round(credited_rate, 6),
        coi_factor=round(coi_factor, 6),
        lapse_year=lapse_year,
        rows=rows,
    )


def illustrate(request: IllustrationRequest) -> IllustrationResponse:
    """Run all three scenarios for a request."""
    product = build_product(request)
    scenarios = {name: project_scenario(request, name, product) for name in SCENARIOS}
    summary = AssumptionsSummary(
        premium_load=product.premium_load,
        monthly_policy_fee=product.monthly_policy_fee,
        per_thousand_monthly_charge=product.per_thousand_monthly_charge,
        per_thousand_years=product.per_thousand_years,
        surrender_charge_years=len(product.surrender_charge_per_thousand),
        current_coi_factor=product.current_coi_factor,
        risk_class_multiplier=RISK_CLASS_MULTIPLIER[request.risk_class],
    )
    return IllustrationResponse(request=request, assumptions=summary, scenarios=scenarios)
