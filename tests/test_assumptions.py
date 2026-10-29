import itertools

from illustration_engine.assumptions import (
    DEFAULT_PRODUCT,
    ProductSpec,
    annual_mortality_rate,
    corridor_factor,
)


def test_mortality_rises_with_age_and_is_bounded() -> None:
    rates = [annual_mortality_rate(age) for age in range(18, 122)]
    assert all(0.0 < r <= 1.0 for r in rates)
    assert all(b >= a for a, b in itertools.pairwise(rates))
    assert annual_mortality_rate(35) < 0.005
    assert annual_mortality_rate(200) == 1.0


def test_corridor_factor_declines_to_one() -> None:
    assert corridor_factor(25) == 2.5
    assert corridor_factor(40) == 2.5
    factors = [corridor_factor(age) for age in range(40, 121)]
    assert all(b <= a for a, b in itertools.pairwise(factors))
    assert corridor_factor(95) == 1.0
    assert corridor_factor(110) == 1.0
    assert 1.0 < corridor_factor(92) < 1.05


def test_surrender_charge_schedule() -> None:
    face = 250_000
    assert DEFAULT_PRODUCT.surrender_charge(face, 1) == 7_500
    assert DEFAULT_PRODUCT.surrender_charge(face, 10) == 750
    assert DEFAULT_PRODUCT.surrender_charge(face, 11) == 0
    assert DEFAULT_PRODUCT.surrender_charge(face, 0) == 0


def test_product_spec_is_immutable_and_overridable() -> None:
    custom = ProductSpec(premium_load=0.0, monthly_policy_fee=0.0)
    assert custom.premium_load == 0.0
    assert DEFAULT_PRODUCT.premium_load == 0.06
