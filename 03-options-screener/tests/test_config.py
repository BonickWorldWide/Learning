import json

from options_screener.config import load_config


def test_defaults_when_no_file(tmp_path):
    config = load_config(tmp_path / "nope.json")
    assert config.pop_delta_range == (0.10, 0.30)
    assert config.cheap_max_premium == 2.00


def test_reads_overrides_from_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"cheap_max_premium": 5.0, "pop_delta_min": 0.15}))
    config = load_config(path)
    assert config.cheap_max_premium == 5.0
    assert config.pop_delta_min == 0.15
    assert config.pop_delta_max == 0.30  # untouched keys keep their default
