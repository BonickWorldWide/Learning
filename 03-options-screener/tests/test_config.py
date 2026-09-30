import json

import pytest

from options_screener.config import load_config


def test_defaults_when_no_file(tmp_path):
    config = load_config(tmp_path / "nope.json")
    assert config.pop_delta_range == (0.10, 0.30)
    assert config.cheap_max_contract_cost == 200.00
    assert config.min_days_to_expiry == 7
    assert config.edgar_contact_email == ""
    assert config.include_filings is False
    assert config.finnhub_api_key == ""


def test_include_filings_can_be_turned_on(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"include_filings": True, "edgar_contact_email": "me@example.com"}))
    config = load_config(path)
    assert config.include_filings is True
    assert config.edgar_contact_email == "me@example.com"


def test_reads_overrides_from_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"cheap_max_contract_cost": 500.0, "pop_delta_min": 0.15}))
    config = load_config(path)
    assert config.cheap_max_contract_cost == 500.0
    assert config.pop_delta_min == 0.15
    assert config.pop_delta_max == 0.30  # untouched keys keep their default


def test_max_premium_is_the_contract_cost_divided_by_a_hundred(tmp_path):
    # A real user read a quoted price like "$1.65" as the total cost of one
    # contract when it actually meant $165 -- these two properties exist so
    # every human-facing dollar figure in config.json means "total cost,"
    # and the /100 conversion into a per-share price happens in one place.
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"cheap_max_contract_cost": 30.0, "pop_max_contract_cost": 45.0}))
    config = load_config(path)
    assert config.cheap_max_premium == pytest.approx(0.30)
    assert config.pop_max_premium == pytest.approx(0.45)
