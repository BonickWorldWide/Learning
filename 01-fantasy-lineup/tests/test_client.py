import pytest

from fantasy_lineup.client import get_week_players
from fantasy_lineup.config import Config


def _config(**overrides):
    base = dict(
        league_id=123, team_id=1, year=2026, espn_s2=None, swid=None,
        scoring="ppr", player_seasons_lookback=10, team_seasons_lookback=5,
    )
    base.update(overrides)
    return Config(**base)


def test_missing_league_id_raises_before_any_network_call():
    with pytest.raises(ValueError, match="league_id and team_id"):
        get_week_players(_config(league_id=None))


def test_missing_team_id_raises_before_any_network_call():
    with pytest.raises(ValueError, match="league_id and team_id"):
        get_week_players(_config(team_id=None))
