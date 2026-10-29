"""Command-line front end: print a ledger as a table or as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from illustration_engine.engine import illustrate
from illustration_engine.models import (
    CreditingAssumption,
    IllustrationRequest,
    ScenarioLedger,
)

COLUMNS = (
    ("policy_year", "Yr", 3),
    ("attained_age", "Age", 4),
    ("premium_outlay", "Premium", 11),
    ("coi_charges", "COI", 11),
    ("interest_credited", "Interest", 11),
    ("account_value", "Acct Value", 13),
    ("surrender_value", "Surr Value", 13),
    ("death_benefit", "Death Ben", 13),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="illustrate",
        description="Educational life insurance illustration engine (synthetic assumptions).",
    )
    parser.add_argument("--age", type=int, required=True, help="issue age")
    parser.add_argument("--face", type=float, required=True, help="face amount in dollars")
    parser.add_argument("--premium", type=float, required=True, help="annual premium in dollars")
    parser.add_argument("--premium-years", type=int, default=None, help="years premiums are paid")
    parser.add_argument("--years", type=int, default=None, help="years to project")
    parser.add_argument("--option", choices=("level", "increasing"), default="level")
    parser.add_argument(
        "--risk-class", choices=("preferred", "standard", "substandard"), default="standard"
    )
    parser.add_argument(
        "--rate", type=float, default=0.05, help="assumed current rate or index return"
    )
    parser.add_argument("--guaranteed-rate", type=float, default=0.02)
    parser.add_argument("--indexed", action="store_true", help="use indexed crediting")
    parser.add_argument("--cap", type=float, default=None)
    parser.add_argument("--floor", type=float, default=0.0)
    parser.add_argument("--participation", type=float, default=1.0)
    parser.add_argument(
        "--scenario", choices=("guaranteed", "midpoint", "current", "all"), default="all"
    )
    parser.add_argument("--json", action="store_true", help="emit the full response as JSON")
    return parser


def request_from_args(args: argparse.Namespace) -> IllustrationRequest:
    crediting = CreditingAssumption(
        kind="indexed" if args.indexed else "fixed",
        current_rate=args.rate,
        guaranteed_rate=args.guaranteed_rate,
        cap=args.cap,
        floor=args.floor,
        participation=args.participation,
    )
    return IllustrationRequest(
        issue_age=args.age,
        face_amount=args.face,
        annual_premium=args.premium,
        premium_years=args.premium_years,
        projection_years=args.years,
        death_benefit_option=args.option,
        risk_class=args.risk_class,
        crediting=crediting,
    )


def format_ledger(ledger: ScenarioLedger) -> str:
    header = " ".join(f"{title:>{width}}" for _, title, width in COLUMNS)
    lines = [
        f"{ledger.scenario.upper()} scenario  "
        f"(credited {ledger.credited_rate:.2%}, COI factor {ledger.coi_factor:.2f})",
        header,
        "-" * len(header),
    ]
    for row in ledger.rows:
        cells = []
        for key, _, width in COLUMNS:
            value = getattr(row, key)
            text = f"{value:,.0f}" if isinstance(value, float) else str(value)
            cells.append(f"{text:>{width}}")
        lines.append(" ".join(cells))
    if ledger.lapse_year is not None:
        lines.append(f"Policy lapses in year {ledger.lapse_year}.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        request = request_from_args(args)
    except ValueError as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return 2
    response = illustrate(request)
    if args.json:
        print(json.dumps(response.model_dump(), indent=2))
        return 0
    names = ("guaranteed", "midpoint", "current") if args.scenario == "all" else (args.scenario,)
    for name in names:
        print(format_ledger(response.scenarios[name]))  # type: ignore[index]
        print()
    print(response.notice)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
