import json

import pytest

from illustration_engine.cli import main


def test_cli_prints_all_scenarios(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--age", "35", "--face", "250000", "--premium", "3600", "--years", "5"])
    out = capsys.readouterr().out
    assert code == 0
    assert "GUARANTEED scenario" in out
    assert "MIDPOINT scenario" in out
    assert "CURRENT scenario" in out
    assert "Educational software demo" in out


def test_cli_single_scenario_indexed_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--age",
            "45",
            "--face",
            "300000",
            "--premium",
            "5000",
            "--years",
            "3",
            "--indexed",
            "--rate",
            "0.08",
            "--cap",
            "0.09",
            "--guaranteed-rate",
            "0",
            "--scenario",
            "current",
            "--json",
        ]
    )
    assert code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["request"]["crediting"]["kind"] == "indexed"
    assert len(body["scenarios"]["current"]["rows"]) == 3


def test_cli_reports_lapse(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--age", "60", "--face", "250000", "--premium", "0", "--scenario", "guaranteed"])
    assert "Policy lapses in year 1" in capsys.readouterr().out


def test_cli_rejects_invalid_input(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--age", "10", "--face", "250000", "--premium", "100"])
    assert code == 2
    assert "invalid input" in capsys.readouterr().err
