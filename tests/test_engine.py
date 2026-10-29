import pytest

from illustration_engine import (
    CreditingAssumption,
    IllustrationRequest,
    illustrate,
    project_scenario,
)
from illustration_engine.assumptions import DEFAULT_PRODUCT, corridor_factor
from illustration_engine.engine import coi_factor_for, death_benefit, monthly_rate
from illustration_engine.models import ProductOverrides


def base_request(**overrides: object) -> IllustrationRequest:
    params: dict[str, object] = {
        "issue_age": 35,
        "face_amount": 250_000,
        "annual_premium": 3_600,
        "projection_years": 30,
    }
    params.update(overrides)
    return IllustrationRequest.model_validate(params)


def test_three_scenarios_are_ordered_guaranteed_le_midpoint_le_current() -> None:
    result = illustrate(base_request())
    g, m, c = (result.scenarios[k] for k in ("guaranteed", "midpoint", "current"))
    assert g.credited_rate <= m.credited_rate <= c.credited_rate
    assert g.coi_factor >= m.coi_factor >= c.coi_factor
    assert g.coi_factor == 1.0 and c.coi_factor == 0.6 and m.coi_factor == 0.8
    for year in range(min(len(g.rows), len(m.rows), len(c.rows))):
        if g.rows[year].in_force and m.rows[year].in_force and c.rows[year].in_force:
            assert (
                g.rows[year].account_value
                <= m.rows[year].account_value
                <= c.rows[year].account_value
            )


def test_ledger_invariants_while_in_force() -> None:
    result = illustrate(base_request())
    for ledger in result.scenarios.values():
        for row in ledger.rows:
            if not row.in_force:
                continue
            assert row.account_value >= 0
            assert row.surrender_value == pytest.approx(
                row.account_value - row.surrender_charge, abs=0.01
            )
            assert row.surrender_value >= 0
            assert row.death_benefit >= 250_000
            assert (
                row.death_benefit
                >= row.account_value * corridor_factor(row.attained_age - 1) - 0.01
            )
            assert row.premium_load == pytest.approx(row.premium_outlay * 0.06, abs=0.01)


def test_rows_cover_horizon_and_cumulative_premium_adds_up() -> None:
    result = illustrate(base_request(projection_years=20))
    current = result.scenarios["current"]
    assert current.lapse_year is None
    assert [r.policy_year for r in current.rows] == list(range(1, 21))
    assert current.rows[-1].attained_age == 55
    assert current.rows[-1].cumulative_premium == pytest.approx(20 * 3_600)
    assert current.rows[9].surrender_charge == 750.0
    assert current.rows[10].surrender_charge == 0.0


def test_zero_premium_lapses_in_year_one() -> None:
    ledger = project_scenario(base_request(annual_premium=0), "current")
    assert ledger.lapse_year == 1
    assert len(ledger.rows) == 1
    assert ledger.rows[0].in_force is False
    assert ledger.rows[0].account_value == 0.0
    assert ledger.rows[0].death_benefit == 0.0


def test_guaranteed_scenario_can_lapse_before_current() -> None:
    request = base_request(annual_premium=1_800, projection_years=60)
    g = project_scenario(request, "guaranteed")
    c = project_scenario(request, "current")
    assert g.lapse_year is not None
    assert c.lapse_year is None or c.lapse_year > g.lapse_year


def test_limited_premium_years_stop_outlay() -> None:
    ledger = project_scenario(base_request(premium_years=10, annual_premium=8_000), "current")
    outlays = [r.premium_outlay for r in ledger.rows]
    assert outlays[:10] == [8_000.0] * 10
    assert all(o == 0.0 for o in outlays[10:])
    assert ledger.rows[-1].cumulative_premium == 80_000


def test_increasing_option_pays_face_plus_account_value() -> None:
    request = base_request(death_benefit_option="increasing")
    ledger = project_scenario(request, "current")
    row = ledger.rows[14]
    assert row.death_benefit == pytest.approx(250_000 + row.account_value, abs=0.01)
    level = project_scenario(base_request(), "current").rows[14]
    assert level.account_value > row.account_value


def test_corridor_lifts_death_benefit_when_overfunded() -> None:
    request = base_request(annual_premium=60_000, face_amount=100_000, projection_years=10)
    ledger = project_scenario(request, "current")
    last = ledger.rows[-1]
    assert last.death_benefit > 100_000
    factor = corridor_factor(last.attained_age - 1)
    assert last.death_benefit == pytest.approx(last.account_value * factor, abs=0.01)


