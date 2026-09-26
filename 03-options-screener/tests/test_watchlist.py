import json

import pytest

from options_screener.watchlist import load_watchlist


def test_loads_and_uppercases_tickers(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps(["aapl", " nvda ", "TSLA"]))
    assert load_watchlist(path) == ["AAPL", "NVDA", "TSLA"]


def test_missing_file_raises_with_a_helpful_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="watchlist.example.json"):
        load_watchlist(tmp_path / "nope.json")


def test_non_list_json_raises(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps({"not": "a list"}))
    with pytest.raises(ValueError):
        load_watchlist(path)


def test_non_string_entries_raise(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps(["AAPL", 123]))
    with pytest.raises(ValueError):
        load_watchlist(path)