def test_risk_class_ordering() -> None:
    values = {}
    for risk_class in ("preferred", "standard", "substandard"):
        ledger = project_scenario(base_request(risk_class=risk_class), "current")
        values[risk_class] = ledger.rows[19].account_value
    assert values["preferred"] > values["standard"] > values["substandard"]


def test_indexed_crediting_is_clamped_by_cap_and_floor() -> None:
    capped = CreditingAssumption(kind="indexed", current_rate=0.15, cap=0.09, floor=0.0)
    assert capped.credited_rate("current") == pytest.approx(0.09)
    assert capped.credited_rate("guaranteed") == 0.0
    assert capped.credited_rate("midpoint") == pytest.approx(0.045)

    floored = CreditingAssumption(kind="indexed", current_rate=-0.20, cap=0.09, floor=0.01)
    assert floored.credited_rate("current") == pytest.approx(0.01)

    participation = CreditingAssumption(
        kind="indexed", current_rate=0.08, cap=0.12, floor=0.0, participation=0.5
    )
    assert participation.credited_rate("current") == pytest.approx(0.04)


def test_indexed_projection_credits_once_per_year() -> None:
    fixed = base_request(crediting={"kind": "fixed", "current_rate": 0.06})
    indexed = base_request(
        crediting={
            "kind": "indexed",
            "current_rate": 0.06,
            "cap": 0.10,
            "floor": 0.0,
            "guaranteed_rate": 0.0,
        }
    )
    f = project_scenario(fixed, "current").rows[0]
    i = project_scenario(indexed, "current").rows[0]
    assert i.interest_credited > 0
    # Monthly compounding on a declining balance versus one annual credit on the
    # year-end balance give different but same-order results.
    assert i.interest_credited == pytest.approx(f.interest_credited, rel=0.15)


def test_guaranteed_rate_defaults_by_crediting_kind() -> None:
    assert CreditingAssumption(kind="fixed").guaranteed_rate == 0.02
    assert CreditingAssumption(kind="indexed", floor=0.01).guaranteed_rate == 0.01
    assert CreditingAssumption(kind="indexed").credited_rate("guaranteed") == 0.0


def test_fixed_rate_never_below_guarantee() -> None:
    crediting = CreditingAssumption(kind="fixed", current_rate=0.01, guaranteed_rate=0.02)
    assert crediting.credited_rate("current") == 0.02
    assert crediting.credited_rate("midpoint") == 0.02


def test_invalid_crediting_combinations_are_rejected() -> None:
    with pytest.raises(ValueError):
        CreditingAssumption(kind="indexed", cap=0.01, floor=0.02)
    with pytest.raises(ValueError):
        CreditingAssumption(kind="indexed", guaranteed_rate=0.02, floor=0.0)
    with pytest.raises(ValueError):
        CreditingAssumption(kind="indexed", participation=5.0)
    with pytest.raises(ValueError):
        base_request(projection_years=90)


def test_product_overrides_change_charges() -> None:
    cheap = base_request(product=ProductOverrides(premium_load=0.0, monthly_policy_fee=0.0))
    standard = base_request()
    cheap_row = project_scenario(cheap, "current").rows[0]
    standard_row = project_scenario(standard, "current").rows[0]
    assert cheap_row.premium_load == 0.0
    assert cheap_row.expense_charges < standard_row.expense_charges
    assert cheap_row.account_value > standard_row.account_value


def test_helpers() -> None:
    assert coi_factor_for("guaranteed", DEFAULT_PRODUCT) == 1.0
    assert coi_factor_for("current", DEFAULT_PRODUCT) == 0.6
    assert monthly_rate(0.0) == 0.0
    assert (1 + monthly_rate(0.05)) ** 12 == pytest.approx(1.05)
    assert death_benefit(100_000, -5.0, 30, "level") == 100_000
    assert death_benefit(100_000, 50_000, 30, "increasing") == 150_000


def test_projection_is_deterministic() -> None:
    first = illustrate(base_request()).model_dump()
    second = illustrate(base_request()).model_dump()
    assert first == second


def test_default_horizon_runs_to_age_100() -> None:
    request = base_request(projection_years=None, annual_premium=12_000)
    assert request.horizon_years == 65
    ledger = project_scenario(request, "current")
    assert ledger.rows[-1].attained_age == 100 or ledger.lapse_year is not None
